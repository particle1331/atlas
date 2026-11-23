"""Screen repository and local workspace paths and text for secrets."""

import errno
import os
import re
import stat
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath

from atlas.cms_source import (
    GIT,
    SecretFinding,
    git_environment,
    git_run,
    is_git_worktree,
    notebook_view,
    redact_path,
    secret_findings,
)

type Views = dict[PurePosixPath, dict[str, None]]
type Blobs = dict[bytes, dict[PurePosixPath, bool]]
OBJECT_ID = re.compile(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})")
WORKSPACE_BATCH_PATHS = 2048
WORKSPACE_BATCH_CHARS = 16 * 1024 * 1024


def git_output(root: Path, *args: str, index_file: str | None = None) -> bytes:
    if index_file is None:
        result = git_run(root, *args)
    else:
        # A commit hook can receive a temporary index for a partial commit.
        result = subprocess.run(
            [*GIT, *args],
            cwd=root,
            env=git_environment() | {"GIT_INDEX_FILE": index_file},
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    if result.returncode:
        raise ValueError
    return result.stdout


def git_entries(data: bytes) -> list[bytes]:
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise ValueError
    return data[:-1].split(b"\0")


def repository_path(raw: bytes) -> PurePosixPath:
    if any(part in (b"", b".", b"..", b".git") for part in raw.split(b"/")):
        raise ValueError
    return PurePosixPath(os.fsdecode(raw))


def collect_blobs(
    entries: Iterable[bytes], views: Views, blobs: Blobs, *, head: bool = False
) -> None:
    for entry in entries:
        metadata, raw_path = entry.split(b"\t", 1)
        mode, middle, last = metadata.split()
        path = repository_path(raw_path)
        views.setdefault(path, {})
        if mode == b"160000":
            continue  # Gitlinks name another repository, not a blob.
        oid = last if head else middle
        if mode not in {b"100644", b"100755", b"120000"} or not OBJECT_ID.fullmatch(
            oid
        ):
            raise ValueError
        paths = blobs.setdefault(oid, {})
        paths[path] = paths.get(path, False) or mode != b"120000"


def head_entries(root: Path) -> list[bytes]:
    head = git_run(root, "rev-parse", "--verify", "-q", "HEAD")
    if head.returncode == 1:
        # An unborn branch has a symbolic HEAD but no object to enumerate.
        git_output(root, "symbolic-ref", "-q", "HEAD")
        return []
    if head.returncode:
        raise ValueError
    oid = head.stdout.strip()
    if not OBJECT_ID.fullmatch(oid):
        raise ValueError
    return git_entries(git_output(root, "ls-tree", "-rz", oid.decode("ascii")))


def blob_contents(root: Path, oids: Iterable[bytes]) -> Iterator[tuple[bytes, bytes]]:
    with subprocess.Popen(
        [*GIT, "cat-file", "--batch"],
        cwd=root,
        env=git_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as git:
        assert git.stdin is not None and git.stdout is not None
        for oid in oids:
            git.stdin.write(oid + b"\n")
            git.stdin.flush()
            match = re.fullmatch(oid + rb" blob ([0-9]+)\n", git.stdout.readline())
            if match is None:
                raise ValueError
            size = int(match[1])
            data = git.stdout.read(size)
            if len(data) != size or git.stdout.read(1) != b"\n":
                raise ValueError
            yield oid, data
        git.stdin.close()
        if git.wait():
            raise ValueError


def file_content(
    parent: int, name: str, *, read_symlink: bool = True
) -> tuple[bytes, bool] | None:
    try:
        mode = os.stat(name, dir_fd=parent, follow_symlinks=False).st_mode
        if read_symlink and stat.S_ISLNK(mode):
            return os.readlink(os.fsencode(name), dir_fd=parent), False
        if stat.S_ISREG(mode):
            fd = os.open(
                name, os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY, dir_fd=parent
            )
            with os.fdopen(fd, "rb") as file:
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    return file.read(), True
    except OSError as error:
        if error.errno not in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
            raise
    return None


def worktree_content(root: Path, path: PurePosixPath) -> tuple[bytes, bool] | None:
    # Walk through opened directories so a replaced parent cannot redirect reads.
    flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
    parent = os.open(root, flags)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        return file_content(parent, path.name)
    except OSError as error:
        if error.errno not in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
            raise
    finally:
        os.close(parent)
    return None


def add_views(
    variants: dict[str, None], path: PurePosixPath, data: bytes, regular: bool
) -> None:
    if b"\0" in data:
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    variants[text] = None
    if regular and path.suffix.lower() == ".ipynb":
        try:
            normalized = notebook_view(data).text
            normalized.encode("utf-8")
        except (ValueError, TypeError, RecursionError):
            return  # Raw text still gets scanned when the notebook is malformed.
        if "\0" not in normalized:
            variants[normalized] = None


def repository_views(root: Path, *, staged: bool) -> Views:
    views: Views = {}
    blobs: Blobs = {}
    index = git_output(
        root,
        "ls-files",
        "--stage",
        "-z",
        index_file=os.environ.get("GIT_INDEX_FILE") if staged else None,
    )
    collect_blobs(git_entries(index), views, blobs)
    if not staged:
        collect_blobs(head_entries(root), views, blobs, head=True)
        others = git_output(root, "ls-files", "--others", "--exclude-standard", "-z")
        for raw_path in git_entries(others):
            # Git lists embedded repositories as a single directory entry.
            views.setdefault(repository_path(raw_path.removesuffix(b"/")), {})
    if blobs:
        for oid, data in blob_contents(root, blobs):
            for path, regular in blobs[oid].items():
                add_views(views[path], path, data, regular)
    if not staged:
        for path, variants in views.items():
            content = worktree_content(root, path)
            if content is not None:
                add_views(variants, path, *content)
    return views


def workspace_views(root: Path) -> Iterator[Views]:
    def unreadable(error: OSError) -> None:
        raise error

    batch: Views = {}
    chars = 0
    # fwalk supplies open directory descriptors and does not follow symlinks.
    for folder, dirs, files, parent in os.fwalk(
        root, onerror=unreadable, follow_symlinks=False
    ):
        dirs[:] = [name for name in dirs if name not in {".git", ".venv"}]
        # fwalk can open directory symlinks before deciding not to follow them.
        if ".env" in dirs and stat.S_ISLNK(
            os.stat(".env", dir_fd=parent, follow_symlinks=False).st_mode
        ):
            dirs.remove(".env")
        relative = PurePosixPath(Path(folder).relative_to(root))
        for name in dirs + files:
            if name in {".git", ".env"}:
                continue
            # A non-directory .venv entry can be a dangling or file symlink.
            content = file_content(parent, name, read_symlink=name != ".venv")
            if content is None:
                continue
            path = relative / name
            variants = batch[path] = {}
            add_views(variants, path, *content)
            chars += sum(map(len, variants))
            if len(batch) >= WORKSPACE_BATCH_PATHS or chars >= WORKSPACE_BATCH_CHARS:
                yield batch
                batch = {}
                chars = 0
    if batch:
        yield batch


def scan_views(views: Views) -> dict[PurePosixPath, SecretFinding]:
    inputs = {}
    aliases = {}
    for path, variants in views.items():
        texts = iter(variants)
        inputs[path] = next(texts, "")
        # Keep each variant separate without scanning the same real path twice.
        # Git paths cannot use the .git namespace.
        for text in texts:
            alias = PurePosixPath(".git", str(len(aliases)))
            aliases[alias] = path
            inputs[alias] = text
    blocked = {}
    for scanned, finding in secret_findings(inputs).items():
        path = aliases.get(scanned, scanned)
        entry = blocked.setdefault(path, SecretFinding())
        entry.rules.update(finding.rules)
        if path == scanned:
            entry.path_spans.extend(finding.path_spans)
    return blocked


def reject_findings(blocked: dict[PurePosixPath, SecretFinding], *, scope: str) -> None:
    if not blocked:
        return
    lines = [f"{scope} secret scan found possible secrets:"]
    for path, finding in sorted(blocked.items()):
        label = redact_path(path, finding.path_spans)
        label = "".join(
            char if char.isprintable() else repr(char)[1:-1] for char in label
        )
        lines.append(f"  {label}: {', '.join(sorted(finding.rules))}")
    raise ValueError("\n".join(lines))


def verify_repository(root: Path, *, staged: bool = False) -> None:
    """Raise a safe diagnostic for possible secrets, or if scanning could not run."""
    try:
        root = root.resolve()
        if not is_git_worktree(root):
            raise ValueError
        views = repository_views(root, staged=staged)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        raise ValueError(
            "Git could not read the repository for secret scanning."
        ) from None

    try:
        blocked = scan_views(views)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise ValueError("The secret scan failed.") from None
    reject_findings(blocked, scope="Repository")


def verify_workspace(root: Path) -> None:
    """Scan files on disk independently of Git's index and ignore rules."""
    blocked = {}
    try:
        for views in workspace_views(root.resolve()):
            blocked.update(scan_views(views))
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise ValueError("The workspace secret scan could not complete.") from None
    reject_findings(blocked, scope="Workspace")
