"""YAML authoring records, revisions, validation and recoverable file saves."""

import base64
import fcntl
import hashlib
import io
import json
import os
import re
import tempfile
import warnings
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import uuid4

import yaml
from PIL import Image

from atlas import cms_notebooks as nb

SECTIONS = {
    "employment": "Employment History",
    "skills": "Skills",
    "education": "Education",
    "projects": "Projects",
}
COMMON = {
    "id",
    "status",
    "title",
    "short_description",
    "created_at",
    "updated_at",
}
FIELDS = {
    "post": COMMON
    | {
        "tags",
        "thumbnail_path",
        "source_path",
        "code_path",
        "related_post_ids",
        "source_digest",
    },
    "collection": COMMON
    | {
        "cover_path",
        "cover_caption",
        "long_description",
        "post_ids",
        "source_path",
        "source_digest",
    },
    "resume": {
        "id",
        "title",
        "section",
        "subtitle",
        "position",
        "created_at",
        "updated_at",
        "source_path",
        "source_digest",
    },
}
INTERNAL = {"internal_notes", "internal_todos"}
PROFILE = {"title", "summary"}
CONTENT_FIELDS = {
    "collection": ("title", "short_description", "long_description", "cover_caption"),
    "resume": ("title", "subtitle", "body"),
}
CONTENT_DEFAULTS = {"collection": {"cover_caption": ""}}


class Conflict(ValueError):
    """A caller's loaded revision is no longer current."""


class NotFound(ValueError):
    """A requested record does not exist."""


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError(f"Duplicate or invalid YAML field: {key!r}")
        result[key] = loader.construct_object(value_node)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or uuid4().hex[:12]


def split_document(raw: str) -> tuple[dict, str]:
    raw = raw.replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)(.*)\Z", raw, re.S)
    if not match:
        raise ValueError("Expected Markdown with YAML front matter.")
    meta = yaml.load(match[1], Loader=StrictLoader)
    if not isinstance(meta, dict):
        raise ValueError("Front matter must be a mapping.")
    return meta, match[2].strip("\n")


def document(meta: dict, body: str = "") -> bytes:
    return (
        "---\n"
        + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
        + "---\n\n"
        + body
        + "\n"
    ).encode()


def decode(raw: bytes) -> dict:
    value = yaml.load(raw.decode(), Loader=StrictLoader)
    if not isinstance(value, dict):
        raise ValueError("Expected a YAML mapping.")
    return value


class AuthoringDumper(yaml.SafeDumper):
    pass


def _string(dumper, value):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None
    )


AuthoringDumper.add_representer(str, _string)


def encode(record: dict) -> bytes:
    return yaml.dump(
        record, Dumper=AuthoringDumper, sort_keys=False, allow_unicode=True, width=100
    ).encode()


def normalized_tags(values: list) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("Tags must be a list.")
    result = []
    for item in values:
        if (
            not isinstance(item, str)
            or not item.strip()
            or any(c in item for c in ",\r\n")
        ):
            raise ValueError(
                "Tags must be nonempty labels without commas or line breaks."
            )
        item = item.strip()
        if item not in result:
            result.append(item)
    return result


def duplicate_sources(records: list[dict]) -> dict[str, list[str]]:
    """Map notebook source paths shared by more than one post to their IDs."""
    owners: dict[str, list[str]] = {}
    for record in records:
        if record["id"].startswith("post/"):
            owners.setdefault(record["source_path"], []).append(record["id"])
    return {path: ids for path, ids in owners.items() if len(ids) > 1}


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, relative: str) -> Path:
        if not isinstance(relative, str):
            raise ValueError("Paths must be relative text strings.")
        p = PurePosixPath(relative)
        if not relative or p.is_absolute() or ".." in p.parts or "\\" in relative:
            raise ValueError(f"Expected a safe relative path: {relative!r}")
        path = self.root.joinpath(*p.parts)
        for parent in (path, *path.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                raise ValueError(f"Symlink paths are unsupported: {relative}")
        return path

    def record_path(self, identity: str) -> Path:
        if not re.fullmatch(r"(post|collection|resume)/[a-z0-9][a-z0-9-]*", identity):
            raise ValueError("Use an exact ID such as post/attention or resume/afni.")
        kind, key = identity.split("/")
        directory = {"post": "posts", "collection": "collections", "resume": "resume"}[
            kind
        ]
        return self.path(f"backend/{directory}/{key}.yaml")

    def record_bytes(self, record: dict) -> bytes:
        """Persist CLI bookkeeping separately from editable source fields."""
        authored = CONTENT_FIELDS.get(record["id"].split("/")[0], ())
        return encode(
            {key: value for key, value in record.items() if key not in authored}
        )

    def content_bytes(self, record: dict) -> bytes:
        kind = record["id"].split("/")[0]
        defaults = CONTENT_DEFAULTS.get(kind, {})
        return encode(
            {
                key: record[key]
                for key in CONTENT_FIELDS[kind]
                if key not in defaults or record[key] != defaults[key]
            }
        )

    def prepare_content(self, record: dict) -> tuple[Path, bytes]:
        kind, key = record["id"].split("/")
        for field, default in CONTENT_DEFAULTS.get(kind, {}).items():
            record.setdefault(field, default)
        directory = {"collection": "collections", "resume": "resume"}[kind]
        relative = f"content/{directory}/{key}.yaml"
        raw = self.content_bytes(record)
        record.update(source_path=relative, source_digest=digest(raw))
        return self.path(relative), raw

    @contextmanager
    def lock(self):
        lock_path = self.path(".atlas/cms/writer.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                self.recover()
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _install(self, path: Path, raw: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".cms-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def recover(self):
        pending = self.path(".atlas/cms/pending.json")
        if not pending.exists():
            return
        entries = json.loads(pending.read_text())
        for entry in entries:
            target = self.path(entry["path"])
            current = target.read_bytes() if target.exists() else None
            before = (
                base64.b64decode(entry["before"])
                if entry["before"] is not None
                else None
            )
            after = (
                base64.b64decode(entry["after"]) if entry["after"] is not None else None
            )
            if current not in (before, after):
                raise Conflict(
                    f"Interrupted save conflicts with {entry['path']}; preserve pending.json for repair."
                )
        for entry in entries:
            target = self.path(entry["path"])
            if entry["after"] is None:
                target.unlink(missing_ok=True)
            else:
                self._install(target, base64.b64decode(entry["after"]))
        pending.unlink()

    def preserve(self, relative: str, raw: bytes) -> Path:
        """Save a recovery copy independently of the canonical save journal."""
        path = self.path(f".atlas/cms/{relative}")
        self._install(path, raw)
        return path

    def commit(self, changes: dict[Path, bytes | None]):
        entries = []
        for path, raw in changes.items():
            relative = path.relative_to(self.root).as_posix()
            self.path(relative)
            old = path.read_bytes() if path.exists() else None
            if old == raw:
                continue
            entries.append(
                {
                    "path": relative,
                    "before": (
                        base64.b64encode(old).decode() if old is not None else None
                    ),
                    "after": (
                        base64.b64encode(raw).decode() if raw is not None else None
                    ),
                }
            )
        if entries:
            self._install(
                self.path(".atlas/cms/pending.json"), json.dumps(entries).encode()
            )
            self.recover()

    def require_initialized(self):
        marker = self.path("backend/cms.yaml")
        if not marker.exists():
            raise ValueError("Run 'at cms init' to initialize this workspace.")
        if decode(marker.read_bytes()) != {"schema": 3}:
            raise ValueError("Unsupported or malformed CMS schema.")
        path = self.path("content/resume.yaml")
        if not path.exists():
            raise ValueError("Run 'at cms init' first.")
        profile = decode(path.read_bytes())
        if set(profile) != PROFILE:
            raise ValueError("Unsupported or malformed CMS profile.")
        if (
            not isinstance(profile["title"], str)
            or not profile["title"].strip()
            or not isinstance(profile["summary"], str)
        ):
            raise ValueError("Résumé title and summary must be text.")

    def get(self, identity: str) -> dict:
        self.require_initialized()
        path = self.record_path(identity)
        if not path.exists():
            raise NotFound(f"Unknown record: {identity}")
        raw = path.read_bytes()
        record = decode(raw)
        if record.get("id") != identity:
            raise ValueError(
                f"Record identity does not match its filename: {path.name}"
            )
        kind = identity.split("/")[0]
        authored = CONTENT_FIELDS.get(kind, ())
        if any(key in record for key in authored):
            raise ValueError(
                f"Editable fields for {identity} belong in its content/ source."
            )
        revision_raw = raw
        if authored:
            source_raw = self.path(record.get("source_path")).read_bytes()
            content = CONTENT_DEFAULTS.get(kind, {}) | decode(source_raw)
            if set(content) != set(authored):
                raise ValueError(
                    f"Expected only {', '.join(authored)} in {record['source_path']}."
                )
            record.update(content)
            revision_raw += b"\0" + source_raw
        self.validate(record)
        return {"record": record, "revision": digest(revision_raw)}

    def ls(self, kind: str) -> list[dict]:
        directory = self.record_path(f"{kind}/placeholder").parent
        self.require_initialized()
        records = [
            self.get(f"{kind}/{path.stem}") for path in sorted(directory.glob("*.yaml"))
        ]
        if kind == "resume":
            records.sort(
                key=lambda item: (
                    list(SECTIONS).index(item["record"]["section"]),
                    item["record"]["position"],
                    item["record"]["id"],
                )
            )
        return records

    def validate(self, record: dict):
        kind = record["id"].split("/")[0]
        self.record_path(record["id"])
        extra = {"body"} if kind == "resume" else INTERNAL
        required = FIELDS[kind] | extra
        if set(record) != required:
            raise ValueError(
                f"Missing/unknown fields for {record['id']}: {sorted(set(record) ^ required)}"
            )
        for key in ("title", "created_at", "updated_at"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError(f"{key} must be nonempty text.")
        if any(character in record["title"] for character in "\r\n"):
            raise ValueError("Title must be single-line text.")
        for key in ("created_at", "updated_at"):
            value = datetime.fromisoformat(record[key])
            if value.tzinfo is None:
                raise ValueError(f"{key} must include a timezone.")
        self.path(record["source_path"])
        extension = ".ipynb" if kind == "post" else ".yaml"
        if not record["source_path"].endswith(extension):
            raise ValueError(f"{kind} source must be a {extension} file.")
        if not isinstance(record["source_digest"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", record["source_digest"]
        ):
            raise ValueError("Invalid source digest.")
        if kind == "resume":
            if (
                not isinstance(record["section"], str)
                or record["section"] not in SECTIONS
                or type(record["position"]) is not int
                or record["position"] < 0
            ):
                raise ValueError("Invalid résumé section or position.")
            if not all(isinstance(record[key], str) for key in ("subtitle", "body")):
                raise ValueError("Résumé text must be strings.")
            return
        if record["status"] not in ("draft", "published"):
            raise ValueError("Status must be draft or published.")
        if not all(
            isinstance(record[key], str)
            for key in ("short_description", "internal_notes")
        ):
            raise ValueError("Descriptions and notes must be text.")
        todos = record["internal_todos"]
        if not isinstance(todos, list):
            raise ValueError("To-dos must be a list.")
        for todo in todos:
            if (
                not isinstance(todo, dict)
                or set(todo) != {"text", "done"}
                or not isinstance(todo["text"], str)
                or not todo["text"].strip()
                or any(c in todo["text"] for c in "\r\n")
                or type(todo["done"]) is not bool
            ):
                raise ValueError(
                    "Each to-do needs nonempty single-line text and a boolean done value."
                )
        image = record["thumbnail_path" if kind == "post" else "cover_path"]
        if image is not None:
            self.path(image)
        links = record["related_post_ids" if kind == "post" else "post_ids"]
        if (
            not isinstance(links, list)
            or any(not isinstance(item, str) for item in links)
            or len(links) != len(set(links))
        ):
            raise ValueError(
                "Post references must be an ordered list without duplicates."
            )
        for identity in links:
            if not identity.startswith("post/") or identity == record["id"]:
                raise ValueError("References must name other posts.")
            self.record_path(identity)
        if kind == "post":
            if record["tags"] != normalized_tags(record["tags"]):
                raise ValueError("Tags must be normalized.")
            if record["code_path"] is not None:
                self.path(record["code_path"])
        else:
            if not isinstance(record["long_description"], str):
                raise ValueError("Collection introduction must be text.")
            if not isinstance(record["cover_caption"], str) or any(
                character in record["cover_caption"] for character in "\r\n"
            ):
                raise ValueError("Cover caption must be single-line Markdown text.")

    def references(self, record: dict):
        links = record.get("related_post_ids", record.get("post_ids", []))
        for identity in links:
            self.get(identity)

    def check_revision(self, loaded: dict, expected: str | None):
        if expected is not None and expected != loaded["revision"]:
            raise Conflict(
                "Stale revision; reload the record and review your edit before saving."
            )

    def image(self, filename: Path, *, allow_svg: bool = False) -> tuple[str, bytes]:
        """Read and verify an image without modifying or re-encoding its bytes."""
        filename = filename.expanduser()
        raw = filename.read_bytes()
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("Images must be at most 20 MiB.")
        if allow_svg and filename.suffix.lower() == ".svg":
            try:
                root = ET.fromstring(raw)
            except ET.ParseError as error:
                raise ValueError("Invalid SVG image.") from error
            if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
                raise ValueError("Expected an SVG document with an svg root element.")
            return f"content/images/{digest(raw)}.svg", raw
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                extension = {
                    "PNG": "png",
                    "JPEG": "jpg",
                    "WEBP": "webp",
                    "GIF": "gif",
                }.get(image.format)
                if extension is None:
                    raise ValueError("Use a PNG, JPEG, WebP or GIF image.")
                image.verify()
        return f"content/images/{digest(raw)}.{extension}", raw

    def ready(self, record: dict):
        kind = record["id"].split("/")[0]
        if not record["short_description"].strip():
            raise ValueError("A short description is required to publish.")
        image = record["thumbnail_path" if kind == "post" else "cover_path"]
        if not image:
            raise ValueError("A thumbnail/cover is required to publish.")
        self.image(self.path(image))
        if kind == "post":
            value = nb.load(self.path(record["source_path"]).read_bytes())
            if not any(nb.source(item).strip() for item in value["cells"]):
                raise ValueError(
                    "A notebook with meaningful content is required to publish."
                )
        else:
            if not record["long_description"].strip():
                raise ValueError("A collection introduction is required to publish.")
            if not any(
                self.get(identity)["record"]["status"] == "published"
                for identity in record["post_ids"]
            ):
                raise ValueError(
                    "A collection needs at least one published member to publish."
                )

    def new(self, kind: str, title: str, **fields) -> dict:
        allowed = {
            "post": {"short_description", "tags", "code_path"},
            "collection": {
                "short_description",
                "long_description",
                "cover_caption",
                "post_ids",
            },
            "resume": {"section", "subtitle", "body"},
        }
        if kind not in allowed or not set(fields) <= allowed[kind]:
            raise ValueError("Unknown or system-managed creation field.")
        with self.lock():
            self.require_initialized()
            key = slug(title)
            identity = f"{kind}/{key}"
            if self.record_path(identity).exists():
                identity += "-" + uuid4().hex[:8]
            timestamp = now()
            record = {
                "id": identity,
                "title": title,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            changes = {}
            if kind == "resume":
                section = fields.get("section", "employment")
                position = 1 + max(
                    (
                        item["record"]["position"]
                        for item in self.ls("resume")
                        if item["record"]["section"] == section
                    ),
                    default=-1,
                )
                record.update(section=section, position=position, subtitle="", body="")
            else:
                record.update(
                    status="draft",
                    short_description="",
                    internal_notes="",
                    internal_todos=[],
                )
                if kind == "post":
                    raw = nb.dump(nb.notebook())
                    source_path = f"content/posts/{identity.split('/')[1]}.ipynb"
                    if self.path(source_path).exists():
                        raise ValueError(f"Notebook already exists: {source_path}")
                    record.update(
                        tags=[],
                        thumbnail_path=None,
                        source_path=source_path,
                        code_path=None,
                        related_post_ids=[],
                        source_digest=digest(raw),
                    )
                    changes[self.path(source_path)] = raw
                else:
                    record.update(cover_path=None, long_description="", post_ids=[])
            record.update(fields)
            if kind in CONTENT_FIELDS:
                source_path, source_raw = self.prepare_content(record)
                if source_path.exists():
                    raise ValueError(
                        f"Content source already exists: {record['source_path']}"
                    )
                changes[source_path] = source_raw
            self.validate(record)
            self.references(record)
            changes[self.record_path(identity)] = self.record_bytes(record)
            self.commit(changes)
            return self.get(identity)

    def update(
        self,
        identity: str,
        patch: dict,
        expected: str | None = None,
        image: Path | None = None,
    ) -> dict:
        with self.lock():
            loaded = self.get(identity)
            self.check_revision(loaded, expected)
            old = loaded["record"]
            kind = identity.split("/")[0]
            forbidden = {
                "id",
                "created_at",
                "updated_at",
                "source_digest",
                "source_path",
            }
            if set(patch) & forbidden or not set(patch) <= set(old):
                raise ValueError("Unknown or system-managed field in patch.")
            record = old | patch
            if "tags" in patch:
                record["tags"] = normalized_tags(patch["tags"])
            if kind == "resume" and record["section"] != old["section"]:
                record["position"] = 1 + max(
                    (
                        item["record"]["position"]
                        for item in self.ls("resume")
                        if item["record"]["section"] == record["section"]
                    ),
                    default=-1,
                )
            changes = {}
            if image is not None:
                if kind == "resume":
                    raise ValueError("Résumé entries do not have images.")
                relative, raw = self.image(image)
                changes[self.path(relative)] = raw
                record["thumbnail_path" if kind == "post" else "cover_path"] = relative
            self.validate(record)
            if "related_post_ids" in patch or "post_ids" in patch:
                self.references(record)
            if patch.get("status") == "published":
                self.ready(record)
            if record == old:
                # Importing the same image can restore missing managed bytes
                # without changing public metadata or its modification date.
                self.commit(changes)
                return loaded
            if any(record[key] != old[key] for key in CONTENT_FIELDS.get(kind, ())):
                source_raw = self.content_bytes(record)
                changes[self.path(record["source_path"])] = source_raw
                record["source_digest"] = digest(source_raw)
            if any(record[key] != old[key] for key in record.keys() - INTERNAL):
                record["updated_at"] = now()
            if kind == "resume" and record["section"] != old["section"]:
                remaining = [
                    item["record"]
                    for item in self.ls("resume")
                    if item["record"]["section"] == old["section"]
                    and item["record"]["id"] != identity
                ]
                for position, entry in enumerate(remaining):
                    if entry["position"] != position:
                        entry.update(position=position, updated_at=now())
                        changes[self.record_path(entry["id"])] = self.record_bytes(
                            entry
                        )
            # Publication is a deliberate transition. Other public edits can make
            # a published record unready; release validation catches that state.
            changes[self.record_path(identity)] = self.record_bytes(record)
            self.commit(changes)
            return self.get(identity)

    def write_notebook(
        self,
        identity: str,
        raw: bytes,
        expected: str,
        source_revision: str,
        *,
        images: dict[str, bytes] | None = None,
    ) -> dict:
        nb.load(raw)
        with self.lock():
            loaded = self.get(identity)
            self.check_revision(loaded, expected)
            record = loaded["record"]
            path = self.path(record["source_path"])
            current = path.read_bytes()
            if digest(current) != source_revision:
                raise Conflict(
                    "Notebook changed while editing; your edit has not been saved."
                )
            changes = {}
            for relative, image_raw in (images or {}).items():
                if not PurePosixPath(relative).is_relative_to("content/images"):
                    raise ValueError("Notebook images must be under content/images/.")
                image_path = self.path(relative)
                if image_path.exists() and image_path.read_bytes() != image_raw:
                    raise Conflict(f"Image already exists: {relative}")
                changes[image_path] = image_raw
            if nb.load(current) == nb.load(raw):
                self.commit(changes)
                return loaded
            record.update(source_digest=digest(raw), updated_at=now())
            changes.update(
                {path: raw, self.record_path(identity): self.record_bytes(record)}
            )
            self.commit(changes)
            return self.get(identity)
