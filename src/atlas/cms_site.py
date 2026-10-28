"""Import the frontend scaffold and project allowlisted public content for Quarto."""

import posixpath
import re
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import uuid4

import yaml

from atlas import cms_notebooks as nb
from atlas.cms_store import (
    CONTENT_FIELDS,
    SECTIONS,
    Store,
    decode,
    digest,
    document,
    encode,
    now,
    slug,
    split_document,
)


def imported_body(body: str) -> str:
    """Discard the scaffold's legacy navigation paragraph."""
    parts = body.rsplit("\n\n", 1)
    if len(parts) == 2 and parts[1].startswith("[←") and "[All posts](" in parts[1]:
        return parts[0].rstrip()
    return body


def migrate_content_records(store: Store) -> dict:
    """Split the previous mixed content/ records without changing authored values."""
    profile_path = store.path("content/resume.yaml")
    profile = decode(profile_path.read_bytes())
    if (
        set(profile) != {"schema", "title", "summary"}
        or type(profile["schema"]) is not int
        or profile["schema"] != 1
    ):
        raise ValueError(
            "Content exists without backend records; preserve it for repair."
        )
    if (
        not isinstance(profile["title"], str)
        or not profile["title"].strip()
        or not isinstance(profile["summary"], str)
    ):
        raise ValueError("Résumé title and summary must be text.")
    changes = {
        profile_path: encode({key: profile[key] for key in ("title", "summary")})
    }
    migrated = {"post": 0, "collection": 0, "resume": 0}
    for kind, directory in (
        ("post", "posts"),
        ("collection", "collections"),
        ("resume", "resume"),
    ):
        for path in sorted(store.path(f"content/{directory}").glob("*.yaml")):
            record = decode(path.read_bytes())
            identity = f"{kind}/{path.stem}"
            if record.get("id") != identity:
                raise ValueError(
                    f"Record identity does not match {path}; nothing has been saved."
                )
            if kind in CONTENT_FIELDS:
                source_path, source_raw = store.prepare_content(record)
                changes[source_path] = source_raw
            else:
                changes[path] = None
            store.validate(record)
            changes[store.record_path(identity)] = store.record_bytes(record)
            migrated[kind] += 1
    changes[store.path("backend/cms.yaml")] = encode({"schema": 2})
    store.commit(changes)
    store.require_initialized()
    return {"initialized": True, "changed": True, "migrated": migrated}


def initialize(store: Store, empty: bool = False) -> dict:
    with store.lock():
        marker = store.path("backend/cms.yaml")
        if marker.exists():
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
            return migrate_content_records(store)
        if any(
            path
            for directory in ("posts", "collections", "resume")
            for path in store.path(f"content/{directory}").glob("*.yaml")
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
                        toc=bool(meta.get("toc", True)),
                        toc_depth=meta.get("toc-depth", 3),
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
                    if (
                        not record["thumbnail_path"]
                        or not body.strip()
                        or not record["short_description"].strip()
                    ):
                        record["status"] = "draft"
                    if record["status"] == "published":
                        published_posts.add(identity)
                elif (
                    not any(member in published_posts for member in record["post_ids"])
                    or not record["cover_path"]
                ):
                    record["status"] = "draft"
                if kind in CONTENT_FIELDS:
                    source_path, source_raw = store.prepare_content(record)
                    if source_path.exists():
                        raise ValueError(
                            f"Import would overwrite {record['source_path']}; nothing has been saved."
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
                    source_path, source_raw = store.prepare_content(record)
                    if source_path.exists():
                        raise ValueError(
                            f"Import would overwrite {record['source_path']}; nothing has been saved."
                        )
                    changes[source_path] = source_raw
                    store.validate(record)
                    changes[store.record_path(identity)] = store.record_bytes(record)
                    imported["resume"] += 1
            template = document(meta, header + "\n\n{{cms:entries}}" + footer)
        else:
            template = document(
                {"title": "Résumé", "toc": True}, "{{cms:summary}}\n\n{{cms:entries}}"
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
        changes[marker] = encode({"schema": 2})
        store.commit(changes)
        return {"initialized": True, "changed": True, "imported": imported}


def public_meta(record: dict) -> dict:
    meta = {
        "title": record["title"],
        "description": record["short_description"],
        "date": record["created_at"],
        "date-modified": record["updated_at"],
        "draft": record["status"] == "draft",
        "toc": record.get("toc", True),
    }
    if "tags" in record:
        meta.update(categories=record["tags"], **{"toc-depth": record["toc_depth"]})
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


def reading_time(value: dict) -> int:
    """Estimate minutes from saved notebook prose at 200 words per minute."""
    words = sum(
        len(nb.source(item).split())
        for item in value.get("cells", [])
        if item["cell_type"] == "markdown"
    )
    return max(1, (words + 199) // 200)


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


def generate(store: Store, preview: bool = False) -> dict:
    """Project saved source and public metadata into ignored frontend files."""
    with store.lock():
        store.require_initialized()
        posts = [item["record"] for item in store.ls("post")]
        collections = [item["record"] for item in store.ls("collection")]
        resumes = [item["record"] for item in store.ls("resume")]
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
        # Source dates describe observation at explicit sync, never filesystem mtime.
        store.commit(changes)
        selected_posts = [r for r in posts if preview or r["status"] == "published"]
        selected_collections = [
            r for r in collections if preview or r["status"] == "published"
        ]
        by_id = {r["id"]: r for r in selected_posts}
        for record in selected_posts + selected_collections:
            store.references(record)
            if not preview:
                store.ready(record)
        site = store.path("frontend")
        stage = Path(
            tempfile.mkdtemp(prefix="projection-", dir=store.path(".atlas/cms"))
        )
        try:
            shutil.copytree(
                store.path("frontend"),
                stage,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "_site*", ".quarto", "_cms", "__pycache__"
                ),
            )
            for directory in ("posts", "collections"):
                target = stage / directory
                target.mkdir(exist_ok=True)
                for path in target.rglob("*"):
                    if path.is_file() and path.name != "_metadata.yml":
                        path.unlink()
            if (stage / "assets/cms").exists():
                shutil.rmtree(stage / "assets/cms")
            (stage / "assets/cms").mkdir(parents=True, exist_ok=True)
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
                metadata_cell = nb.cell(document(public_meta(record)).decode())
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
                for sidecar in source_dir.iterdir() if source_dir.exists() else []:
                    if sidecar.name.startswith(".") or sidecar.suffix in (
                        ".ipynb",
                        ".md",
                        ".yaml",
                        ".yml",
                    ):
                        continue
                    if sidecar.is_symlink() or (
                        sidecar.is_dir()
                        and any(p.is_symlink() for p in sidecar.rglob("*"))
                    ):
                        raise ValueError("Notebook sidecars cannot be symlinks.")
                    destination = stage / "posts" / sidecar.name
                    if sidecar.is_dir():
                        shutil.copytree(
                            sidecar,
                            destination,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(
                                ".*", "*.yaml", "*.yml", "*.md", "*.ipynb"
                            ),
                        )
                    else:
                        shutil.copyfile(sidecar, destination)
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
                    "| # | Title | Short description | Reading time | Created at |",
                    "| --- | --- | --- | --- | --- |",
                ]
                for index, member in enumerate(members, 1):
                    minutes = reading_time(notebooks.get(member["id"], {}))
                    created = datetime.fromisoformat(member["created_at"]).date()
                    rows.append(
                        f"| {index} | {link(member)} | "
                        f"{table_text(member['short_description'])} | "
                        f"{minutes} min | {created} |"
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
            for section, title in SECTIONS.items():
                entries = [r for r in resumes if r["section"] == section]
                if not entries:
                    continue
                sections.append(f"## {title}")
                for entry in entries:
                    heading = (
                        f"**{entry['title']}**"
                        if section == "skills"
                        else f"### {entry['title']}"
                    )
                    sections += [heading, entry["subtitle"], entry["body"]]
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
                "{{cms:entries}}", "\n\n".join(sections)
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
                        and path.name != "_metadata.yml"
                    ):
                        generated[path] = None
            for page in ("resume.qmd", "posts.qmd", "collections.qmd"):
                generated[store.path("frontend/" + page)] = (stage / page).read_bytes()
            generated[store.path(".atlas/cms/resume.qmd")] = document(
                pdf_meta, pdf_body
            )
            store.commit(generated)
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
