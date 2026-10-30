"""A terminal CMS over the documented Atlas authoring model."""

import functools
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml
from PIL import Image
from rich.console import Console
from rich.table import Table

from atlas.cms_site import generate, initialize
from atlas.cms_store import (
    Conflict,
    NotFound,
    Store,
    decode,
    digest,
    duplicate_sources,
    encode,
    normalized_tags,
    now,
)
from atlas.config import ROOT_PATH

app = typer.Typer(
    no_args_is_help=True, help="Create and edit posts, collections and résumé entries."
)
post = typer.Typer(no_args_is_help=True, help="Notebook posts and listing metadata.")
collection = typer.Typer(
    no_args_is_help=True, help="Collections and their ordered contents."
)
resume = typer.Typer(
    no_args_is_help=True, help="Résumé profile and ordered YAML entries."
)
app.add_typer(post, name="post")
app.add_typer(collection, name="collection")
app.add_typer(resume, name="resume")
Identity = Annotated[
    str, typer.Argument(help="Exact immutable ID returned by new or ls.")
]
Revision = Annotated[
    str | None,
    typer.Option(
        "--expected-revision", help="Reject the save if this revision changed."
    ),
]
File = Annotated[
    Path | None,
    typer.Option(
        "--file",
        "-f",
        help="Read plain text from a file, or '-' for stdin. Otherwise open $VISUAL/$EDITOR.",
    ),
]


def guard(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (
            ValueError,
            OSError,
            yaml.YAMLError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            code = (
                3
                if isinstance(error, Conflict)
                else 4 if isinstance(error, NotFound) else 2
            )
            typer.echo(json.dumps({"error": str(error)}, ensure_ascii=False), err=True)
            raise typer.Exit(code) from error

    return wrapped


def emit(value):
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@app.callback()
def configure(
    ctx: typer.Context,
    root: Annotated[
        Path, typer.Option(help="Atlas workspace root; defaults to this checkout.")
    ] = ROOT_PATH,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print lists as JSON for scripts.")
    ] = False,
):
    ctx.obj = {"store": Store(root), "json": as_json}


def store_for(ctx: typer.Context) -> Store:
    return ctx.obj["store"]


def read_text(
    filename: Path | None, initial: str = "", extension: str = ".md"
) -> str | None:
    if filename is not None:
        return sys.stdin.read() if str(filename) == "-" else filename.read_text()
    return edit_text(initial, extension)


def edit_text(initial: str, extension: str) -> str | None:
    """Run a configured editor without a shell, keeping text on editor failure."""
    command = shlex.split(os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi")
    if not command:
        raise ValueError("Set VISUAL or EDITOR to a text editor command.")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=extension, prefix="atlas-", delete=False
    ) as handle:
        handle.write(initial)
        path = Path(handle.name)
    try:
        result = subprocess.run([*command, str(path)], check=False)
        if result.returncode:
            raise ValueError(
                f"Editor exited with code {result.returncode}; text is preserved at {path}."
            )
        edited = path.read_text()
    except OSError as error:
        raise ValueError(
            f"Could not run editor; text is preserved at {path}: {error}"
        ) from error
    path.unlink()
    return edited if edited != initial else None


def preserve_edit(store: Store, text: str, error: Exception):
    path = store.preserve(f"edits/{uuid4().hex}.txt", text.encode())
    raise type(error)(f"{error} Your entered text is preserved at {path}.") from error


def listing(ctx: typer.Context, kind: str, section: str | None = None):
    store = store_for(ctx)
    with store.lock():
        items = store.ls(kind)
    if section:
        items = [item for item in items if item["record"].get("section") == section]
    if ctx.obj["json"]:
        emit(items)
        return
    table = Table("ID", "Section" if kind == "resume" else "Status", "Title")
    table.columns[0].overflow = "fold"
    for item in items:
        record = item["record"]
        table.add_row(
            record["id"],
            record.get("section", record.get("status", "")),
            record["title"],
        )
    Console().print(table)


@app.command("init")
@guard
def init(
    ctx: typer.Context,
    empty: Annotated[
        bool,
        typer.Option(help="Start empty instead of importing frontend sample content."),
    ] = False,
):
    """Initialize backend records or migrate the former mixed content/ layout."""
    emit(initialize(store_for(ctx), empty))


@post.command("ls")
@guard
def post_ls(ctx: typer.Context):
    """List post IDs, statuses and titles."""
    listing(ctx, "post")


@collection.command("ls")
@guard
def collection_ls(ctx: typer.Context):
    """List collections."""
    listing(ctx, "collection")


@resume.command("ls")
@guard
def resume_ls(ctx: typer.Context, section: str | None = None):
    """List résumé entries in their display order."""
    listing(ctx, "resume", section)


def show(ctx, identity, kind):
    if not identity.startswith(kind + "/"):
        raise ValueError(f"Expected a {kind}/ ID.")
    store = store_for(ctx)
    with store.lock():
        emit(store.get(identity))


@post.command("show")
@guard
def post_show(ctx: typer.Context, identity: Identity):
    """Read all public/internal fields and the exact edit revision."""
    show(ctx, identity, "post")


@collection.command("show")
@guard
def collection_show(ctx: typer.Context, identity: Identity):
    """Read collection metadata, ordered membership and revision."""
    show(ctx, identity, "collection")


@resume.command("show")
@guard
def resume_show(ctx: typer.Context, identity: Identity):
    """Read an entry without any page layout markup."""
    show(ctx, identity, "resume")


@post.command("new")
@guard
def post_new(ctx: typer.Context, title: str, description: str = "", tags: str = ""):
    """Create a draft and an empty notebook. No planning step is required."""
    emit(
        store_for(ctx).new(
            "post",
            title,
            short_description=description,
            tags=normalized_tags(tags.split(",")) if tags else [],
        )
    )


@collection.command("new")
@guard
def collection_new(ctx: typer.Context, title: str, description: str = ""):
    """Create an empty draft collection."""
    emit(store_for(ctx).new("collection", title, short_description=description))


@resume.command("add")
@guard
def resume_add(
    ctx: typer.Context,
    title: str,
    section: Annotated[
        str, typer.Option(help="employment, skills, education, or projects.")
    ],
    subtitle: str = "",
    file: File = None,
):
    """Append an entry. --file supplies its body; otherwise open your editor."""
    body = read_text(file)
    if body is not None:
        store = store_for(ctx)
        try:
            result = store.new(
                "resume",
                title,
                section=section,
                subtitle=subtitle,
                body=body.strip("\n"),
            )
        except (ValueError, OSError, yaml.YAMLError) as error:
            preserve_edit(store, body, error)
        emit(result)


def edit_fields(ctx, identity, kind, patch, expected, image=None):
    if not identity.startswith(kind + "/"):
        raise ValueError(f"Expected a {kind}/ ID.")
    store = store_for(ctx)
    if not patch and image is None:
        with store.lock():
            loaded = store.get(identity)
        store.check_revision(loaded, expected)
        expected = loaded["revision"]
        record = loaded["record"]
        patch["title"] = typer.prompt("Title", default=record["title"])
        if kind != "resume":
            patch["short_description"] = typer.prompt(
                "Short description", default=record["short_description"]
            )
        if kind == "post":
            text = typer.prompt(
                "Tags (comma-separated; blank to clear)",
                default=", ".join(record["tags"]),
            )
            patch["tags"] = text.split(",") if text else []
        if kind == "resume":
            patch["subtitle"] = typer.prompt(
                "Subtitle / dates", default=record["subtitle"]
            )
    emit(store.update(identity, patch, expected, image))


@post.command("edit")
@guard
def post_edit(
    ctx: typer.Context,
    identity: Identity,
    title: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    code_path: Annotated[
        str | None,
        typer.Option(help="Supporting directory; pass an empty string to clear."),
    ] = None,
    related: Annotated[
        list[str] | None,
        typer.Option(
            help="Related post ID; repeat for ordered links. Use --clear-related to clear."
        ),
    ] = None,
    clear_related: bool = False,
    thumbnail: Annotated[
        Path | None, typer.Option(help="Import/replace a listing image.")
    ] = None,
    expected_revision: Revision = None,
):
    """Edit listing fields with flags, or prompt when no flags are supplied."""
    patch = {}
    for key, value in (
        ("title", title),
        ("short_description", description),
        ("code_path", code_path),
    ):
        if value is not None:
            patch[key] = value or None if key == "code_path" else value
    if tags is not None:
        patch["tags"] = tags.split(",") if tags else []
    if related is not None or clear_related:
        patch["related_post_ids"] = related or []
    edit_fields(ctx, identity, "post", patch, expected_revision, thumbnail)


@collection.command("edit")
@guard
def collection_edit(
    ctx: typer.Context,
    identity: Identity,
    title: str | None = None,
    description: str | None = None,
    cover: Path | None = None,
    cover_caption: Annotated[
        str | None,
        typer.Option(
            help="Single-line Markdown caption beneath the cover; empty to clear."
        ),
    ] = None,
    expected_revision: Revision = None,
):
    """Edit card metadata or import a cover image."""
    patch = {
        key: value
        for key, value in (
            ("title", title),
            ("short_description", description),
            ("cover_caption", cover_caption),
        )
        if value is not None
    }
    edit_fields(ctx, identity, "collection", patch, expected_revision, cover)


@resume.command("edit")
@guard
def resume_edit(
    ctx: typer.Context,
    identity: Identity,
    title: str | None = None,
    subtitle: str | None = None,
    section: str | None = None,
    expected_revision: Revision = None,
):
    """Edit a résumé entry's heading, dates or section."""
    patch = {
        key: value
        for key, value in (
            ("title", title),
            ("subtitle", subtitle),
            ("section", section),
        )
        if value is not None
    }
    edit_fields(ctx, identity, "resume", patch, expected_revision)


def write_field(ctx, identity, field, file, expected, kind=None):
    if kind and not identity.startswith(kind + "/"):
        raise ValueError(f"Expected a {kind}/ ID.")
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
    store.check_revision(loaded, expected)
    if field not in loaded["record"]:
        raise ValueError("This record does not support that field.")
    text = read_text(file, loaded["record"][field])
    if text is None:
        return
    try:
        emit(store.update(identity, {field: text.strip("\n")}, loaded["revision"]))
    except (ValueError, OSError, yaml.YAMLError) as error:
        preserve_edit(store, text, error)


@collection.command("open")
@guard
def collection_open(
    ctx: typer.Context,
    identity: Identity,
    file: File = None,
    expected_revision: Revision = None,
):
    """Open an editor for the collection introduction; contents are automatic."""
    write_field(
        ctx, identity, "long_description", file, expected_revision, "collection"
    )


@resume.command("open")
@guard
def resume_open(
    ctx: typer.Context,
    identity: Identity,
    file: File = None,
    expected_revision: Revision = None,
):
    """Open an editor for one entry's Markdown body."""
    write_field(ctx, identity, "body", file, expected_revision, "resume")


@app.command("notes")
@guard
def notes(
    ctx: typer.Context,
    identity: Identity,
    file: File = None,
    expected_revision: Revision = None,
):
    """Edit private scratch notes without changing the public modification date."""
    write_field(ctx, identity, "internal_notes", file, expected_revision)


@post.command("toc")
@guard
def post_toc(
    ctx: typer.Context,
    identity: Identity,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
    depth: Annotated[int, typer.Option(min=1, max=6)] = 3,
    expected_revision: Revision = None,
):
    """Set generated TOC options; headings in the body populate it automatically."""
    if not identity.startswith("post/"):
        raise ValueError("Expected a post/ ID.")
    emit(
        store_for(ctx).update(
            identity, {"toc": enabled, "toc_depth": depth}, expected_revision
        )
    )


def status(ctx, identity, kind, value, expected):
    if not identity.startswith(kind + "/"):
        raise ValueError(f"Expected a {kind}/ ID.")
    emit(store_for(ctx).update(identity, {"status": value}, expected))


@post.command("publish")
@guard
def post_publish(
    ctx: typer.Context, identity: Identity, expected_revision: Revision = None
):
    """Check title, description, image and notebook content, then mark eligible."""
    status(ctx, identity, "post", "published", expected_revision)


@post.command("draft")
@guard
def post_draft(
    ctx: typer.Context, identity: Identity, expected_revision: Revision = None
):
    """Return a post to draft; keep its source and metadata."""
    status(ctx, identity, "post", "draft", expected_revision)


@post.command("rm")
@guard
def post_rm(
    ctx: typer.Context,
    identity: Identity,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    expected_revision: Revision = None,
):
    """Remove a post and its notebook; detach it from collections and related posts."""
    if not identity.startswith("post/"):
        raise ValueError("Expected a post/ ID.")
    if not yes:
        typer.confirm(f"Remove {identity} and its notebook?", abort=True)
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
        store.check_revision(loaded, expected_revision)
        records = {
            kind: [item["record"] for item in store.ls(kind)]
            for kind in ("post", "collection")
        }
        source_path = loaded["record"]["source_path"]
        owners = duplicate_sources(records["post"]).get(source_path)
        if owners:
            raise ValueError(
                "A notebook source path can belong to only one post: "
                f"{source_path} ({', '.join(owners)})."
            )
        changes = {
            store.record_path(identity): None,
            store.path(source_path): None,
        }
        collections = []
        posts = []
        for kind, field in (
            ("collection", "post_ids"),
            ("post", "related_post_ids"),
        ):
            for record in records[kind]:
                if record["id"] == identity or identity not in record[field]:
                    continue
                updated = record | {
                    field: [value for value in record[field] if value != identity],
                    "updated_at": now(),
                }
                changes[store.record_path(record["id"])] = store.record_bytes(updated)
                (collections if kind == "collection" else posts).append(record["id"])
        store.commit(changes)
    emit(
        {
            "removed": identity,
            "detached_collections": collections,
            "detached_posts": posts,
        }
    )


@collection.command("rm")
@guard
def collection_rm(
    ctx: typer.Context,
    identity: Identity,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    expected_revision: Revision = None,
):
    """Remove a collection; member posts and managed images are unchanged."""
    if not identity.startswith("collection/"):
        raise ValueError("Expected a collection/ ID.")
    if not yes:
        typer.confirm(f"Remove {identity}?", abort=True)
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
        store.check_revision(loaded, expected_revision)
        store.commit(
            {
                store.record_path(identity): None,
                store.path(loaded["record"]["source_path"]): None,
            }
        )
    emit({"removed": identity})


@collection.command("publish")
@guard
def collection_publish(
    ctx: typer.Context, identity: Identity, expected_revision: Revision = None
):
    """Require descriptions, cover and a published member. Members are unchanged."""
    status(ctx, identity, "collection", "published", expected_revision)


@collection.command("draft")
@guard
def collection_draft(
    ctx: typer.Context, identity: Identity, expected_revision: Revision = None
):
    """Return a collection to draft without changing its posts."""
    status(ctx, identity, "collection", "draft", expected_revision)


def membership(ctx, identity, post_id, action, position, expected):
    if not identity.startswith("collection/"):
        raise ValueError("Expected a collection/ ID.")
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
    store.check_revision(loaded, expected)
    members = loaded["record"]["post_ids"].copy()
    if action == "add":
        if post_id in members:
            raise ValueError("That post is already a member.")
        position = len(members) if position is None else position
        if not 0 <= position <= len(members):
            raise ValueError("Position is out of range (positions start at zero).")
    elif post_id not in members:
        raise ValueError("That post is not a member.")
    else:
        members.remove(post_id)
        if action == "move" and not 0 <= position <= len(members):
            raise ValueError("Position is out of range (positions start at zero).")
    if action != "remove":
        members.insert(position, post_id)
    emit(store.update(identity, {"post_ids": members}, loaded["revision"]))


@collection.command("add")
@guard
def collection_add(
    ctx: typer.Context,
    identity: Identity,
    post_id: str,
    position: int | None = None,
    expected_revision: Revision = None,
):
    """Append an existing post, or insert it at a zero-based position."""
    membership(ctx, identity, post_id, "add", position, expected_revision)


@collection.command("remove")
@guard
def collection_remove(
    ctx: typer.Context,
    identity: Identity,
    post_id: str,
    expected_revision: Revision = None,
):
    """Remove membership, preserving the post and its notebook."""
    membership(ctx, identity, post_id, "remove", None, expected_revision)


@collection.command("move")
@guard
def collection_move(
    ctx: typer.Context,
    identity: Identity,
    post_id: str,
    position: Annotated[int, typer.Option(min=0)],
    expected_revision: Revision = None,
):
    """Move a member to a zero-based position; regenerate Contents on sync."""
    membership(ctx, identity, post_id, "move", position, expected_revision)


@app.command("todos")
@guard
def todos(
    ctx: typer.Context,
    identity: Identity,
    add: str | None = None,
    text: str | None = None,
    index: int | None = None,
    done: Annotated[bool | None, typer.Option("--done/--undone")] = None,
    remove: bool = False,
    position: int | None = None,
    expected_revision: Revision = None,
):
    """List/add tasks, or edit/check/remove/move --index N (zero-based)."""
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
    store.check_revision(loaded, expected_revision)
    if "internal_todos" not in loaded["record"]:
        raise ValueError("Only posts and collections have internal to-dos.")
    items = [item.copy() for item in loaded["record"]["internal_todos"]]
    if add is not None:
        if any(value is not None for value in (index, text, done, position)) or remove:
            raise ValueError("Use --add alone.")
        items.append({"text": add, "done": False})
    elif index is not None:
        if not 0 <= index < len(items):
            raise ValueError("Task index is out of range (indices start at zero).")
        item = items[index]
        if remove:
            del items[index]
        else:
            if text is not None:
                item["text"] = text
            if done is not None:
                item["done"] = done
            if position is not None:
                if not 0 <= position < len(items):
                    raise ValueError(
                        "Task position is out of range (positions start at zero)."
                    )
                items.pop(index)
                items.insert(position, item)
    elif any(value is not None for value in (text, done, position)) or remove:
        raise ValueError("Select a task with --index N.")
    else:
        emit({"internal_todos": items, "revision": loaded["revision"]})
        return
    emit(store.update(identity, {"internal_todos": items}, loaded["revision"]))


@resume.command("move")
@guard
def resume_move(
    ctx: typer.Context,
    identity: Identity,
    position: Annotated[int, typer.Option(min=0)],
    expected_revision: Revision = None,
):
    """Move an entry within its section (zero-based display position)."""
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
        store.check_revision(loaded, expected_revision)
        section = loaded["record"].get("section")
        if section is None:
            raise ValueError("Expected a resume/ ID.")
        entries = [
            item["record"]
            for item in store.ls("resume")
            if item["record"]["section"] == section
        ]
        if not 0 <= position < len(entries):
            raise ValueError("Position is out of range.")
        entries = [entry for entry in entries if entry["id"] != identity]
        entries.insert(position, loaded["record"])
        changes = {}
        for index, entry in enumerate(entries):
            if entry["position"] != index:
                entry.update(position=index, updated_at=now())
                changes[store.record_path(entry["id"])] = store.record_bytes(entry)
        store.commit(changes)
        emit(store.get(identity))


@resume.command("rm")
@guard
def resume_rm(
    ctx: typer.Context,
    identity: Identity,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    expected_revision: Revision = None,
):
    """Remove one résumé entry. Other entries and the PDF remain intact."""
    if not identity.startswith("resume/"):
        raise ValueError("Expected a resume/ ID.")
    if not yes:
        typer.confirm(f"Remove {identity}?", abort=True)
    store = store_for(ctx)
    with store.lock():
        loaded = store.get(identity)
        store.check_revision(loaded, expected_revision)
        changes = {
            store.record_path(identity): None,
            store.path(loaded["record"]["source_path"]): None,
        }
        entries = [
            item["record"]
            for item in store.ls("resume")
            if item["record"]["section"] == loaded["record"]["section"]
            and item["record"]["id"] != identity
        ]
        for position, entry in enumerate(entries):
            if entry["position"] != position:
                entry.update(position=position, updated_at=now())
                changes[store.record_path(entry["id"])] = store.record_bytes(entry)
        store.commit(changes)
    emit({"removed": identity})


@resume.command("profile")
@guard
def resume_profile(
    ctx: typer.Context,
    title: str | None = None,
    summary: str | None = None,
    expected_revision: Revision = None,
):
    """Read or update the résumé page title and opening summary."""
    store = store_for(ctx)
    with store.lock():
        store.require_initialized()
        path = store.path("content/resume.yaml")
        raw = path.read_bytes()
        store.check_revision({"revision": digest(raw)}, expected_revision)
        profile = decode(raw)
        if title is not None:
            if not title.strip():
                raise ValueError("Title cannot be blank.")
            profile["title"] = title
        if summary is not None:
            profile["summary"] = summary
        if title is not None or summary is not None:
            store.commit({path: encode(profile)})
        emit({"profile": profile, "revision": digest(path.read_bytes())})


@app.command("check")
@guard
def check(ctx: typer.Context):
    """Validate records/references and report publication blockers without writing."""
    store = store_for(ctx)
    diagnostics = []
    with store.lock():
        records = {
            kind: [item["record"] for item in store.ls(kind)]
            for kind in ("post", "collection", "resume")
        }
        shared = duplicate_sources(records["post"])
        posts_by_id = {record["id"]: record for record in records["post"]}
        for path, identities in shared.items():
            for identity in identities:
                record = posts_by_id[identity]
                diagnostics.append(
                    {
                        "id": identity,
                        "status": record.get("status"),
                        "message": (
                            "A notebook source path can belong to only one post: "
                            f"{path} ({', '.join(identities)})."
                        ),
                    }
                )
        for kind, items in records.items():
            for record in items:
                try:
                    store.references(record)
                    if kind != "resume":
                        store.ready(record)
                except (ValueError, OSError) as error:
                    diagnostics.append(
                        {
                            "id": record["id"],
                            "status": record.get("status"),
                            "message": str(error),
                        }
                    )
    emit({"diagnostics": diagnostics})
    if diagnostics:
        raise typer.Exit(1)


@app.command("sync")
@guard
def sync(ctx: typer.Context, preview: bool = False):
    """Sync ignored frontend copies with public metadata. --preview includes drafts."""
    emit(generate(store_for(ctx), preview))


def render_resume_pdf(store: Store, executable: str):
    """Replace the download only after an isolated PDF render succeeds."""
    with tempfile.TemporaryDirectory(
        prefix="resume-pdf-", dir=store.path(".atlas/cms")
    ) as directory:
        source = Path(directory) / "resume.qmd"
        shutil.copyfile(store.path(".atlas/cms/resume.qmd"), source)
        status = subprocess.call(
            [executable, "render", str(source), "--to", "typst", "--no-execute"],
            cwd=directory,
        )
        if status:
            raise typer.Exit(status)
        pdf = source.with_suffix(".pdf").read_bytes()
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("Quarto did not generate a résumé PDF.")
        with store.lock():
            store.commit({store.path("frontend/assets/resume.pdf"): pdf})


def run_quarto(ctx, preview, port=4200):
    executable = shutil.which(os.environ.get("QUARTO", "quarto"))
    if executable is None:
        raise ValueError("Install Quarto, then run this command again.")
    store = store_for(ctx)
    result = generate(store, preview)
    render_resume_pdf(store, executable)
    command = [executable, "preview" if preview else "render", result["site"]]
    if preview:
        command += ["--profile", "preview", "--port", str(port), "--render", "all"]
    command += ["--no-execute"]
    raise typer.Exit(subprocess.call(command, cwd=store.root))


@app.command("build")
@guard
def build(ctx: typer.Context):
    """Generate and render published content locally without executing notebooks."""
    run_quarto(ctx, False)


@app.command("preview")
@guard
def preview(
    ctx: typer.Context, port: Annotated[int, typer.Option(min=1, max=65535)] = 4200
):
    """Generate drafts and start Quarto preview; run again after CMS edits."""
    run_quarto(ctx, True, port)
