"""Browse Git-visible companion files without executing them."""

import os
import posixpath
import re
import stat
import string
import subprocess
from base64 import b64encode
from contextlib import ExitStack
from hashlib import sha256
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import MarkdownLexer, TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from atlas.cms_store import Store, document

HTML_LITERAL = str.maketrans({"{": "&#123;", "}": "&#125;", "`": "&#96;"})
HEADING_PREFIX = "source-heading-"
FILE_LIMIT = 8 * 1024 * 1024
TEXT_LIMIT = 1024 * 1024
GIT = ["git", "-c", "core.fsmonitor=false"]
type SourceTree = dict[str, str | SourceTree]


def folder_id(folder: PurePosixPath) -> str:
    return "folder-" + ":".join(source_page(folder).parts)


def tree_html(tree: SourceTree, parent: PurePosixPath = PurePosixPath()) -> str:
    """Keep arbitrary Git filenames as text rather than interpreting Markdown."""
    lines = ["<ul>"]
    for name, entry in sorted(
        tree.items(), key=lambda item: (isinstance(item[1], str), item[0].casefold())
    ):
        if isinstance(entry, str):
            lines.append(f"<li>{entry}</li>")
        else:
            folder = parent / name
            lines.append(
                f'<li><span id="{folder_id(folder)}" class="source-folder">'
                f"<code>{escape(display_path(name))}/</code></span>"
                f"{tree_html(entry, folder)}</li>"
            )
    return "\n".join([*lines, "</ul>"])


def display_path(path: str | PurePosixPath) -> str:
    return str(path).encode("utf-8", errors="replace").decode("utf-8")


def literal_title(path: PurePosixPath) -> str:
    # Pandoc interprets titles as Markdown, even when quoted in YAML.
    return "".join(
        (
            f"&#{ord(char)};"
            if char in string.punctuation or not char.isprintable()
            else char
        )
        for char in display_path(path)
    )


def source_page(relative: PurePosixPath) -> PurePosixPath:
    # Quarto skips underscore-prefixed paths. Map punctuation and reserved
    # names to a URL-safe namespace that cannot coincide with an ordinary name.
    parts = []
    for part in relative.parts:
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,179}", part):
            digest = sha256(os.fsencode(part)).hexdigest()
            suffix = PurePosixPath(part).suffix
            parts.append(
                f"file~encoded~{digest}"
                + (suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,12}", suffix) else "")
            )
        elif (
            part.startswith("_")
            or part.casefold() == "index"
            or part.lower().endswith((".qmd", ".html"))
        ):
            parts.append(f"file~{part}")
        else:
            parts.append(part)
    return PurePosixPath(*parts)


def raw_html(html: str) -> str:
    # Prevent Quarto from treating file contents as shortcodes or fence delimiters.
    return "```{=html}\n" + html.translate(HTML_LITERAL).rstrip("\n") + "\n```"


def markdown_link(
    href: str,
    relative: PurePosixPath,
    pages: dict[PurePosixPath, PurePosixPath],
    folders: set[PurePosixPath],
) -> str | None:
    """Rewrite local links only when the target is present in this browser."""
    try:
        url = urlsplit(href)
    except ValueError:
        return None
    if url.scheme in {"http", "https"}:
        return href if url.hostname else None
    if url.scheme == "mailto":
        return href
    if url.scheme or url.netloc:
        return None
    path = unquote(url.path)
    if not path:
        return "#" + HEADING_PREFIX + url.fragment if url.fragment else None
    if path.startswith("/") or "\\" in path:
        return None
    target = PurePosixPath(posixpath.normpath((relative.parent / path).as_posix()))
    if target in pages:
        destination, fragment = f"{pages[target]}.html", url.fragment
        if fragment and target.suffix.lower() == ".md":
            fragment = HEADING_PREFIX + fragment
    elif target in folders:
        destination, fragment = "index.html", folder_id(target) if target.parts else ""
    else:
        return None
    return urlunsplit(
        ("", "", posixpath.relpath(destination, pages[relative].parent), "", fragment)
    )


def rendered_markdown(
    text: str,
    relative: PurePosixPath,
    pages: dict[PurePosixPath, PurePosixPath],
    folders: set[PurePosixPath],
) -> str:
    """Render Markdown as inert content, without Quarto directives or raw HTML."""
    parser = MarkdownIt("commonmark", {"html": False}).enable(
        ["table", "strikethrough"]
    )
    env = {}
    tokens = parser.parse(text, env)
    headings: set[str] = set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            title = "".join(
                child.content
                for child in tokens[index + 1].children or []
                if child.type in {"text", "code_inline", "image"}
            )
            anchor = (
                re.sub(r"[^\w -]", "", title.lower()).replace(" ", "-") or "section"
            )
            key, duplicate = anchor, 1
            while key in headings:
                key = f"{anchor}-{duplicate}"
                duplicate += 1
            headings.add(key)
            token.attrSet("id", HEADING_PREFIX + key)
        if token.children is None:
            continue
        link_stack: list[bool] = []
        children = []
        for child in token.children:
            if child.type == "link_open":
                href = markdown_link(
                    child.attrGet("href") or "", relative, pages, folders
                )
                # Autolinks can occur inside an ordinary link label. Keep the
                # label text, but never emit a nested anchor.
                emit = href is not None and not link_stack
                link_stack.append(emit)
                if not emit:
                    continue
                child.attrSet("href", href)
            elif child.type == "link_close" and not link_stack.pop():
                continue
            elif child.type == "image":
                # Show images through their own file pages, not inline markup.
                child.type = "text"
            children.append(child)
        token.children = children
    return raw_html(parser.renderer.render(tokens, parser.options, env))


def ignored_source_paths(root: Path, paths: list[PurePosixPath]) -> set[PurePosixPath]:
    """Ask Git about ignore rules even when a candidate is already tracked."""
    if not paths:
        return set()
    result = subprocess.run(
        [*GIT, "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=root,
        input=b"".join(b"./" + os.fsencode(path) + b"\0" for path in paths),
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise ValueError(
            f"Cannot check Git ignores for source browsing: {os.fsdecode(result.stderr).strip()}"
        )
    return {
        PurePosixPath(os.fsdecode(path)) for path in result.stdout.split(b"\0") if path
    }


def source_files(store: Store, record: dict) -> dict[PurePosixPath, Path | None] | None:
    """List the Git-visible files under code_path; never follow symlinks."""
    project = store.code_directory(record)
    if project is None:
        return None
    base = PurePosixPath(project.relative_to(store.root))
    result = subprocess.run(
        [
            *GIT,
            "--literal-pathspecs",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            f"{base}/",
        ],
        cwd=store.root,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(
            f"Cannot list source files for {base}: {os.fsdecode(result.stderr).strip()}"
        )
    candidates: dict[PurePosixPath, Path | None] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = PurePosixPath(os.fsdecode(raw))
        if not path.is_relative_to(base) or path == base:
            continue
        parent = store.root / path.parent
        if any(p.is_symlink() for p in (parent, *parent.parents) if p != store.root):
            continue
        candidate = store.root / path
        if candidate.is_symlink():
            candidates[path] = None
        elif candidate.is_file():
            candidates[path] = candidate
    ignored = ignored_source_paths(store.root, list(candidates))
    return {
        path.relative_to(base): file
        for path, file in candidates.items()
        if path not in ignored
    }


def source_text(data: bytes) -> str | None:
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def read_source_file(root: Path, file: Path) -> bytes | None:
    """Read a bounded regular file without following any symlink during open."""
    parts = file.relative_to(root).parts
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        directory = os.open(root, dir_flags)
        stack.callback(os.close, directory)
        for part in parts[:-1]:
            directory = os.open(part, dir_flags, dir_fd=directory)
            stack.callback(os.close, directory)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        stack.callback(os.close, descriptor)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(
                f"Expected a regular source file: {file.relative_to(root)}"
            )
        if info.st_size > FILE_LIMIT:
            return None
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(FILE_LIMIT + 1)
        return data if len(data) <= FILE_LIMIT else None


def source_lexer(relative: PurePosixPath, text: str):
    options = {"stripnl": False, "ensurenl": False}
    if relative.suffix.lower() == ".md":
        return MarkdownLexer(**options)
    try:
        return get_lexer_for_filename(relative.name, text, **options)
    except ClassNotFound:
        return TextLexer(**options)


def write_source_browser(
    stage: Path, root: Path, record: dict, files: dict[PurePosixPath, Path | None]
) -> str:
    """Write the Quarto index and file views; return the link for the post."""
    slug = record["id"].split("/")[1]
    directory = stage / "posts" / slug / "source"
    directory.mkdir(parents=True, exist_ok=True)
    meta = {"toc": False, "search": False, "draft": record["status"] == "draft"}
    index = [f"[← Back to post](../../{slug}.html)", "## Project files"]
    tree: SourceTree = {}
    pages = {relative: source_page(relative) for relative in files}
    folders = {parent for relative in pages for parent in relative.parents}
    formatter = HtmlFormatter(
        cssclass="source-preview",
        noclasses=True,
        linenos="inline",
        lineanchors="L",
        anchorlinenos=True,
    )
    for relative, file in files.items():
        page = pages[relative]
        branch = tree
        for part in relative.parts[:-1]:
            subtree = branch.setdefault(part, {})
            assert isinstance(subtree, dict)
            branch = subtree
        label = escape(display_path(relative))
        branch[relative.name] = (
            f'<a href="./{page}.html" aria-label="{label}">'
            f"<code>{escape(display_path(relative.name))}</code></a>"
        )
        output = directory / f"{page}.qmd"
        output.parent.mkdir(parents=True, exist_ok=True)
        parent = "../" * (len(relative.parts) - 1) or "./"
        back = f"[← All project files]({parent}index.html)"
        page_meta = meta | {"title": literal_title(relative)}
        if file is None:
            output.write_bytes(
                document(page_meta, back + "\n\nSymbolic link not followed.")
            )
            continue
        data = read_source_file(root, file)
        if data is None:
            output.write_bytes(
                document(
                    page_meta,
                    back
                    + f"\n\nFile exceeds the {FILE_LIMIT // (1024 * 1024)} MiB browser limit.",
                )
            )
            continue
        text = source_text(data) if len(data) <= TEXT_LIMIT else None
        if text is None:
            encoded = b64encode(data).decode("ascii")
            download = (
                f'<p><a download="{escape(display_path(relative.name))}" '
                f'href="data:application/octet-stream;base64,{encoded}">Download file</a></p>'
            )
            output.write_bytes(document(page_meta, back + "\n\n" + raw_html(download)))
            continue
        nav = back
        if relative.suffix.lower() == ".md":
            raw_name = f"file~raw~{page.name}"
            rendered_nav = f"{back} · [View source](./{raw_name}.html)"
            rendered = rendered_markdown(text, relative, pages, folders)
            output.write_bytes(document(page_meta, rendered_nav + "\n\n" + rendered))
            output = output.with_name(f"{raw_name}.qmd")
            nav += f" · [View rendered](./{page.name}.html)"
        body = "\n\n".join(
            [
                nav,
                "[Skip source listing](#end-of-file){.visually-hidden-focusable}",
                raw_html(highlight(text, source_lexer(relative, text), formatter)),
                '::: {#end-of-file tabindex="-1"}\n:::',
            ]
        )
        output.write_bytes(document(page_meta, body))
    (directory / "index.qmd").write_bytes(
        document(
            meta | {"title": f"{record['title']} — Source"},
            "\n\n".join(
                [
                    *index,
                    (
                        raw_html(
                            '<div class="source-tree">' + tree_html(tree) + "</div>"
                        )
                        if tree
                        else "No non-ignored files found."
                    ),
                ]
            ),
        )
    )
    return f"./{slug}/source/index.html"
