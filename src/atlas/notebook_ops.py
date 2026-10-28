"""Safe inspection and revision-checked operations for registered post notebooks."""

from __future__ import annotations

import base64
import copy
import difflib
import json
import os
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import yaml

from atlas import cms_notebooks as nb
from atlas.cms_store import Conflict, NotFound, Store, digest

MAX_SOURCE_CHARS = 20_000
DEFAULT_SOURCE_LIMIT = 4096


def resolve(store: Store, name: str) -> dict:
    """Resolve a post ID, source path, notebook stem or unique title."""
    records = [item["record"] for item in store.ls("post")]
    exact = [
        record
        for record in records
        if name
        in (record["id"], record["source_path"], Path(record["source_path"]).name)
    ]
    if not exact:
        exact = [
            record
            for record in records
            if name in (record["id"].split("/", 1)[1], Path(record["source_path"]).stem)
        ]
    if not exact:
        exact = [
            record
            for record in records
            if record["title"].casefold() == name.casefold()
        ]
    if len(exact) > 1:
        raise ValueError(f"Ambiguous notebook name {name!r}; use its post ID.")
    if not exact:
        raise NotFound(f"No post notebook named {name!r}.")
    return exact[0]


def load(store: Store, name: str, expected_revision: str | None = None) -> dict:
    """Read a post, its exact notebook bytes and the notebook revision token."""
    store.require_initialized()
    record = resolve(store, name)
    loaded = store.get(record["id"])
    path = store.path(record["source_path"])
    if not path.is_file():
        raise NotFound(f"Notebook source is missing: {record['source_path']}")
    raw = path.read_bytes()
    token = "notebook:" + digest(raw)
    if expected_revision is not None and expected_revision.strip('"') != token:
        raise Conflict(f"Stale notebook revision; current revision is {token}.")
    return {
        "record": loaded["record"],
        "metadata_revision": loaded["revision"],
        "path": path,
        "raw": raw,
        "token": token,
        "notebook": nb.load(raw),
    }


def save(
    store: Store,
    loaded: dict,
    notebook: dict,
    *,
    images: dict[str, bytes] | None = None,
) -> dict:
    if notebook == loaded["notebook"]:
        return {
            "path": loaded["record"]["source_path"],
            "revision": loaded["token"],
            "changed": False,
        }
    raw = nb.dump(notebook)
    updated = store.write_notebook(
        loaded["record"]["id"],
        raw,
        loaded["metadata_revision"],
        digest(loaded["raw"]),
        images=images,
    )
    return {
        "path": loaded["record"]["source_path"],
        "revision": "notebook:" + digest(raw),
        "changed": True,
        "metadata_revision": updated["revision"],
    }


def tags(cell: dict) -> list[str]:
    value = cell.get("metadata", {}).get("tags", [])
    return value if isinstance(value, list) else []


def label(cell: dict) -> str | None:
    if cell["cell_type"] == "markdown":
        match = re.search(r"\{#(fig-[a-zA-Z0-9-]+)(?=\s|\})", nb.source(cell))
        return match[1] if match else None
    for line in nb.source(cell).splitlines():
        current = line.strip()
        if not current:
            continue
        if not current.startswith("#|"):
            return None
        match = re.match(r"#\|\s*label:\s*(.*?)\s*$", current)
        if match:
            return match[1]
    return None


def indices(
    notebook: dict, *, index: int | str | None, tag: str | None, cell_label: str | None
) -> list[int]:
    if sum(item is not None for item in (index, tag, cell_label)) > 1:
        raise ValueError("Use only one of --index, --tag or --label.")
    total = len(notebook["cells"])
    if index is None and tag is None and cell_label is None:
        return list(range(total))
    if index is not None:
        if isinstance(index, int):
            value = index + total if index < 0 else index
            if not 0 <= value < total:
                raise ValueError(
                    f"Cell index {index} is out of range for {total} cells."
                )
            return [value]
        spec = index.strip()
        if ":" not in spec:
            return indices(notebook, index=int(spec), tag=None, cell_label=None)
        start_text, end_text = spec.split(":", 1)
        start = int(start_text) if start_text else 0
        end = int(end_text) if end_text else total
        start = start + total if start < 0 else start
        end = end + total if end < 0 else end
        if not 0 <= start <= end <= total:
            raise ValueError(f"Cell range {spec!r} is out of range for {total} cells.")
        return list(range(start, end))
    return [
        i
        for i, cell in enumerate(notebook["cells"])
        if (tag is not None and tag in tags(cell))
        or (cell_label is not None and label(cell) == cell_label)
    ]


def unique_index(
    notebook: dict, *, index: int | None, tag: str | None, cell_label: str | None
) -> int:
    if sum(item is not None for item in (index, tag, cell_label)) != 1:
        raise ValueError("Pass exactly one of --index, --tag or --label.")
    matches = indices(notebook, index=index, tag=tag, cell_label=cell_label)
    if not matches:
        raise ValueError("No notebook cell matched that locator.")
    if len(matches) != 1:
        raise ValueError(
            f"Ambiguous locator matched cells {', '.join(map(str, matches))}."
        )
    return matches[0]


def _slice(value: str, offset: int, limit: int | None) -> tuple[str, str]:
    if offset < 0 or (limit is not None and limit < 0):
        raise ValueError("Offsets and limits must be non-negative.")
    shown = value[offset:] if limit is None else value[offset : offset + limit]
    return shown, (
        f" src[{offset}:{offset + len(shown)}] of {len(value)}"
        if offset or len(shown) < len(value)
        else ""
    )


def _render_output(output: dict, offset: int, limit: int | None) -> str:
    kind = output.get("output_type", "unknown")
    if kind == "stream":
        text = output.get("text", "")
        text = "".join(text) if isinstance(text, list) else str(text)
        shown, marker = _slice(text, offset, limit)
        return f"[stream:{output.get('name', 'stdout')}{marker}]\n{shown}"
    if kind == "error":
        trace = output.get("traceback", [])
        trace = "\n".join(trace) if isinstance(trace, list) else str(trace)
        text = "\n".join(
            part
            for part in (output.get("ename", "Error"), output.get("evalue", ""), trace)
            if part
        )
        shown, marker = _slice(text, offset, limit)
        return f"[error{marker}]\n{shown}"
    data = output.get("data", {}) or {}
    text = data.get("text/plain") or data.get("text/html")
    if isinstance(text, list):
        text = "".join(text)
    rendered = []
    if text is not None:
        shown, marker = _slice(str(text), offset, limit)
        rendered.append(f"[{kind}:{marker.strip()}]\n{shown}")
    for mime, payload in data.items():
        if mime.startswith("image/"):
            size = len(payload) if isinstance(payload, (str, bytes, list)) else 0
            rendered.append(
                f"[{mime}: stored image ({size} encoded characters); use `at notebook output` to save it]"
            )
    return "\n".join(rendered) if rendered else f"[{kind}: no text output]"


def render_cell(
    cell: dict,
    index: int,
    *,
    offset: int = 0,
    limit: int | None = DEFAULT_SOURCE_LIMIT,
    with_outputs: bool = False,
    out_offset: int = 0,
    out_limit: int | None = None,
    context: bool = False,
) -> str:
    kind = cell["cell_type"]
    extras = []
    if tags(cell):
        extras.append("tags:" + ",".join(str(item) for item in tags(cell)))
    current_label = label(cell)
    if current_label:
        extras.append("label:" + current_label)
    if context:
        extras.append("context")
    header = f"> cell {index} [{kind}]" + (" " + " ".join(extras) if extras else "")
    source, marker = _slice(nb.source(cell), offset, limit)
    header += marker
    if kind == "code":
        body = f"```{{python}}\n{source}\n```" if source else "```{python}\n```"
        result = [header, "", body]
    else:
        result = [header, source] if source else [header]
    if with_outputs and kind == "code":
        outputs = cell.get("outputs", []) or []
        result += ["", f"> cell {index} outputs ({len(outputs)} total)"]
        for output in outputs:
            result += ["", _render_output(output, out_offset, out_limit)]
    return "\n\n".join(result)


def cat(
    store: Store,
    name: str,
    *,
    index: str | None = None,
    tag: str | None = None,
    cell_label: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_SOURCE_LIMIT,
    with_outputs: bool = False,
    out_offset: int = 0,
    out_limit: int | None = None,
    context: int = 0,
    with_revision: bool = False,
) -> str:
    with store.lock():
        loaded = load(store, name)
    if context < 0:
        raise ValueError("Context must be non-negative.")
    selected = indices(loaded["notebook"], index=index, tag=tag, cell_label=cell_label)
    if (
        index is not None or tag is not None or cell_label is not None
    ) and not selected:
        raise ValueError("No notebook cells matched that locator.")
    header = f"> source-revision: {loaded['token']}\n\n" if with_revision else ""
    if context and selected:
        lower = max(0, min(selected) - context)
        upper = min(len(loaded["notebook"]["cells"]), max(selected) + context + 1)
        matched = set(selected)
        selected = list(range(lower, upper))
    else:
        matched = set(selected)
    rendered = [
        render_cell(
            loaded["notebook"]["cells"][i],
            i,
            offset=offset,
            limit=None if limit == 0 else limit,
            with_outputs=with_outputs,
            out_offset=out_offset,
            out_limit=out_limit,
            context=i not in matched,
        )
        for i in selected
    ]
    return header + "\n\n".join(rendered)


def find(store: Store, query: str) -> list[str]:
    if not query.strip():
        raise ValueError("Search query must not be empty.")
    needle = query.casefold()
    found = []
    with store.lock():
        for item in store.ls("post"):
            record = item["record"]
            path = store.path(record["source_path"])
            if not path.is_file():
                continue
            notebook = nb.load(path.read_bytes())
            for index, cell in enumerate(notebook["cells"]):
                for line in nb.source(cell).splitlines():
                    if needle in line.casefold():
                        found.append(f"{record['id']} [cell {index}]: {line}")
    return found


def update(store: Store, name: str, expected_revision: str | None, transform) -> dict:
    with store.lock():
        loaded = load(store, name, expected_revision)
    notebook = copy.deepcopy(loaded["notebook"])
    transform(notebook)
    if len(json.dumps(notebook, ensure_ascii=False)) > 100_000_000:
        raise ValueError("Notebook is too large to save (>100 MB).")
    # write_notebook acquires the writer lock and checks both revisions. Holding
    # our read lock here would deadlock on its second file descriptor.
    return save(store, loaded, notebook)


def set_source(notebook: dict, index: int, source: str):
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError(f"Cell source exceeds {MAX_SOURCE_CHARS:,} characters.")
    if nb.source(notebook["cells"][index]) != source:
        notebook["cells"][index]["source"] = source.splitlines(keepends=True)


def append(notebook: dict, source: str, cell_type: str = "md"):
    notebook["cells"].append(new_cell(source, cell_type))


def new_cell(source: str, cell_type: str = "md") -> dict:
    if cell_type not in ("md", "markdown", "code"):
        raise ValueError("Cell type must be 'md' or 'code'.")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError(f"Cell source exceeds {MAX_SOURCE_CHARS:,} characters.")
    return nb.cell(source, "markdown" if cell_type in ("md", "markdown") else "code")


def _figure_image(store: Store, loaded: dict, filename: Path) -> tuple[str, bytes, str]:
    verified, raw = store.image(filename, allow_svg=True)
    extension = Path(verified).suffix
    if extension == ".jpg" and filename.suffix.lower() == ".jpeg":
        extension = ".jpeg"
    stem = f"{loaded['record']['id'].split('/')[1]}-{uuid4().hex}"
    image_path = f"content/images/post/{stem}{extension}"
    relative = Path(
        os.path.relpath(store.path(image_path), loaded["path"].parent)
    ).as_posix()
    return image_path, raw, relative


def replace_figure(
    store: Store,
    name: str,
    filename: Path,
    *,
    index: int | None = None,
    cell_label: str | None = None,
    expected_revision: str | None = None,
) -> dict:
    """Replace only an image URL, retaining its caption, label and cell metadata."""
    with store.lock():
        loaded = load(store, name, expected_revision)
    position = unique_index(
        loaded["notebook"], index=index, tag=None, cell_label=cell_label
    )
    cell = loaded["notebook"]["cells"][position]
    if cell["cell_type"] != "markdown":
        raise ValueError("Select a Markdown figure cell.")
    source = nb.source(cell)
    images = list(nb.IMAGE_LINK.finditer(source))
    if len(images) != 1:
        raise ValueError("The selected cell must contain exactly one Markdown image.")
    image_path, raw, relative = _figure_image(store, loaded, filename)
    match = images[0]
    if match[2].startswith("<"):
        relative = f"<{relative}>"
    updated_source = source[: match.start(2)] + relative + source[match.end(2) :]
    notebook = copy.deepcopy(loaded["notebook"])
    set_source(notebook, position, updated_source)
    return save(store, loaded, notebook, images={image_path: raw}) | {
        "image": image_path,
        "index": position,
        "label": label(cell),
    }


def figure(
    store: Store,
    name: str,
    filename: Path,
    *,
    index: int | None = None,
    caption: str = "",
    alt: str | None = None,
    expected_revision: str | None = None,
) -> dict:
    """Copy an external image and insert a Quarto figure in one recoverable save."""
    with store.lock():
        loaded = load(store, name, expected_revision)
    position = len(loaded["notebook"]["cells"]) if index is None else index
    if not 0 <= position <= len(loaded["notebook"]["cells"]):
        raise ValueError("Figure index is out of range (indices start at zero).")
    if any("\n" in text or "\r" in text for text in (caption, alt or "")):
        raise ValueError("Figure caption and alt text must be single-line text.")
    image_path, raw, relative = _figure_image(store, loaded, filename)
    figure_label = f"fig-{Path(image_path).stem}"
    attributes = f"#{figure_label}"
    if alt is not None:
        attributes += " fig-alt=" + json.dumps(alt, ensure_ascii=False)
    # --caption is plain text; escape Markdown delimiters without asking authors
    # to know the image syntax. The cell can still be edited normally afterward.
    caption = caption.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    source = f"![{caption}]({relative}){{{attributes}}}\n"
    notebook = copy.deepcopy(loaded["notebook"])
    notebook["cells"].insert(position, new_cell(source))
    return save(store, loaded, notebook, images={image_path: raw}) | {
        "image": image_path,
        "index": position,
        "label": figure_label,
    }


def _extract_images(
    output: dict, paths: list[Path], stem: str, cell_index: int, output_index: int
):
    extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/avif": ".avif",
        "image/svg+xml": ".svg",
    }
    data = output.get("data", {}) or {}
    for mime, ext in extensions.items():
        value = data.get(mime)
        if value is None:
            continue
        if isinstance(value, list):
            value = "".join(value)
        raw = (
            value
            if isinstance(value, bytes)
            else (
                str(value).encode()
                if mime == "image/svg+xml"
                else base64.b64decode(value)
            )
        )
        path = paths[0] / f"{stem}-cell-{cell_index}-output-{output_index}{ext}"
        path.write_bytes(raw)
        paths.append(path)


def output_images(
    store: Store, name: str, cell_index: int, output_index: int | None = None
) -> tuple[list[str], list[Path]]:
    with store.lock():
        loaded = load(store, name)
    cells = loaded["notebook"]["cells"]
    if not 0 <= cell_index < len(cells):
        raise ValueError("Cell index is out of range.")
    cell = cells[cell_index]
    if cell["cell_type"] != "code":
        raise ValueError("That cell has no code outputs.")
    outputs = cell.get("outputs", []) or []
    if not outputs:
        raise ValueError("That code cell has no stored outputs.")
    selected = range(len(outputs)) if output_index is None else [output_index]
    if output_index is not None and not 0 <= output_index < len(outputs):
        raise ValueError("Output index is out of range.")
    directory = store.path(".atlas/cms/notebook-output")
    directory.mkdir(parents=True, exist_ok=True)
    saved = []
    text = []
    paths = [directory]
    for index in selected:
        current = outputs[index]
        text.append(_render_output(current, 0, None))
        _extract_images(current, paths, loaded["path"].stem, cell_index, index)
    saved.extend(path for path in paths[1:])
    return text, saved


def run(
    store: Store,
    name: str,
    *,
    index: int | None = None,
    kernel: str | None = None,
    timeout: int = 300,
    expected_revision: str | None = None,
) -> dict:
    import nbformat
    from nbclient import NotebookClient

    with store.lock():
        loaded = load(store, name, expected_revision)
    notebook = nbformat.reads(
        loaded["raw"].decode("utf-8"), as_version=nbformat.NO_CONVERT
    )
    cells = notebook.cells
    if index is not None and not 0 <= index < len(cells):
        raise ValueError(
            f"Cell index is out of range (notebook has {len(cells)} cells)."
        )
    if index is not None and cells[index].cell_type != "code":
        return {
            "ran": 0,
            "errors": [],
            "path": loaded["record"]["source_path"],
            "revision": loaded["token"],
        }
    code_count = sum(
        cell.cell_type == "code"
        for cell in (cells if index is None else cells[: index + 1])
    )
    if code_count == 0:
        return {
            "ran": 0,
            "errors": [],
            "path": loaded["record"]["source_path"],
            "revision": loaded["token"],
        }
    kernel_name = (
        kernel or (notebook.metadata.get("kernelspec") or {}).get("name") or "python3"
    )
    if index is None:
        target = notebook
    else:
        target = nbformat.v4.new_notebook(
            metadata=copy.deepcopy(notebook.metadata),
            cells=copy.deepcopy(cells[: index + 1]),
        )
    try:
        NotebookClient(
            target,
            timeout=timeout,
            kernel_name=kernel_name,
            allow_errors=True,
            resources={"metadata": {"path": str(loaded["path"].parent)}},
        ).execute()
    except Exception as error:
        raise ValueError(
            f"Kernel {kernel_name!r} failed ({type(error).__name__}): {error}"
        ) from error
    errors = []
    selected_cells = cells if index is None else target.cells
    for i, cell in enumerate(selected_cells):
        for item in cell.get("outputs", []) or []:
            if item.get("output_type") == "error":
                errors.append(
                    {
                        "index": i,
                        "ename": item.get("ename", "Error"),
                        "evalue": item.get("evalue", ""),
                    }
                )
    # Merge execution results into the original JSON structure. Serializing the
    # nbformat copy would normalize every cell, including untouched prefix cells.
    updated = copy.deepcopy(loaded["notebook"])
    for i in range(len(cells)) if index is None else [index]:
        if cells[i].cell_type == "code":
            updated["cells"][i]["outputs"] = target.cells[i].get("outputs", [])
            updated["cells"][i]["execution_count"] = target.cells[i].get(
                "execution_count"
            )
    raw = nb.dump(updated)
    changed = updated != loaded["notebook"]
    try:
        saved = store.write_notebook(
            loaded["record"]["id"],
            raw,
            loaded["metadata_revision"],
            digest(loaded["raw"]),
        )
    except (ValueError, OSError, yaml.YAMLError) as error:
        conflict_path = store.preserve(
            f"execution-conflicts/{loaded['path'].stem}-{uuid4().hex}.ipynb", raw
        )
        raise type(error)(
            f"{error}; execution results retained at {conflict_path}."
        ) from error
    return {
        "ran": code_count,
        "errors": errors,
        "path": loaded["record"]["source_path"],
        "revision": "notebook:" + digest(raw) if changed else loaded["token"],
        "metadata_revision": saved["revision"],
    }


def list_kernels() -> list[dict]:
    from jupyter_client.kernelspec import KernelSpecManager

    specs = KernelSpecManager().get_all_specs()
    return [
        {"name": name, "display_name": item["spec"].get("display_name", name)}
        for name, item in sorted(specs.items())
    ]


def diff(store: Store, name: str, base: str = "HEAD") -> str:
    with store.lock():
        loaded = load(store, name)
    relative = loaded["path"].resolve().relative_to(store.root)
    result = subprocess.run(
        ["git", "show", f"{base}:{relative.as_posix()}"],
        cwd=store.root,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"No tracked notebook found at {base}:{relative}.")
    original = nb.load(result.stdout)
    current = loaded["notebook"]

    def markdown(value: dict) -> str:
        return (
            "\n\n".join(
                f"> cell {i} [{cell['cell_type']}]\n\n{nb.source(cell)}"
                for i, cell in enumerate(value["cells"])
            )
            + "\n"
        )

    lines = difflib.unified_diff(
        markdown(original).splitlines(keepends=True),
        markdown(current).splitlines(keepends=True),
        fromfile=f"{base}:{relative}",
        tofile=str(relative),
    )
    return "".join(lines)
