"""A terminal CMS over the documented Atlas authoring model."""

import fcntl
import functools
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml
from PIL import Image
from rich.console import Console
from rich.table import Table

from atlas.cms_secrets import verify_repository, verify_workspace
from atlas.cms_site import (
    file_stamp,
    generate,
    initialize,
    prune_source_output,
    verify_pages_artifact,
)
from atlas.cms_source import source_files
from atlas.cms_store import (
    Ambiguous,
    Conflict,
    NotFound,
    Store,
    decode,
    digest,
    duplicate_sources,
    encode,
    normalized_tags,
    now,
    url_path,
)
from atlas.config import ROOT_PATH

app = typer.Typer(
    no_args_is_help=True, help="Create and edit posts, collections and résumé entries."
)
post = typer.Typer(
    no_args_is_help=True,
    help="Notebook posts. Edit title, short_description and tags directly in content/posts/<id>.yaml or with edit.",
)
collection = typer.Typer(
    no_args_is_help=True,
    help="Collections and ordered contents. Edit metadata in content/collections/<id>.yaml and introductions in <id>.md.",
)
resume = typer.Typer(
    no_args_is_help=True, help="Résumé profile and ordered YAML entries."
)
app.add_typer(post, name="post")
app.add_typer(collection, name="collection")
app.add_typer(resume, name="resume")
Identity = Annotated[
    str,
    typer.Argument(help="Exact ID from new or ls. Resolve a prefix with `at cms id`."),
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
            payload = (
                {
                    "error": f"Multiple matches for {error.query!r}.",
                    "matches": error.matches,
                }
                if isinstance(error, Ambiguous)
                else {"error": str(error)}
            )
            typer.echo(json.dumps(payload, ensure_ascii=False), err=True)
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


@app.command("id")
@guard
def id(ctx: typer.Context, query: str):
    """Resolve an exact ID or unique prefix for piping into commands.

    A bare 'query' matches post/query*, collection/query*, and resume/query*.
    Use 'post/query' to search only post IDs.

    Existing exact IDs are returned directly. Multiple prefix matches fail and
    list the matching IDs.
    """
    store = store_for(ctx)
    with store.lock():
        identity = store.resolve(query)
    typer.echo(identity)


@app.command("open")
@guard
def open_sources(ctx: typer.Context, identity: Identity):
    """Open a post's notebook or a collection's Markdown, plus its YAML, in VS Code.

    Requires `code` on PATH.
    """
    if not identity.startswith(("post/", "collection/")):
        raise ValueError("Expected a post/ or collection/ ID.")
    store = store_for(ctx)
    with store.lock():
        record = store.get(identity)["record"]
        source = store.path(record["source_path"])
        if not source.is_file():
            raise NotFound(f"Source file not found: {record['source_path']}")
        metadata, _ = store.content_source(record)
    executable = shutil.which("code")
    if executable is None:
        raise ValueError("Install the VS Code 'code' command on PATH, then try again.")
    raise typer.Exit(subprocess.call([executable, str(source), str(metadata)]))


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
    """Initialize/import a workspace, or upgrade post YAML and collection Markdown storage."""
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
        loaded = store.get(identity)
    if kind in ("post", "collection"):
        loaded["url_path"] = url_path(identity)
    emit(loaded)


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
    """Create a draft with an empty notebook and metadata YAML, then refresh preview."""
    store = store_for(ctx)
    created = store.new(
        "post",
        title,
        short_description=description,
        tags=normalized_tags(tags.split(",")) if tags else [],
    )
    emit_created(store, created)


@collection.command("new")
@guard
def collection_new(ctx: typer.Context, title: str, description: str = ""):
    """Create a draft with an empty introduction and metadata YAML, then refresh preview."""
    store = store_for(ctx)
    created = store.new("collection", title, short_description=description)
    emit_created(store, created)


def emit_created(store: Store, created: dict):
    emit(created)
    try:
        render_site(store, preview=True)
    except (ValueError, OSError, yaml.YAMLError, typer.Exit) as error:
        reason = (
            f"Quarto exited with status {error.exit_code}"
            if isinstance(error, typer.Exit)
            else str(error)
        )
        identity = created["record"]["id"]
        typer.echo(
            f"Created {identity}. Preview refresh failed: {reason}\n"
            "Retry the preview with 'uv run at cms build --preview'.",
            err=True,
        )


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
        typer.Option(
            help="Supporting directory relative to the workspace root. The browser uses eligible files from Git HEAD. Pass an empty string to clear."
        ),
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
    """Edit listing fields with flags, or prompt when no flags are supplied.

    Title, short_description and tags live in content/posts/<id>.yaml and can
    also be edited there directly. YAML tags are a list; --tags is comma-separated.
    """
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
    """Edit content/collections/<id>.md; contents are automatic.

    Edit this Markdown file directly in your editor, or use --file for file/stdin
    input. Title, short_description and optional cover_caption stay in <id>.yaml.
    """
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


def status(ctx, identity, kind, value, expected):
    if not identity.startswith(kind + "/"):
        raise ValueError(f"Expected a {kind}/ ID.")
    emit(store_for(ctx).update(identity, {"status": value}, expected))


@post.command("publish")
@guard
def post_publish(
    ctx: typer.Context, identity: Identity, expected_revision: Revision = None
):
    """Require a title, description and notebook content. Thumbnails are optional."""
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
    """Remove a post, notebook and metadata YAML; detach collection/related links."""
    if not identity.startswith("post/"):
        raise ValueError("Expected a post/ ID.")
    if not yes:
        typer.confirm(f"Remove {identity}, its notebook and metadata YAML?", abort=True)
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
            store.content_source(loaded["record"])[0]: None,
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
    """Remove a collection, its metadata YAML and introduction Markdown; keep member posts/images."""
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
                store.content_source(loaded["record"])[0]: None,
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
    """Validate records, list omitted companion files, and report publication blockers."""
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
        browsable = []
        for kind, items in records.items():
            for record in items:
                try:
                    store.references(record)
                    if kind == "post" and record["code_path"] is not None:
                        browsable.append(record)
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
        try:
            source_files(store, browsable)
        except (ValueError, OSError) as error:
            detail = (
                "Companion source inputs could not be read."
                if isinstance(error, OSError)
                else str(error)
            )
            diagnostics.extend(
                {
                    "id": record["id"],
                    "status": record["status"],
                    "message": f"Companion source unavailable. {detail}",
                }
                for record in browsable
            )
    emit({"diagnostics": diagnostics})
    if diagnostics:
        raise typer.Exit(1)


@app.command("sync")
@guard
def sync(ctx: typer.Context, preview: bool = False):
    """Sync ignored frontend copies with public metadata. --preview includes drafts."""
    store = store_for(ctx)
    with site_lock(store, "render"):
        emit(generate(store, preview))


@contextmanager
def site_lock(store: Store, name: str, *, wait: bool = True):
    """Coordinate site operations independently of the content writer."""
    path = store.path(f".atlas/cms/{name}.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            fcntl.flock(
                handle, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except BlockingIOError:
            yield False
        else:
            yield True


def quarto_executable() -> str:
    executable = shutil.which(os.environ.get("QUARTO", "quarto"))
    if executable is None:
        raise ValueError("Install Quarto to render the site.")
    return executable


def preview_options(store: Store) -> list[str]:
    if not store.path("frontend/_quarto-preview.yml").is_file():
        raise ValueError("Missing frontend/_quarto-preview.yml.")
    return ["--profile", "preview", "--output-dir", "_site-preview"]


def render_resume_pdf(store: Store, executable: str):
    """Reuse an unchanged PDF; replace it only after an isolated render succeeds."""
    with tempfile.TemporaryDirectory(
        prefix="resume-pdf-", dir=store.path(".atlas/cms")
    ) as directory:
        source = Path(directory) / "resume.qmd"
        shutil.copyfile(store.path(".atlas/cms/resume.qmd"), source)
        for resource in ("_cms/resume-pdf", "assets/fonts"):
            origin = store.path("frontend/" + resource)
            if origin.is_dir():
                shutil.copytree(origin, source.parent / resource)
        renderer = Path(executable)
        inputs = {
            "renderer": str(renderer.resolve()),
            "renderer_mtime": (
                renderer.stat().st_mtime_ns if renderer.exists() else None
            ),
            "files": {
                path.relative_to(source.parent).as_posix(): digest(path.read_bytes())
                for path in sorted(source.parent.rglob("*"))
                if path.is_file()
            },
        }
        input_digest = digest(json.dumps(inputs, sort_keys=True).encode())
        target = store.path("frontend/assets/resume.pdf")
        cache = store.path(".atlas/cms/resume-pdf.cache.yaml")
        if target.exists() and cache.exists():
            expected = encode(
                {"inputs": input_digest, "pdf": digest(target.read_bytes())}
            )
            if cache.read_bytes() == expected:
                return
        status = subprocess.call(
            [executable, "render", str(source), "--to", "typst", "--no-execute"],
            cwd=directory,
            stdout=sys.stderr,
        )
        if status:
            raise typer.Exit(status)
        pdf = source.with_suffix(".pdf").read_bytes()
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("Quarto did not generate a résumé PDF.")
        with store.lock():
            store.commit(
                {
                    target: pdf,
                    cache: encode({"inputs": input_digest, "pdf": digest(pdf)}),
                }
            )


def prepare_site(
    store: Store,
    executable: str,
    preview: bool,
    *,
    watch_snapshot: dict | None = None,
    source_browser: bool = True,
    require_source_browser: bool = False,
) -> dict:
    result = generate(
        store,
        preview,
        watch_snapshot=watch_snapshot,
        source_browser=source_browser,
        require_source_browser=require_source_browser,
    )
    if preview:
        prune_preview_output(store)
    render_resume_pdf(store, executable)
    return result


def prune_preview_output(store: Store):
    """An incremental render won't necessarily remove pages with no input."""
    frontend = store.path("frontend")
    output = store.path("frontend/_site-preview")
    for pattern in ("posts/*.html", "collections/*.html"):
        for rendered in output.glob(pattern):
            if not rendered.is_file():
                continue
            source = frontend / rendered.relative_to(output)
            if not source.is_file() and not any(
                source.with_suffix(extension).is_file()
                for extension in (".qmd", ".ipynb")
            ):
                store.path(rendered.relative_to(store.root).as_posix()).unlink(
                    missing_ok=True
                )


def render_site(store: Store, preview: bool, *, for_pages: bool = False):
    if preview and for_pages:
        raise ValueError("--for-pages requires a public build.")
    with site_lock(store, "render"):
        if preview:
            with site_lock(store, "live-preview", wait=False) as idle:
                if not idle:
                    # The live preview watches the source files created by the CMS.
                    return
        options = preview_options(store) if preview else []
        if for_pages:
            verify_repository(store.root)
            options = ["--output-dir", "_site"]
        executable = quarto_executable()
        result = prepare_site(
            store, executable, preview, require_source_browser=for_pages
        )
        command = [executable, "render", result["site"], "--no-execute", *options]
        status = subprocess.call(command, cwd=store.root, stdout=sys.stderr)
        if status:
            raise typer.Exit(status)
        if for_pages:
            verify_pages_artifact(store)


def preview_snapshot(store: Store) -> dict:
    """Track authored inputs, not generated output or editor checkpoint files."""
    snapshot = {}
    ignore_file = store.root / ".gitignore"
    try:
        if not ignore_file.is_symlink() and ignore_file.is_file():
            snapshot[".gitignore"] = file_stamp(ignore_file)
    except FileNotFoundError:
        pass  # An editor may have replaced it between the stat calls.
    for directory in (
        "content",
        "backend",
        "frontend/_cms",
        "frontend/assets/fonts",
    ):
        root = store.path(directory)
        for path in root.rglob("*"):
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
                continue
            try:
                if path.is_file():
                    snapshot[path.relative_to(store.root).as_posix()] = file_stamp(path)
            except FileNotFoundError:
                # Atomic editor saves can replace a file while scanning.
                continue
    return snapshot


def preview_pages(snapshot: dict) -> set[str]:
    return {
        path
        for path in snapshot
        if path.startswith(("backend/posts/", "backend/collections/"))
        and path.endswith(".yaml")
        and path.count("/") == 2
    }


def preview_source_pages(store: Store) -> dict[Path, tuple[int, int, int]]:
    pages = {}
    for path in store.path("frontend/posts").glob("*/source/**/*.qmd"):
        with suppress(FileNotFoundError):
            pages[path] = file_stamp(path)
    return pages


def watch_preview(
    store: Store,
    executable: str,
    process,
    previous: dict | None = None,
    *,
    source_browser: bool = True,
) -> dict | None:
    """Sync source changes and return the latest snapshot if Quarto must restart."""
    if previous is None:
        previous = preview_snapshot(store)
    pages = preview_pages(previous)
    source_pages = preview_source_pages(store)
    changed_at = None
    typer.echo("Watching content/ and backend/ for CMS changes.")
    while process.poll() is None:
        time.sleep(0.25)
        current = preview_snapshot(store)
        if current != previous:
            previous = current
            changed_at = time.monotonic()
        if changed_at is None or time.monotonic() - changed_at < 0.5:
            continue
        changed_at = None
        synced = False
        try:
            with site_lock(store, "render"):
                prepare_site(
                    store,
                    executable,
                    preview=True,
                    watch_snapshot=previous,
                    source_browser=source_browser,
                )
            synced = True
        except (ValueError, OSError, yaml.YAMLError, typer.Exit) as error:
            # A half-written or invalid save must not kill the preview server.
            typer.echo(
                f"Preview sync failed: {error}. Fix the source and save again.",
                err=True,
            )
        if preview_source_pages(store) != source_pages or (
            synced and preview_pages(previous) != pages
        ):
            return previous
        if synced:
            typer.echo("Preview content synced.")
    return None


@app.command("scan-secrets")
@guard
def scan_secrets(
    ctx: typer.Context,
    staged: Annotated[
        bool,
        typer.Option(
            "--staged", help="Scan only the full Git index (the next commit)."
        ),
    ] = False,
    workspace: Annotated[
        bool,
        typer.Option(
            "--workspace",
            help=(
                "Scan local files, including Git-ignored files, but skip .env files, "
                ".venv directories, and symlinks with either name at any depth. "
                "Git-visible scans do not use these exclusions."
            ),
        ),
    ] = False,
):
    """Scan Git-visible files, or audit the local workspace with --workspace."""
    if workspace and staged:
        raise ValueError("--workspace and --staged cannot be combined.")
    root = store_for(ctx).root
    if workspace:
        verify_workspace(root)
        typer.echo("Workspace secret scan passed.")
        return
    verify_repository(root, staged=staged)
    typer.echo("Repository secret scan passed.")


@app.command("build")
@guard
def build(
    ctx: typer.Context,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview", help="Include drafts and render to frontend/_site-preview/."
        ),
    ] = False,
    for_pages: Annotated[
        bool,
        typer.Option(
            "--for-pages",
            help="Scan repository inputs before rendering and verify the public Pages output.",
        ),
    ] = False,
):
    """Sync and render the site once without executing notebooks."""
    render_site(store_for(ctx), preview, for_pages=for_pages)


@app.command("preview")
@guard
def preview(
    ctx: typer.Context,
    port: Annotated[int, typer.Option(min=1, max=65535)] = 4200,
    source_browser: Annotated[
        bool,
        typer.Option(
            "--source-browser/--no-source-browser",
            help="Skip the project source browser for a quicker preview.",
        ),
    ] = True,
):
    """Preview drafts and watch content/backend edits; sync changed files without executing code."""
    store = store_for(ctx)
    executable = quarto_executable()
    options = [
        *preview_options(store),
        "--port",
        str(port),
        "--render",
        "none",
        "--no-execute",
    ]
    with site_lock(store, "live-preview", wait=False) as available:
        if not available:
            raise ValueError("A live preview is already running in this workspace.")
        with site_lock(store, "render"):
            # Watch for creations made while Quarto is starting.
            previous = preview_snapshot(store)
            result = prepare_site(
                store,
                executable,
                preview=True,
                watch_snapshot=previous,
                source_browser=source_browser,
            )
        while True:
            source_pages = preview_source_pages(store)
            process = subprocess.Popen(
                [executable, "preview", result["site"], *options],
                cwd=store.root,
                start_new_session=True,
            )
            try:
                previous = watch_preview(
                    store, executable, process, previous, source_browser=source_browser
                )
            finally:
                stop_preview(process)
            if previous is None:
                raise typer.Exit(process.returncode)
            # The stopped preview might have finished writing an old view
            # while sync updated its projection.
            with site_lock(store, "render"):
                invalidated = {
                    path
                    for path, stamp in preview_source_pages(store).items()
                    if source_pages.get(path) != stamp
                }
                prune_source_output(store, preview_only=True, invalidated=invalidated)
            typer.echo("Refreshing live preview for changed pages.")
            if "--no-browser" not in options:
                options.append("--no-browser")


def stop_preview(process):
    # The Quarto launcher starts a child server that also needs to release the port.
    if process.poll() is None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
