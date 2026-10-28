"""The standalone ``at notebook`` command suite."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from atlas import cms_notebooks as nb
from atlas.cms import edit_text, emit, guard, preserve_edit
from atlas.cms_store import Store
from atlas.config import ROOT_PATH

app = typer.Typer(
    no_args_is_help=True,
    help="Navigate and edit cells, outputs and execution for post notebooks.",
)
Revision = Annotated[
    str | None,
    typer.Option(
        "--expected-revision",
        help="Notebook token from `at notebook cat --with-revision`.",
    ),
]
File = Annotated[
    Path | None,
    typer.Option("--file", "-f", help="Read source from a file, or '-' for stdin."),
]


@app.callback()
def configure(
    ctx: typer.Context,
    root: Annotated[Path, typer.Option(help="Atlas workspace root.")] = ROOT_PATH,
):
    ctx.obj = {"store": Store(root)}


def source_input(
    content: str | None, file: Path | None, initial: str, extension: str
) -> str:
    if content is not None and file is not None:
        raise ValueError("Use only one of --content or --file.")
    if content is not None:
        return content
    if file is not None:
        return sys.stdin.read() if str(file) == "-" else file.read_text()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    edited = edit_text(initial, extension)
    return initial if edited is None else edited


def save_source(store: Store, source: str, operation):
    try:
        result = operation()
    except (ValueError, OSError, yaml.YAMLError) as error:
        preserve_edit(store, source, error)
    emit(result)


@app.command("map")
@guard
def notebook_map(ctx: typer.Context):
    """List registered post notebooks with their ID, title and cell count."""
    store: Store = ctx.obj["store"]
    table = Table("ID", "Status", "Cells", "Source", "Title")
    with store.lock():
        for item in store.ls("post"):
            record = item["record"]
            path = store.path(record["source_path"])
            if path.is_file():
                from atlas.cms_notebooks import load

                count = len(load(path.read_bytes())["cells"])
            else:
                count = "missing"
            table.add_row(
                record["id"],
                record["status"],
                str(count),
                record["source_path"],
                record["title"],
            )
    Console().print(table)


@app.command("find")
@guard
def notebook_find(ctx: typer.Context, query: str):
    """Search cell source across registered post notebooks."""
    from atlas.notebook_ops import find

    matches = find(ctx.obj["store"], query)
    typer.echo("\n".join(matches) if matches else "No matches.")


@app.command("count")
@guard
def notebook_count(ctx: typer.Context, name: str):
    """Print the number of cells in a post notebook."""
    from atlas.notebook_ops import load

    with ctx.obj["store"].lock():
        item = load(ctx.obj["store"], name)
    typer.echo(
        f"{item['record']['id']}: {len(item['notebook']['cells'])} cells ({item['token']})"
    )


@app.command("cat")
@guard
def notebook_cat(
    ctx: typer.Context,
    name: str,
    index: Annotated[
        str | None,
        typer.Option(
            "--index",
            "-i",
            help="0-based cell index or Python-style range, such as 2:5 or -1.",
        ),
    ] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    label: Annotated[
        str | None,
        typer.Option("--label", "-l", help="Quarto cell label or Markdown figure ID."),
    ] = None,
    offset: Annotated[int, typer.Option(min=0)] = 0,
    limit: Annotated[
        int, typer.Option(min=0, help="Characters per cell; 0 shows all.")
    ] = 4096,
    with_outputs: bool = False,
    out_offset: Annotated[int, typer.Option(min=0)] = 0,
    out_limit: Annotated[int | None, typer.Option(min=0)] = None,
    context: Annotated[
        int,
        typer.Option(
            "--context",
            "-C",
            min=0,
            help="Include neighboring cells around a selection.",
        ),
    ] = 0,
    with_revision: bool = False,
):
    """Read cell source as clean Markdown, without notebook JSON."""
    from atlas.notebook_ops import cat

    typer.echo(
        cat(
            ctx.obj["store"],
            name,
            index=index,
            tag=tag,
            cell_label=label,
            offset=offset,
            limit=limit,
            with_outputs=with_outputs,
            out_offset=out_offset,
            out_limit=out_limit,
            context=context,
            with_revision=with_revision,
        )
    )


@app.command("edit-cell")
@guard
def notebook_edit_cell(
    ctx: typer.Context,
    name: str,
    index: Annotated[
        int | None, typer.Option("--index", "-i", help="0-based cell index.")
    ] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    label: Annotated[str | None, typer.Option("--label", "-l")] = None,
    content: Annotated[str | None, typer.Option("--content", "-c")] = None,
    file: File = None,
    expected_revision: Revision = None,
):
    """Edit one cell by index/tag/label while preserving its outputs and metadata."""
    from atlas.notebook_ops import load, set_source, unique_index, update

    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    cell_index = unique_index(
        loaded["notebook"], index=index, tag=tag, cell_label=label
    )
    cell = loaded["notebook"]["cells"][cell_index]
    source = source_input(
        content,
        file,
        nb.source(cell),
        ".py" if cell["cell_type"] == "code" else ".md",
    )
    save_source(
        store,
        source,
        lambda: update(
            store,
            name,
            loaded["token"],
            lambda notebook: set_source(notebook, cell_index, source),
        ),
    )


@app.command("append-cell")
@guard
def notebook_append_cell(
    ctx: typer.Context,
    name: str,
    cell_type: Annotated[str, typer.Option("--type", "-t", help="md or code.")] = "md",
    content: Annotated[str | None, typer.Option("--content", "-c")] = None,
    file: File = None,
    expected_revision: Revision = None,
):
    """Append an empty or authored Markdown/code cell."""
    from atlas.notebook_ops import append, load, update

    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    source = source_input(content, file, "", ".py" if cell_type == "code" else ".md")
    save_source(
        store,
        source,
        lambda: update(
            store,
            name,
            loaded["token"],
            lambda notebook: append(notebook, source, cell_type),
        ),
    )


@app.command("insert-cell")
@guard
def notebook_insert_cell(
    ctx: typer.Context,
    name: str,
    after: Annotated[int | None, typer.Option("--after", "-a", min=0)] = None,
    before: Annotated[int | None, typer.Option("--before", "-b", min=0)] = None,
    tag: str | None = None,
    label: str | None = None,
    cell_type: Annotated[str, typer.Option("--type", "-t")] = "md",
    content: Annotated[str | None, typer.Option("--content", "-c")] = None,
    file: File = None,
    expected_revision: Revision = None,
):
    """Insert a cell before/after an index, or after a unique tag/label."""
    from atlas.notebook_ops import load, new_cell, unique_index, update

    if sum(value is not None for value in (after, before, tag, label)) != 1:
        raise ValueError("Use exactly one of --after, --before, --tag or --label.")
    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    source = source_input(content, file, "", ".py" if cell_type == "code" else ".md")

    def operation(notebook):
        if after is not None:
            position = after + 1
        elif before is not None:
            position = before
        else:
            position = unique_index(notebook, index=None, tag=tag, cell_label=label) + 1
        if not 0 <= position <= len(notebook["cells"]):
            raise ValueError("Insert position is out of range.")
        notebook["cells"].insert(position, new_cell(source, cell_type))

    save_source(store, source, lambda: update(store, name, loaded["token"], operation))


@app.command("figure")
@guard
def notebook_figure(
    ctx: typer.Context,
    name: str,
    image: Annotated[
        Path, typer.Argument(help="Image to copy, such as ~/Desktop/plot.png.")
    ],
    index: Annotated[
        int | None,
        typer.Option(
            "--index",
            "-i",
            min=0,
            help="Zero-based insertion position, or existing figure cell with --replace.",
        ),
    ] = None,
    caption: Annotated[
        str, typer.Option(help="Optional plain text figure caption.")
    ] = "",
    alt: Annotated[
        str | None, typer.Option(help="Optional accessible image description.")
    ] = None,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help="Replace an existing figure's image, preserving its caption and attributes.",
        ),
    ] = False,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            "-l",
            help="With --replace, select this figure ID instead of --index.",
        ),
    ] = None,
    expected_revision: Revision = None,
):
    """Copy an image and insert a Quarto figure, or replace an existing image."""
    from atlas.notebook_ops import figure, replace_figure

    if replace:
        if caption or alt is not None:
            raise ValueError(
                "Use --replace without --caption or --alt to keep existing figure text."
            )
        emit(
            replace_figure(
                ctx.obj["store"],
                name,
                image,
                index=index,
                cell_label=label,
                expected_revision=expected_revision,
            )
        )
        return
    if label is not None:
        raise ValueError("Use --label with --replace to select an existing figure.")

    emit(
        figure(
            ctx.obj["store"],
            name,
            image,
            index=index,
            caption=caption,
            alt=alt,
            expected_revision=expected_revision,
        )
    )


@app.command("remove-cell")
@guard
def notebook_remove_cell(
    ctx: typer.Context,
    name: str,
    index: Annotated[int | None, typer.Option("--index", "-i", min=0)] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    label: Annotated[str | None, typer.Option("--label", "-l")] = None,
    expected_revision: Revision = None,
):
    """Remove one indexed/labeled cell or all cells with a tag."""
    from atlas.notebook_ops import indices, load, unique_index, update

    if sum(value is not None for value in (index, tag, label)) != 1:
        raise ValueError("Pass exactly one of --index, --tag or --label.")

    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    matched = indices(loaded["notebook"], index=index, tag=tag, cell_label=label)
    if label is not None:
        matched = [
            unique_index(loaded["notebook"], index=None, tag=None, cell_label=label)
        ]
    if not matched:
        raise ValueError("No notebook cells matched that locator.")
    emit(
        update(
            store,
            name,
            loaded["token"],
            lambda notebook: [notebook["cells"].pop(i) for i in reversed(matched)],
        )
    )


@app.command("clear-outputs")
@guard
def notebook_clear_outputs(
    ctx: typer.Context,
    name: str,
    index: Annotated[int | None, typer.Option("--index", "-i", min=0)] = None,
    tag: str | None = None,
    label: str | None = None,
    from_index: Annotated[int | None, typer.Option("--from", "-f", min=0)] = None,
    expected_revision: Revision = None,
):
    """Clear stored code outputs by locator, from an index, or for all code cells."""
    from atlas.notebook_ops import load, update

    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    if from_index is not None:
        if any(value is not None for value in (index, tag, label)):
            raise ValueError("Use --from alone.")
        if from_index >= len(loaded["notebook"]["cells"]):
            raise ValueError("Start index is out of range.")
        matched = list(range(from_index, len(loaded["notebook"]["cells"])))
    elif any(value is not None for value in (index, tag, label)):
        from atlas.notebook_ops import indices

        matched = indices(loaded["notebook"], index=index, tag=tag, cell_label=label)
    else:
        matched = list(range(len(loaded["notebook"]["cells"])))
    targets = [
        i for i in matched if loaded["notebook"]["cells"][i]["cell_type"] == "code"
    ]
    if not targets:
        raise ValueError("No code cells matched that locator.")

    def operation(notebook):
        for i in targets:
            notebook["cells"][i]["outputs"] = []

    emit(update(store, name, loaded["token"], operation))


@app.command("tag")
@guard
def notebook_tag(
    ctx: typer.Context,
    name: str,
    index: Annotated[int | None, typer.Option("--index", "-i", min=0)] = None,
    match_tag: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Locate an existing tag; must be unique."),
    ] = None,
    label: Annotated[str | None, typer.Option("--label", "-l")] = None,
    add: Annotated[list[str] | None, typer.Option("--add", "-a")] = None,
    remove: Annotated[list[str] | None, typer.Option("--remove", "-r")] = None,
    expected_revision: Revision = None,
):
    """Read or update tags on one cell."""
    from atlas.notebook_ops import load, tags, unique_index, update

    store = ctx.obj["store"]
    with store.lock():
        loaded = load(store, name, expected_revision)
    cell_index = unique_index(
        loaded["notebook"], index=index, tag=match_tag, cell_label=label
    )
    if not add and not remove:
        typer.echo(
            json.dumps(
                tags(loaded["notebook"]["cells"][cell_index]), ensure_ascii=False
            )
        )
        return

    def operation(notebook):
        cell = notebook["cells"][cell_index]
        current = set(tags(cell))
        current.difference_update(remove or [])
        current.update(add or [])
        cell.setdefault("metadata", {})["tags"] = sorted(current)

    emit(update(store, name, loaded["token"], operation))


@app.command("output")
@guard
def notebook_output(
    ctx: typer.Context,
    name: str,
    index: Annotated[int, typer.Option("--index", "-i", min=0)],
    output: Annotated[int | None, typer.Option("--output", "-o", min=0)] = None,
):
    """Inspect stored output text and extract images under .atlas/cms/notebook-output."""
    from atlas.notebook_ops import output_images

    text, paths = output_images(ctx.obj["store"], name, index, output)
    typer.echo("\n\n".join(text))
    for path in paths:
        typer.echo(f"Saved image: {path}")


@app.command("run")
@guard
def notebook_run(
    ctx: typer.Context,
    name: str,
    index: Annotated[int | None, typer.Option("--index", "-i", min=0)] = None,
    kernel: Annotated[str | None, typer.Option("--kernel", "-k")] = None,
    timeout: Annotated[int, typer.Option("--timeout", min=1)] = 300,
    expected_revision: Revision = None,
):
    """Explicitly execute notebook code cells and save their outputs."""
    from atlas.notebook_ops import run

    result = run(
        ctx.obj["store"],
        name,
        index=index,
        kernel=kernel,
        timeout=timeout,
        expected_revision=expected_revision,
    )
    emit(result)
    if result["errors"]:
        raise typer.Exit(1)


@app.command("diff")
@guard
def notebook_diff(
    ctx: typer.Context,
    name: str,
    base: Annotated[str, typer.Option("--base", "-b")] = "HEAD",
):
    """Show a source-only diff against a Git ref, without cell output JSON."""
    from atlas.notebook_ops import diff

    result = diff(ctx.obj["store"], name, base)
    if result:
        typer.echo(result, nl=False)


@app.command("kernels")
@guard
def notebook_kernels():
    """List Jupyter kernels available to `at notebook run`."""
    from atlas.notebook_ops import list_kernels

    table = Table("Name", "Display name")
    for item in list_kernels():
        table.add_row(item["name"], item["display_name"])
    Console().print(table)
