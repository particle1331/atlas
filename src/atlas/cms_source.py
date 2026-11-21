"""Project eligible committed companion text without executing it."""

import json
import os
import posixpath
import re
import shutil
import string
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import (
    MarkdownLexer,
    TextLexer,
    get_lexer_by_name,
    get_lexer_for_filename,
)
from pygments.util import ClassNotFound

from atlas import cms_notebooks as nb
from atlas.cms_store import Store, document

HTML_LITERAL = str.maketrans({"{": "&#123;", "}": "&#125;", "`": "&#96;"})
HEADING_PREFIX = "source-heading-"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TEXT_LIMIT = 1024 * 1024
GIT = ["git", "--no-replace-objects", "-c", "core.fsmonitor=false"]
PRIVATE_NAME = re.compile(
    r"^(?:id_(?:rsa|dsa|ecdsa|ed25519)|kubeconfig|private)(?:\.|$)"
    r"|(?:^|[._-])(?:credentials?|secrets?|passwords?|passwd|"
    r"api[_-]?keys?|private[_-]?keys?|access[_-]?tokens?)(?:[._-]|$)"
    r"|\.(?:key|pem|p12|pfx|jks|keystore|kdbx|tfstate|sqlite3?|db|bak|old|orig|rej)$",
    re.IGNORECASE,
)
SCANNER_CONFIG = r"""
[extend]
useDefault = true

[[rules]]
id = "atlas-jina-api-key"
description = "Jina API key"
regex = '''\bjina_[A-Za-z0-9_-]{24,}\b'''
keywords = ["jina_"]

[[rules]]
id = "atlas-literal-password"
description = "Literal password or client secret"
regex = '''(?im)(?:^|[\s{,])["']?(?:[a-z_]*password|passwd|client_secret)["']?\s*[:=]\s*["'][^"'\r\n]{8,}["']'''
keywords = ["password", "passwd", "client_secret"]

[[rules]]
id = "atlas-unquoted-password"
description = "Unquoted password or client secret in an environment assignment"
regex = '''(?m)^[\t ]*(?:export[\t ]+)?(?:[A-Z_][A-Z0-9_]*_)?(?:PASSWORD|PASSWD|CLIENT_SECRET)[\t ]*=[\t ]*([^\t \r\n"'`#][^\t \r\n"'`]{7,})[\t ]*(?:[\t ]#.*)?\r?$'''
secretGroup = 1
keywords = ["password", "passwd", "client_secret"]

[[rules.allowlists]]
description = "Unquoted environment variable references, not literal values"
regexes = ['''^\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})$''']

[[rules.allowlists]]
description = "Exact Redis example placeholders that mirror their field names"
regexTarget = "match"
regexes = [
    '''^LANGFUSE_REDIS_PASSWORD=langfuse_redis_password$''',
    '''^REDIS__PASSWORD=redis_password$''',
]
"""
type SourceTree = dict[str, str | SourceTree]


@dataclass(frozen=True)
class NotebookView:
    language: str
    blocks: tuple[tuple[str, str], ...]

    @property
    def text(self) -> str:
        return "\n\n".join(text for _, text in self.blocks)


type SourceFiles = dict[PurePosixPath, str | NotebookView]


@dataclass
class SecretFinding:
    rules: set[str] = field(default_factory=set)
    path_spans: list[tuple[int, int]] = field(default_factory=list)


class SourceBrowserUnavailable(ValueError):
    """The source browser could not read its inputs safely."""


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
        if fragment and target.suffix.lower() in {".md", ".ipynb"}:
            fragment = HEADING_PREFIX + fragment
    elif target in folders:
        destination, fragment = "index.html", folder_id(target) if target.parts else ""
    else:
        return None
    return urlunsplit(
        ("", "", posixpath.relpath(destination, pages[relative].parent), "", fragment)
    )


def markdown_html(
    text: str,
    relative: PurePosixPath,
    pages: dict[PurePosixPath, PurePosixPath],
    folders: set[PurePosixPath],
    *,
    headings: set[str] | None = None,
) -> str:
    """Render Markdown as inert content, without Quarto directives or raw HTML."""
    parser = MarkdownIt("commonmark", {"html": False}).enable(
        ["table", "strikethrough"]
    )
    env = {}
    tokens = parser.parse(text, env)
    if headings is None:
        headings = set()
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
    return parser.renderer.render(tokens, parser.options, env)


def git_environment() -> dict[str, str]:
    # Bind Git to this workspace and its own configuration, not a caller's
    # alternate index, object database, worktree or command-line config.
    global_config = {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM"}
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") or key in global_config
    } | {
        "GIT_NO_LAZY_FETCH": "1",
    }


def git_run(root: Path, *args: str, input: bytes | None = None):
    return subprocess.run(
        [*GIT, *args],
        cwd=root,
        env=git_environment(),
        input=input,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def is_git_worktree(root: Path) -> bool:
    result = git_run(root, "rev-parse", "--show-toplevel")
    return (
        result.returncode == 0
        and Path(os.fsdecode(result.stdout.removesuffix(b"\n"))).resolve() == root
    )


def ignored_source_paths(
    root: Path, paths: Iterable[PurePosixPath]
) -> set[PurePosixPath]:
    """Ask Git about ignore rules even when a candidate is already tracked."""
    path_list = b"".join(b"./" + os.fsencode(path) + b"\0" for path in paths)
    if not path_list:
        return set()
    result = git_run(
        root, "check-ignore", "--no-index", "-z", "--stdin", input=path_list
    )
    if result.returncode not in (0, 1):
        raise SourceBrowserUnavailable("Git ignore rules could not be checked.")
    return {
        PurePosixPath(os.fsdecode(path)) for path in result.stdout.split(b"\0") if path
    }


def project_blobs(root: Path, commit: str, bases: set[PurePosixPath]):
    """Select bounded regular blobs from one immutable commit."""
    result = git_run(
        root,
        "--literal-pathspecs",
        "ls-tree",
        "-rlz",
        commit,
        "--",
        *(f"{base}/" for base in sorted(bases)),
    )
    if result.returncode:
        raise SourceBrowserUnavailable("Git could not list committed source files.")
    candidates = {}
    for entry in result.stdout.rstrip(b"\0").split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid, size = metadata.split()
        if (
            mode not in {b"100644", b"100755"}
            or kind != b"blob"
            or int(size) > TEXT_LIMIT
        ):
            continue
        path = PurePosixPath(os.fsdecode(raw_path))
        if any(
            part.startswith(".") or PRIVATE_NAME.search(part) for part in path.parts
        ):
            continue
        candidate = root / path
        # The working checkout supplies ignore rules only. Excluding absent or
        # replaced paths also keeps check-ignore from traversing symlink parents.
        if any(
            parent.is_symlink()
            for parent in (candidate, *candidate.parents)
            if parent != root
        ):
            continue
        if candidate.is_file():
            candidates[path] = (oid, int(size))
    ignored = ignored_source_paths(root, candidates)
    return {path: blob for path, blob in candidates.items() if path not in ignored}


def stored_text(value, separator: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(line, str) for line in value):
        return separator.join(value)
    return ""


def notebook_view(data: bytes) -> NotebookView:
    notebook = nb.load(data)
    metadata = notebook.get("metadata")
    language_info = (
        metadata.get("language_info") if isinstance(metadata, dict) else None
    )
    language = language_info.get("name") if isinstance(language_info, dict) else None
    blocks = []
    for cell in notebook["cells"]:
        cell_type = cell["cell_type"]
        blocks.append((cell_type, nb.source(cell)))
        outputs = cell.get("outputs")
        if cell_type != "code" or not isinstance(outputs, list):
            continue
        for output in outputs:
            if not isinstance(output, dict):
                continue
            kind = output.get("output_type")
            block_type = "output"
            if kind == "stream":
                text = stored_text(output.get("text"))
            elif kind == "error":
                text = stored_text(output.get("traceback"), "\n")
                if not text:
                    text = ": ".join(
                        filter(
                            None,
                            (
                                stored_text(output.get(key))
                                for key in ("ename", "evalue")
                            ),
                        )
                    )
            elif kind in ("display_data", "execute_result") and isinstance(
                output.get("data"), dict
            ):
                bundle = output["data"]
                text = stored_text(bundle.get("text/markdown"))
                if text:
                    block_type = "output-markdown"
                else:
                    text = stored_text(bundle.get("text/plain"))
            else:
                continue
            if text:
                blocks.append((block_type, ANSI_ESCAPE.sub("", text)))
    return NotebookView(language if isinstance(language, str) else "", tuple(blocks))


def read_committed_text(
    root: Path, blobs: dict[PurePosixPath, tuple[bytes, int]]
) -> SourceFiles:
    files = {}
    with subprocess.Popen(
        [*GIT, "cat-file", "--batch"],
        cwd=root,
        env=git_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as git:
        assert git.stdin is not None and git.stdout is not None
        for path, (oid, size) in blobs.items():
            git.stdin.write(oid + b"\n")
            git.stdin.flush()
            header = oid + b" blob " + str(size).encode() + b"\n"
            if git.stdout.readline() != header:
                raise SourceBrowserUnavailable(
                    "Git could not read a committed source blob."
                )
            data = git.stdout.read(size)
            if len(data) != size or git.stdout.read(1) != b"\n":
                raise SourceBrowserUnavailable(
                    "Git returned an incomplete source blob."
                )
            if b"\0" in data:
                continue
            try:
                if path.suffix.casefold() == ".ipynb":
                    content = notebook_view(data)
                    text = content.text
                    text.encode("utf-8")
                else:
                    content = text = data.decode("utf-8")
            except (ValueError, RecursionError):
                continue
            if "\0" not in text:
                files[path] = content
        git.stdin.close()
        if git.wait():
            raise SourceBrowserUnavailable("Git could not read committed source files.")
    return files


def path_match_span(path: str, finding: dict) -> tuple[int, int]:
    """Convert Gitleaks' inclusive byte columns to a slice of the scanned path."""
    length = len(path.encode("utf-8"))
    start, end = finding.get("StartColumn"), finding.get("EndColumn")
    if (
        "\n" not in path
        and "\r" not in path
        and finding.get("StartLine") == finding.get("EndLine") == 1
        and type(start) is int
        and type(end) is int
        and 1 <= start <= end <= length
    ):
        return start - 1, end
    return 0, length


def secret_findings(
    files: dict[PurePosixPath, str],
) -> dict[PurePosixPath, SecretFinding]:
    """Collect rule IDs and the path spans to redact in diagnostics."""
    if not files:
        return {}
    scanner = shutil.which("gitleaks")
    if scanner is None:
        raise ValueError("Install Gitleaks to scan for secrets.")
    with tempfile.TemporaryDirectory(prefix="atlas-source-scan-") as temporary:
        workspace = Path(temporary)
        config = workspace / "scan.toml"
        config.write_text(SCANNER_CONFIG, encoding="utf-8")
        inputs = workspace / "files"
        inputs.mkdir()
        scan_paths = {}
        # Neutral filenames avoid scanner path allowlists. Scan names too because
        # they are displayed on pages and in the directory index.
        for index, (path, content) in enumerate(files.items()):
            for kind, text in (("content", content), ("path", display_path(path))):
                name = f"{index}-{kind}.txt"
                (inputs / name).write_bytes(text.encode("utf-8"))
                scan_paths[name] = (path, kind)
        try:
            result = subprocess.run(
                [
                    scanner,
                    "dir",
                    "--config",
                    str(config),
                    "--exit-code",
                    "23",
                    "--gitleaks-ignore-path",
                    str(workspace),
                    "--ignore-gitleaks-allow",
                    "--max-decode-depth",
                    "5",
                    "--no-banner",
                    "--no-color",
                    "--redact=100",
                    "--log-level",
                    "error",
                    "--report-format",
                    "json",
                    "--report-path",
                    "-",
                    str(inputs),
                ],
                cwd=workspace,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith("GITLEAKS_")
                },
                capture_output=True,
                timeout=120,
            )
            findings = json.loads(result.stdout)
            if (
                result.returncode not in {0, 23}
                or result.stderr
                or not isinstance(findings, list)
                or bool(findings) != (result.returncode == 23)
            ):
                raise ValueError
            blocked = {}
            for finding in findings:
                path, kind = scan_paths[Path(finding["File"]).name]
                rule = finding["RuleID"]
                if not re.fullmatch(r"[A-Za-z0-9_-]+", rule):
                    raise ValueError
                entry = blocked.setdefault(path, SecretFinding())
                entry.rules.add(rule)
                if kind == "path":
                    entry.path_spans.append(
                        path_match_span(display_path(path), finding)
                    )
        except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
            # Never print scanner output: it was produced from private input.
            raise ValueError("The secret scan failed.") from None
    return blocked


def redact_path(path: PurePosixPath, spans: list[tuple[int, int]]) -> str:
    raw = display_path(path).encode("utf-8")
    visible = []
    offset = 0
    # Overlapping and adjacent findings share a single mask.
    for start, end in sorted(spans):
        if not visible or start > offset:
            visible.append(raw[offset:start])
        offset = max(offset, end)
    visible.append(raw[offset:])
    try:
        return b"***".join(visible).decode("utf-8")
    except UnicodeDecodeError:
        return "***"


def source_files(store: Store, records: Iterable[dict]) -> dict[str, SourceFiles]:
    """Read eligible committed companion text for the browser pages."""
    projects = {}
    for record in records:
        project = store.code_directory(record)
        if project is not None:
            projects[record["id"]] = PurePosixPath(project.relative_to(store.root))
    if not projects:
        return {}
    if not is_git_worktree(store.root):
        raise SourceBrowserUnavailable("Companion source requires a Git checkout.")
    head = git_run(store.root, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    if head.returncode == 1:
        return {identity: {} for identity in projects}
    if head.returncode:
        raise SourceBrowserUnavailable("Git could not resolve the source commit.")
    commit = head.stdout.strip().decode("ascii")
    blobs = project_blobs(store.root, commit, set(projects.values()))
    files = read_committed_text(store.root, blobs)
    return {
        identity: {
            path.relative_to(base): text
            for path, text in files.items()
            if path.is_relative_to(base)
        }
        for identity, base in projects.items()
    }


def source_lexer(relative: PurePosixPath, text: str):
    options = {"stripnl": False, "ensurenl": False}
    if relative.suffix.lower() == ".md":
        return MarkdownLexer(**options)
    try:
        return get_lexer_for_filename(relative.name, text, **options)
    except ClassNotFound:
        return TextLexer(**options)


def notebook_html(
    notebook: NotebookView,
    relative: PurePosixPath,
    pages: dict[PurePosixPath, PurePosixPath],
    folders: set[PurePosixPath],
) -> str:
    options = {"stripnl": False, "ensurenl": False}
    try:
        lexer = get_lexer_by_name(notebook.language, **options)
    except ClassNotFound:
        lexer = TextLexer(**options)
    formatter = HtmlFormatter(cssclass="source-preview", noclasses=True)
    headings: set[str] = set()
    blocks = []
    for kind, text in notebook.blocks:
        if kind in {"markdown", "output-markdown"}:
            html = markdown_html(text, relative, pages, folders, headings=headings)
        elif kind == "output":
            html = f"<pre><code>{escape(text)}</code></pre>"
        else:
            html = highlight(
                text, lexer if kind == "code" else TextLexer(**options), formatter
            )
        if kind.startswith("output"):
            html = f'<div class="cell-output mb-3">{html}</div>'
        elif kind in {"code", "raw"}:
            html = f'<div class="cell mb-3">{html}</div>'
        blocks.append(html)
    return "\n".join(blocks)


def write_source_browser(stage: Path, record: dict, files: SourceFiles) -> str:
    """Write the Quarto index and file views; return the link for the post."""
    slug = record["id"].split("/")[1]
    directory = stage / "posts" / slug / "source"
    directory.mkdir(parents=True, exist_ok=True)
    meta = {
        "toc": False,
        "search": False,
        "draft": record["status"] == "draft",
        "grid": {"body-width": "1053px"},
    }
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
    for relative, text in files.items():
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
        if isinstance(text, NotebookView):
            rendered = raw_html(notebook_html(text, relative, pages, folders))
            output.write_bytes(document(page_meta, back + "\n\n" + rendered))
            continue
        nav = back
        if relative.suffix.lower() == ".md":
            raw_name = f"file~raw~{page.name}"
            rendered_nav = f"{back} · [View source](./{raw_name}.html)"
            rendered = raw_html(markdown_html(text, relative, pages, folders))
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
                        else "No eligible committed files found."
                    ),
                ]
            ),
        )
    )
    return f"./{slug}/source/index.html"
