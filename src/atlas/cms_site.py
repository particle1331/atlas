"""Import the frontend scaffold and project allowlisted public content for Quarto."""

import errno
import logging
import posixpath
import re
import shutil
import stat
import tempfile
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import uuid4

import yaml

from atlas import cms_notebooks as nb
from atlas.cms_source import (
    PRIVATE_NAME,
    SourceBrowserUnavailable,
    ignored_source_paths,
    secret_findings,
    source_files,
    write_source_browser,
)
from atlas.cms_store import (
    CONTENT_DEFAULTS,
    CONTENT_FIELDS,
    FIELDS,
    INTERNAL,
    SECTIONS,
    Store,
    decode,
    digest,
    document,
    duplicate_sources,
    encode,
    now,
    slug,
    split_document,
)

LOGGER = logging.getLogger(__name__)


def imported_body(body: str) -> str:
    """Discard the scaffold's generated post-navigation paragraph."""
    parts = body.rsplit("\n\n", 1)
    if len(parts) == 2 and parts[1].startswith("[←") and "[All posts](" in parts[1]:
        return parts[0].rstrip()
    return body


def initialize(store: Store, empty: bool = False) -> dict:
    with store.lock():
        marker = store.path("backend/cms.yaml")
        if marker.exists():
            schema = decode(marker.read_bytes())
            if schema in ({"schema": 3}, {"schema": 4}):
                return migrate_content(store, schema["schema"])
            store.require_initialized()
            return {"initialized": True, "changed": False}
        if any(
            path
            for directory in ("posts", "collections", "resume")
            for path in store.path(f"backend/{directory}").glob("*.yaml")
        ):
            raise ValueError(
                "Backend records exist without backend/cms.yaml; preserve them for repair."
            )
        if store.path("content/resume.yaml").exists():
            raise ValueError(
                "A résumé profile exists without CMS records; convert it before initialization."
            )
        if any(
            path
            for directory in ("posts", "collections", "resume")
            for pattern in (
                ("*.yaml", "*.md") if directory == "collections" else ("*.yaml",)
            )
            for path in store.path(f"content/{directory}").glob(pattern)
        ):
            raise ValueError(
                "Content sources exist without CMS initialization; preserve them for repair."
            )
        changes = {}
        profile = {"title": "Résumé", "summary": ""}
        timestamp = now()
        imported = {"post": 0, "collection": 0, "resume": 0}
        frontend = store.path("frontend")
        published_posts = set()
        for kind, directory in (("post", "posts"), ("collection", "collections")):
            for path in ([] if empty else sorted((frontend / directory).glob("*.qmd"))):
                meta, body = split_document(path.read_text())
                identity = f"{kind}/{path.stem}"
                record = {
                    "id": identity,
                    "title": str(meta.get("title", path.stem)),
                    "status": "draft" if meta.get("draft") else "published",
                    "short_description": str(meta.get("description", "")),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "internal_notes": "",
                    "internal_todos": [],
                }
                if kind == "post":
                    date = meta.get("date")
                    if date:
                        date = datetime.fromisoformat(str(date))
                        if date.tzinfo is None:
                            date = date.replace(tzinfo=timezone.utc)
                        record["created_at"] = record["updated_at"] = date.isoformat()
                    raw = nb.dump(nb.notebook(imported_body(body)))
                    source = f"content/posts/{path.stem}.ipynb"
                    record.update(
                        tags=meta.get("categories", []),
                        thumbnail_path=None,
                        source_path=source,
                        code_path=None,
                        related_post_ids=[],
                        source_digest=digest(raw),
                    )
                    if store.path(source).exists():
                        raise ValueError(
                            f"Import would overwrite {source}; nothing has been saved."
                        )
                    changes[store.path(source)] = raw
                else:
                    intro = body.split("## Contents", 1)[0].strip()
                    intro = re.sub(r"^!\[.*?\]\(.*?\)\s*", "", intro).strip()
                    members = re.findall(r"\]\(\.\./posts/([a-z0-9-]+)\.qmd\)", body)
                    record.update(
                        cover_path=None,
                        long_description=intro,
                        post_ids=list(dict.fromkeys(f"post/{key}" for key in members)),
                    )
                image = meta.get("image")
                if image:
                    candidate = (path.parent / image).resolve()
                    candidate.relative_to(frontend)
                    relative, image_raw = store.image(candidate)
                    changes[store.path(relative)] = image_raw
                    record["thumbnail_path" if kind == "post" else "cover_path"] = (
                        relative
                    )
                # Incomplete scaffold pages become drafts under the content model.
                if kind == "post":
                    if not body.strip() or not record["short_description"].strip():
                        record["status"] = "draft"
                    if record["status"] == "published":
                        published_posts.add(identity)
                elif (
                    not any(member in published_posts for member in record["post_ids"])
                    or not record["cover_path"]
                ):
                    record["status"] = "draft"
                if kind in CONTENT_FIELDS:
                    for source_path, source_raw in store.prepare_content(
                        record
                    ).items():
                        if source_path.exists():
                            raise ValueError(
                                f"Import would overwrite {source_path.relative_to(store.root)}; nothing has been saved."
                            )
                        changes[source_path] = source_raw
                store.validate(record)
                changes[store.record_path(identity)] = store.record_bytes(record)
                # The body now lives in the canonical notebook/record. This path
                # is generated on sync, so no second authored copy is retained.
                changes[path] = None
                imported[kind] += 1

        resume = frontend / "resume.qmd"
        if resume.exists() and not empty:
            meta, body = split_document(resume.read_text())
            profile["title"] = meta.get("title", "Résumé")
            parts = re.split(r"^## (.+)\n", body, flags=re.M)
            header = parts[0].rstrip()
            summary = re.search(
                r"(::: \{\.resume-summary\}\n)(.*?)(\n <a href=)", header, re.S
            )
            if summary:
                profile["summary"] = summary[2]
                header = (
                    header[: summary.start(2)]
                    + "{{cms:summary}}"
                    + header[summary.end(2) :]
                )
            footer = '\n\n<script src="assets/contact.js"></script>\n'
            for title, section_body in zip(parts[1::2], parts[2::2]):
                section = next(
                    (key for key, value in SECTIONS.items() if value == title), None
                )
                if section is None:
                    raise ValueError(
                        f"Unrecognized résumé section: {title}; nothing has been saved."
                    )
                section_body = section_body.replace(footer.strip(), "").strip()
                pattern = r"^\*\*(.+)\*\*\n" if section == "skills" else r"^### (.+)\n"
                entries = re.split(pattern, section_body, flags=re.M)
                if entries[0].strip():
                    raise ValueError(
                        f"Unrecognized content before {title} entries; nothing has been saved."
                    )
                for index, (heading, entry_body) in enumerate(
                    zip(entries[1::2], entries[2::2])
                ):
                    entry_body = entry_body.strip()
                    subtitle = ""
                    if entry_body.startswith("*") and not entry_body.startswith("**"):
                        subtitle, _, entry_body = entry_body.partition("\n")
                        entry_body = entry_body.strip()
                    identity = f"resume/{section}-{slug(heading)}"
                    while store.record_path(identity) in changes:
                        identity = f"resume/{section}-{slug(heading)}-{uuid4().hex[:8]}"
                    record = {
                        "id": identity,
                        "title": heading,
                        "section": section,
                        "subtitle": subtitle,
                        "position": index,
                        "body": entry_body,
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    }
                    for source_path, source_raw in store.prepare_content(
                        record
                    ).items():
                        if source_path.exists():
                            raise ValueError(
                                f"Import would overwrite {source_path.relative_to(store.root)}; nothing has been saved."
                            )
                        changes[source_path] = source_raw
                    store.validate(record)
                    changes[store.record_path(identity)] = store.record_bytes(record)
                    imported["resume"] += 1
            template = document(meta, header + "\n\n{{cms:entries}}" + footer)
        else:
            template = document(
                {"title": "Résumé"}, "{{cms:summary}}\n\n{{cms:entries}}"
            )
        layout = store.path("frontend/_cms/resume.qmd")
        if layout.exists():
            raise ValueError(
                "The résumé template already exists; nothing has been saved."
            )
        changes[layout] = template
        for page in ("posts", "collections"):
            target = store.path(f"frontend/_cms/{page}.qmd")
            if target.exists():
                raise ValueError(
                    f"The {page} template already exists; nothing has been saved."
                )
            changes[target] = store.path(f"frontend/{page}.qmd").read_bytes()
        changes[store.path("content/resume.yaml")] = encode(profile)
        changes[marker] = encode({"schema": 5})
        store.commit(changes)
        return {"initialized": True, "changed": True, "imported": imported}


def migrate_content(store: Store, schema: int) -> dict:
    """Upgrade schema 3/4 together under the writer lock, preserving values/dates."""
    changes = {}
    migrated = {}
    if schema == 3:
        keys = store.record_keys("post")
        for key in keys:
            identity = f"post/{key}"
            backend_path = store.record_path(identity)
            record = decode(backend_path.read_bytes())
            legacy_fields = (FIELDS["post"] - {"metadata_digest"}) | INTERNAL
            if record.get("id") != identity or set(record) != legacy_fields:
                raise ValueError(f"Malformed legacy post record: {backend_path.name}")
            for path, raw in store.prepare_content(record).items():
                if path.exists():
                    raise ValueError(
                        f"Upgrade would overwrite {path.relative_to(store.root)}; nothing has been saved."
                    )
                changes[path] = raw
            store.validate(record)
            changes[backend_path] = store.record_bytes(record)
        migrated["post"] = len(keys)
    keys = store.record_keys("collection")
    for key in keys:
        identity = f"collection/{key}"
        backend_path = store.record_path(identity)
        record = decode(backend_path.read_bytes())
        legacy_fields = (
            FIELDS["collection"]
            - set(CONTENT_FIELDS["collection"])
            - {"metadata_digest"}
        ) | INTERNAL
        if record.get("id") != identity or set(record) != legacy_fields:
            raise ValueError(f"Malformed legacy collection record: {backend_path.name}")
        old_path = store.path(record["source_path"])
        metadata_path, _ = store.content_source(record)
        if old_path != metadata_path:
            raise ValueError(
                f"Expected collection YAML at {metadata_path.relative_to(store.root)}; nothing has been saved."
            )
        content = CONTENT_DEFAULTS["collection"] | decode(old_path.read_bytes())
        if set(content) != set(CONTENT_FIELDS["collection"]):
            raise ValueError(
                f"Malformed legacy collection YAML: {old_path.relative_to(store.root)}"
            )
        record.update(content)
        for path, raw in store.prepare_content(record).items():
            if path != old_path and path.exists():
                raise ValueError(
                    f"Upgrade would overwrite {path.relative_to(store.root)}; nothing has been saved."
                )
            changes[path] = raw
        store.validate(record)
        changes[backend_path] = store.record_bytes(record)
    migrated["collection"] = len(keys)
    changes[store.path("backend/cms.yaml")] = encode({"schema": 5})
    store.commit(changes)
    return {"initialized": True, "changed": True, "migrated": migrated}


def public_meta(record: dict) -> dict:
    meta = {
        "title": record["title"],
        "description": record["short_description"],
        "date": record["created_at"],
        "date-modified": record["updated_at"],
        "draft": record["status"] == "draft",
    }
    if "tags" in record:
        meta.update(categories=record["tags"])
    image = record.get("thumbnail_path", record.get("cover_path"))
    if image:
        meta["image"] = "../assets/cms/" + Path(image).name
    return meta


def table_text(text: str) -> str:
    """Keep plain text within one Markdown table cell."""
    return re.sub(r"([\\`*_{}\[\]<>!|$])", r"\\\1", " ".join(text.split()))


def link(record: dict, prefix: str = "../posts/") -> str:
    title = table_text(record["title"])
    return f"[{title}]({prefix}{record['id'].split('/')[1]}.html)"


def project_images(store: Store, source: str, text: str, assets: Path) -> str:
    """Copy referenced managed images and rewrite links in the generated cell."""

    def replace(match):
        target = urlsplit(match[2].strip("<>"))
        if target.scheme or target.netloc or not target.path:
            return match[0]
        image = PurePosixPath(
            posixpath.normpath(
                posixpath.join(posixpath.dirname(source), unquote(target.path))
            )
        )
        if image == PurePosixPath("content/images") or not image.is_relative_to(
            "content/images"
        ):
            return match[0]
        canonical = store.path(image.as_posix())
        if not canonical.is_file():
            raise ValueError(f"Missing figure image: {image}")
        relative = image.relative_to("content/images")
        destination = assets / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical, destination)
        url = urlunsplit(
            (
                "",
                "",
                "../assets/cms/" + quote(relative.as_posix()),
                target.query,
                target.fragment,
            )
        )
        if match[2].startswith("<"):
            url = f"<{url}>"
        return match[1] + url

    return nb.IMAGE_LINK.sub(replace, text)


def file_stamp(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size


def copy_post_sidecars(store: Store, source: Path, destination: Path):
    """Keep public sidecars out of the generated browser namespace."""
    files = {}
    for directory, subdirs, filenames in source.walk():
        relative = directory.relative_to(source)

        def allowed(name):
            return (
                not name.startswith(".")
                and Path(name).suffix.lower() not in {".ipynb", ".md", ".yaml", ".yml"}
                and not (len(relative.parts) == 1 and name.casefold() == "source")
            )

        subdirs[:] = [name for name in subdirs if allowed(name)]
        for name in filenames:
            if not allowed(name):
                continue
            file = directory / name
            if file.is_symlink():
                raise ValueError("Notebook sidecars cannot be symlinks.")
            if file.is_file():
                files[PurePosixPath(file.relative_to(store.root))] = file
    ignored = (
        ignored_source_paths(store.root, files)
        if (store.root / ".git").exists()
        else set()
    )
    for path, file in files.items():
        if path not in ignored:
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)


def prune_empty_source_dirs(browser: Path):
    for directory, _, _ in browser.walk(top_down=False):
        try:
            directory.rmdir()
        except OSError as error:
            if error.errno not in {errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST}:
                raise


def prune_source_output(store: Store, *, preview_only: bool, invalidated: set[Path]):
    """Invalidate rendered browser pages even when sync runs without Quarto."""
    frontend = store.path("frontend")
    outputs = ("_site-preview",) if preview_only else ("_site", "_site-preview")
    for output in outputs:
        posts = store.path(f"frontend/{output}/posts")
        for post in posts.iterdir() if posts.is_dir() else ():
            if post.is_symlink() or not post.is_dir():
                continue
            browser = post / "source"
            if browser.is_symlink():
                browser.unlink()
                continue
            for path in browser.rglob("*"):
                if path.is_symlink():
                    path.unlink()
                elif path.is_file():
                    projection = frontend / "posts" / post.name / path.relative_to(post)
                    projection = projection.with_suffix(".qmd")
                    try:
                        stale = (
                            path.suffix != ".html"
                            or projection in invalidated
                            or path.stat().st_mtime_ns < projection.stat().st_mtime_ns
                        )
                    except FileNotFoundError:
                        stale = True
                    if stale:
                        path.unlink(missing_ok=True)
            prune_empty_source_dirs(browser)


def verify_pages_artifact(store: Store):
    """Check the exact output directory that the Pages workflow uploads."""
    site = store.path("frontend/_site")
    if not (site / "index.html").is_file():
        raise ValueError("GitHub Pages output is missing its index.")
    files = {}
    assets = set()

    def raise_walk_error(error: OSError):
        raise error

    try:
        for directory, subdirs, filenames in site.walk(on_error=raise_walk_error):
            for name in subdirs + filenames:
                path = directory / name
                relative = PurePosixPath(path.relative_to(site))
                if name.startswith(".") or PRIVATE_NAME.search(name):
                    raise ValueError("GitHub Pages output contains a private path.")
                if name.casefold() == "_site-preview":
                    raise ValueError(
                        "GitHub Pages output contains draft preview output."
                    )
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    files[relative] = ""
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError(
                        "GitHub Pages output contains a link or special file."
                    )
                if relative.suffix.casefold() in {".ipynb", ".qmd"}:
                    raise ValueError(
                        "GitHub Pages output contains an unrendered source file."
                    )
                if (
                    len(relative.parts) >= 4
                    and relative.parts[0] == "posts"
                    and relative.parts[2] == "source"
                ):
                    try:
                        projection = store.path(
                            f"frontend/{relative.with_suffix('.qmd')}"
                        )
                    except ValueError:
                        raise ValueError(
                            "GitHub Pages output contains an unapproved source page."
                        ) from None
                    if relative.suffix != ".html" or not projection.is_file():
                        raise ValueError(
                            "GitHub Pages output contains an unapproved source page."
                        )
                if relative.parts[0] == "assets" and not relative.is_relative_to(
                    "assets/cms"
                ):
                    # Authored frontend assets are also copied as Quarto resources.
                    assets.add(PurePosixPath("frontend") / relative)
                try:
                    files[relative] = path.read_bytes().decode("utf-8")
                except UnicodeDecodeError:
                    files[relative] = ""  # Screen binary asset names.
        if ignored_source_paths(store.root, assets):
            raise ValueError("GitHub Pages output contains a Git-ignored asset.")
        blocked = secret_findings(files)
    except OSError:
        raise ValueError("GitHub Pages output could not be verified.") from None
    if blocked:
        raise ValueError(
            f"GitHub Pages verification found possible secrets in {len(blocked)} output path(s)."
        )


def generate(
    store: Store,
    preview: bool = False,
    *,
    watch_snapshot: dict | None = None,
    source_browser: bool = True,
    require_source_browser: bool = False,
    before_install: Callable[[], None] | None = None,
) -> dict:
    """Project saved source and public metadata into ignored frontend files."""
    with store.lock():
        store.require_initialized()
        posts = [item["record"] for item in store.ls("post")]
        collections = [item["record"] for item in store.ls("collection")]
        resumes = [item["record"] for item in store.ls("resume")]
        shared = duplicate_sources(posts)
        if shared:
            path, identities = next(iter(shared.items()))
            raise ValueError(
                "A notebook source path can belong to only one post: "
                f"{path} ({', '.join(identities)})."
            )
        changes = {}
        notebooks = {}
        for record in posts + collections + resumes:
            path = store.path(record["source_path"])
            if path.exists():
                raw = path.read_bytes()
                if record["id"].startswith("post/"):
                    notebooks[record["id"]] = nb.load(raw)
                if digest(raw) != record["source_digest"]:
                    record.update(source_digest=digest(raw), updated_at=now())
                    changes[store.record_path(record["id"])] = store.record_bytes(
                        record
                    )
            elif record.get("status") == "published":
                raise ValueError(f"Missing notebook: {record['source_path']}")
            if record["id"].startswith(("post/", "collection/")):
                metadata_path, digest_field = store.content_source(record)
                observed = digest(metadata_path.read_bytes())
                if observed != record[digest_field]:
                    record.update({digest_field: observed, "updated_at": now()})
                    changes[store.record_path(record["id"])] = store.record_bytes(
                        record
                    )
        # Source dates describe observation at explicit sync, never filesystem mtime.
        store.commit(changes)
        if watch_snapshot is not None:
            # Acknowledge our writes while other CMS writers are still locked out.
            for path in changes:
                watch_snapshot[path.relative_to(store.root).as_posix()] = file_stamp(
                    path
                )
        selected_posts = [r for r in posts if preview or r["status"] == "published"]
        selected_collections = [
            r for r in collections if preview or r["status"] == "published"
        ]
        by_id = {r["id"]: r for r in selected_posts}
        for record in selected_posts + selected_collections:
            store.references(record)
            if not preview:
                store.ready(record)
        browsers = {}
        if source_browser:
            try:
                browsers = source_files(store, selected_posts)
            except SourceBrowserUnavailable as error:
                if require_source_browser:
                    raise
                LOGGER.warning("Companion source disabled. %s", error)
            except OSError:
                if require_source_browser:
                    raise SourceBrowserUnavailable(
                        "Companion source inputs could not be read."
                    ) from None
                LOGGER.warning(
                    "Companion source disabled because its inputs could not be read."
                )
        site = store.path("frontend")
        stage = Path(
            tempfile.mkdtemp(prefix="projection-", dir=store.path(".atlas/cms"))
        )
        try:
            # Stage only new projections. The existing generated pages and
            # static frontend assets do not need to be copied on every sync.
            for directory in ("posts", "collections"):
                (stage / directory).mkdir()
            (stage / "assets/cms").mkdir(parents=True)
            for record in selected_posts + selected_collections:
                image = record.get("thumbnail_path", record.get("cover_path"))
                if image and store.path(image).exists():
                    shutil.copyfile(
                        store.path(image), stage / "assets/cms" / Path(image).name
                    )
            copied_sidecars = set()
            for record in selected_posts:
                value = deepcopy(
                    notebooks.get(
                        record["id"],
                        nb.notebook("Draft notebook has not been created yet."),
                    )
                )
                # Strip source document metadata; the CMS owns document metadata.
                if value["cells"] and value["cells"][0]["cell_type"] == "markdown":
                    text = nb.source(value["cells"][0])
                    if text.startswith("---\n"):
                        try:
                            _, body = split_document(text)
                        except (ValueError, yaml.YAMLError):
                            # A leading Markdown horizontal rule is ordinary
                            # authored content, not necessarily YAML metadata.
                            pass
                        else:
                            value["cells"][0]["source"] = body
                for item in value["cells"]:
                    if item["cell_type"] == "markdown":
                        original = nb.source(item)
                        projected = re.sub(
                            r"(\]\([^\s)]+)\.qmd(?=[#)])", r"\1.html", original
                        )
                        projected = project_images(
                            store,
                            record["source_path"],
                            projected,
                            stage / "assets/cms",
                        )
                        if projected != original:
                            item["source"] = projected.splitlines(keepends=True)
                meta = public_meta(record)
                files = browsers.get(record["id"])
                if files is not None:
                    href = write_source_browser(stage, record, files)
                    shortcut = f"[📁 `source`]({href}){{.source-browser-link}}"
                    meta["margin-header"] = shortcut
                    # Quarto hides the margin sidebar below the md breakpoint.
                    source_cell = nb.cell(f"::: {{.d-md-none}}\n{shortcut}\n:::")
                    source_cell["id"] = "cms-source-browser"
                    value["cells"].insert(0, source_cell)
                metadata_cell = nb.cell(document(meta).decode())
                metadata_cell["id"] = "cms-metadata"
                value["cells"].insert(0, metadata_cell)
                (stage / "posts" / f"{record['id'].split('/')[1]}.ipynb").write_bytes(
                    nb.dump(value)
                )
                # Notebook-relative sidecars retain their authored paths.
                source_dir = store.path(record["source_path"]).parent
                if source_dir in copied_sidecars:
                    continue
                copied_sidecars.add(source_dir)
                copy_post_sidecars(store, source_dir, stage / "posts")
            for record in selected_collections:
                lines = []
                if record["cover_path"]:
                    lines.append(
                        f"![{record['cover_caption']}](../assets/cms/{Path(record['cover_path']).name})"
                    )
                lines.append(record["long_description"])
                members = [
                    by_id[identity]
                    for identity in record["post_ids"]
                    if identity in by_id
                ]
                rows = [
                    "| # | Title | Short description | Last modified |",
                    "| --- | --- | --- | --- |",
                ]
                for index, member in enumerate(members, 1):
                    modified = datetime.fromisoformat(member["updated_at"]).date()
                    rows.append(
                        f"| {index} | {link(member)} | "
                        f"{table_text(member['short_description'])} | {modified} |"
                    )
                lines.append(
                    "::: {.collection-contents}\n\n" + "\n".join(rows) + "\n\n:::"
                )
                (
                    stage / "collections" / f"{record['id'].split('/')[1]}.qmd"
                ).write_bytes(document(public_meta(record), "\n\n".join(lines)))
            for page, contents in (
                ("posts", "posts/*.ipynb"),
                ("collections", "collections/*.qmd"),
            ):
                meta, body = split_document(
                    store.path(f"frontend/_cms/{page}.qmd").read_text()
                )
                meta["listing"]["contents"] = (
                    contents
                    if (selected_posts if page == "posts" else selected_collections)
                    else []
                )
                (stage / f"{page}.qmd").write_bytes(document(meta, body))
            profile = decode(store.path("content/resume.yaml").read_bytes())
            meta, template = split_document(
                store.path("frontend/_cms/resume.qmd").read_text()
            )
            meta["title"] = profile["title"]
            sections = []
            pdf_sections = []
            for section, title in SECTIONS.items():
                entries = [r for r in resumes if r["section"] == section]
                if not entries:
                    continue
                sections.append(f"## {title}")
                pdf_sections.append(f"## {title}")
                for entry in entries:
                    heading = (
                        f"**{entry['title']}**"
                        if section == "skills"
                        else f"### {entry['title']}"
                    )
                    sections += [heading, entry["subtitle"], entry["body"]]
                    subtitle = (
                        "::: {.resume-subtitle}\n\n" + entry["subtitle"] + "\n\n:::"
                        if entry["subtitle"]
                        else ""
                    )
                    pdf_sections += [heading, subtitle, entry["body"]]
            body = template.replace("{{cms:summary}}", profile["summary"]).replace(
                "{{cms:entries}}", "\n\n".join(sections)
            )
            (stage / "resume.qmd").write_bytes(document(meta, body))
            pdf_template = store.path("frontend/_cms/resume-pdf.qmd")
            pdf_meta, pdf_body = (
                split_document(pdf_template.read_text())
                if pdf_template.exists()
                else ({}, "{{cms:summary}}\n\n{{cms:entries}}")
            )
            pdf_meta["title"] = profile["title"]
            pdf_body = pdf_body.replace("{{cms:summary}}", profile["summary"]).replace(
                "{{cms:entries}}", "\n\n".join(pdf_sections)
            )
            # Install complete generated files together through the recoverable
            # writer. Templates, configuration and authored notebooks stay put.
            generated = {}
            for directory in ("posts", "collections", "assets/cms"):
                for path in (stage / directory).rglob("*"):
                    if path.is_file():
                        target = store.path(
                            "frontend/" + path.relative_to(stage).as_posix()
                        )
                        generated[target] = path.read_bytes()
                for path in (site / directory).rglob("*"):
                    if (
                        path.is_file()
                        and path not in generated
                        and path != site / directory / "_metadata.yml"
                    ):
                        generated[path] = None
            for page in ("resume.qmd", "posts.qmd", "collections.qmd"):
                generated[store.path("frontend/" + page)] = (stage / page).read_bytes()
            generated[store.path(".atlas/cms/resume.qmd")] = document(
                pdf_meta, pdf_body
            )
            if before_install is not None:
                before_install()
            invalidated = store.commit(generated)
            for browser in (site / "posts").glob("*/source"):
                if not browser.is_symlink():
                    prune_empty_source_dirs(browser)
            prune_source_output(
                store, preview_only=not source_browser, invalidated=invalidated
            )
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return {
            "site": str(site),
            "preview": preview,
            "posts": len(selected_posts),
            "collections": len(selected_collections),
            "resume_entries": len(resumes),
        }
