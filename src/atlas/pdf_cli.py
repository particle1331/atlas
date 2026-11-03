"""Read local PDF documents: metadata, bookmarks, page text and search."""

from pathlib import Path
from typing import Annotated, NoReturn

import typer

app = typer.Typer(no_args_is_help=True, help="Inspect and read local PDF documents.")

PdfPath = Annotated[
    Path,
    typer.Argument(help="Path to a local PDF file.", show_default=False),
]
ReadPages = Annotated[
    str,
    typer.Option(
        "--pages",
        help="1-based page range: 25-53, 25, 25- (to the end) or -53 (from the start).",
    ),
]
FindPages = Annotated[
    str | None,
    typer.Option(
        "--pages",
        help="Optional 1-based page range to search, such as 25-53 or 25-.",
    ),
]


def _exit(message: str, *, code: int = 2) -> NoReturn:
    typer.secho(f"Error: {message}", err=True, fg=typer.colors.BRIGHT_RED)
    raise typer.Exit(code)


def _resolve(path: Path) -> Path:
    resolved = path.expanduser()
    if not resolved.is_file():
        _exit(f"No such file: {path}")
    return resolved


def _open(path: Path):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        return PdfReader(path)
    except (PdfReadError, OSError, ValueError) as error:
        _exit(f"Could not read PDF ({type(error).__name__}): {path}")


def _parse_pages(spec: str, total: int) -> range:
    """Convert a 1-based page spec such as 25-53 into an inclusive range."""
    spec = spec.strip()
    if not spec or spec == "-":
        _exit("The page range is empty. Use forms like 25-53, 25, 25- or -53.")
    first, sep, last = spec.partition("-")
    if first == "":
        start = 1
    elif first.isdigit():
        start = int(first)
    else:
        _exit(f"Invalid page range {spec!r}. Use forms like 25-53, 25, 25- or -53.")
    if not sep:
        end = start
    elif last == "":
        end = total
    elif last.isdigit():
        end = int(last)
    else:
        _exit(f"Invalid page range {spec!r}. Use forms like 25-53, 25, 25- or -53.")
    if start < 1 or end > total:
        _exit(f"Pages must be between 1 and {total}.")
    if start > end:
        _exit("The start page must not exceed the end page.")
    return range(start, end + 1)


def _walk_outline(items):
    for item in items:
        if isinstance(item, list):
            yield from _walk_outline(item)
        else:
            yield item


def _extract_pages(path: Path, numbers: range) -> list[str]:
    """Extract text for consecutive 1-based pages with pdfminer.six."""
    from pdfminer.high_level import extract_text
    from pdfminer.pdfexceptions import PDFException

    try:
        text = extract_text(str(path), page_numbers=[n - 1 for n in numbers])
    except (PDFException, OSError, ValueError) as error:
        _exit(f"Could not extract PDF text ({type(error).__name__}): {path}")
    chunks = text.split("\x0c")
    return [chunks[i].rstrip() if i < len(chunks) else "" for i in range(len(numbers))]


@app.command("info")
def pdf_info(path: PdfPath):
    """Show page count, title, author and bookmark count for a PDF."""
    reader = _open(_resolve(path))
    metadata = reader.metadata or {}
    title = str(metadata.get("/Title") or "unknown")
    author = str(metadata.get("/Author") or "unknown")
    typer.echo(f"Path: {path}")
    typer.echo(f"Pages: {len(reader.pages)}")
    typer.echo(f"Title: {title}")
    typer.echo(f"Author: {author}")
    typer.echo(f"Bookmarks: {len(list(_walk_outline(reader.outline)))}")


@app.command("outline")
def pdf_outline(path: PdfPath):
    """Print the bookmark tree with 1-based page numbers."""
    reader = _open(_resolve(path))

    def walk(items, depth: int = 0):
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
                typer.echo(f"{'  ' * depth}{item.title} (p.{page})")
            except (ValueError, KeyError):
                continue

    try:
        items = reader.outline
    except (ValueError, KeyError):
        items = []
    if not items:
        typer.echo("No bookmarks.")
        return
    walk(items)


@app.command("read")
def pdf_read(path: PdfPath, pages: ReadPages):
    """Print extracted text for a 1-based page range."""
    path = _resolve(path)
    reader = _open(path)
    numbers = _parse_pages(pages, len(reader.pages))
    for number, text in zip(numbers, _extract_pages(path, numbers), strict=True):
        typer.echo(f"--- p.{number} ---")
        typer.echo(text if text.strip() else "[no extractable text]")


@app.command("find")
def pdf_find(path: PdfPath, query: str, pages: FindPages = None):
    """Search text across the PDF and print page numbers with matching lines."""
    path = _resolve(path)
    reader = _open(path)
    numbers = (
        _parse_pages(pages, len(reader.pages))
        if pages is not None
        else range(1, len(reader.pages) + 1)
    )
    needle = query.casefold()
    matches = 0
    for number, text in zip(numbers, _extract_pages(path, numbers), strict=True):
        for line in text.splitlines():
            if needle in line.casefold():
                matches += 1
                typer.echo(f"p.{number}: {line.strip()}")
    if not matches:
        typer.echo("No matches.")
