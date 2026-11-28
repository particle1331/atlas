import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

import pytest
from PIL import Image
from typer.testing import CliRunner

from atlas import cms_notebooks as nb
from atlas.cli import app
from atlas.cms_site import generate, initialize
from atlas.cms_store import (
    Conflict,
    Store,
    decode,
    digest,
    document,
    encode,
    split_document,
)
from atlas.notebook_ops import figure


@pytest.fixture(autouse=True)
def without_quarto(tmp_path, monkeypatch):
    monkeypatch.setenv("QUARTO", str(tmp_path / "unavailable-quarto"))


@pytest.fixture
def workspace(tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "posts").mkdir(parents=True)
    (frontend / "collections").mkdir()
    (frontend / "_quarto.yml").write_text(
        "project:\n  type: website\nexecute:\n  enabled: false\n"
    )
    (frontend / "_quarto-preview.yml").write_text(
        "project:\n  output-dir: _site-preview\nwebsite:\n  draft-mode: visible\n"
    )
    for page in ("posts", "collections"):
        (frontend / f"{page}.qmd").write_bytes(
            document(
                {"title": page, "listing": {"contents": f"{page}/*.qmd"}}, "Listing."
            )
        )
    (frontend / "posts/example.qmd").write_bytes(
        document(
            {
                "title": "Example",
                "description": "Sample",
                "date": "2026-10-28",
                "categories": ["Python"],
            },
            "## Original body\n\nWrite freely.",
        )
    )
    (frontend / "collections/guide.qmd").write_bytes(
        document(
            {"title": "Guide", "description": "An ordered guide"},
            "Introduction.\n\n## Contents\n\n1. [Example](../posts/example.qmd)",
        )
    )
    (frontend / "resume.qmd").write_bytes(
        document(
            {"title": "My résumé"},
            '::: {.resume-summary}\nOriginal summary.\n <a href="assets/resume.pdf">PDF</a>\n:::\n\n## Employment History\n\n### Engineer · Example\n*2020 -- Present*\n\n- Built useful things.\n\n## Skills\n\n**Python**\n\n- Data and systems.\n\n## Education\n\n### University\n*Mathematics*\n\nA degree.\n\n<script src="assets/contact.js"></script>',
        )
    )
    return Store(tmp_path)


@pytest.fixture
def store(workspace):
    initialize(workspace)
    return workspace


def invoke(store, *args, input=None, code=0):
    result = CliRunner().invoke(
        app, ["cms", "--root", str(store.root), *args], input=input
    )
    assert result.exit_code == code, (result.output, result.exception)
    return result


def run(store, *args, **kwargs):
    return json.loads(invoke(store, *args, **kwargs).stdout)


def notebook_invoke(store, *args, input=None, code=0):
    result = CliRunner().invoke(
        app, ["notebook", "--root", str(store.root), *args], input=input
    )
    assert result.exit_code == code, (result.output, result.exception)
    return result


def new_post(store, title="Attention"):
    return run(
        store,
        "post",
        "new",
        title,
        "--description",
        "An explanation",
        "--tags",
        " python ,Python,python ",
    )


@pytest.mark.parametrize(
    ("kind", "projected"),
    [("post", "posts/attention.ipynb"), ("collection", "collections/attention.qmd")],
)
def test_new_renders_draft_preview_and_keeps_stdout_as_json(
    store, monkeypatch, kind, projected
):
    from atlas import cms

    calls = []

    def quarto(args, cwd, *, stdout):
        assert stdout is sys.stderr
        calls.append(args)
        if "--to" in args:
            Path(args[2]).with_suffix(".pdf").write_bytes(b"%PDF-1.7\n")
        else:
            assert cwd == store.root
            assert store.path(f"frontend/{projected}").is_file()
            assert store.path("frontend/assets/resume.pdf").is_file()
            print("Preview rendered", file=stdout)
        return 0

    monkeypatch.setattr(cms.shutil, "which", lambda _: "/bin/quarto")
    monkeypatch.setattr(cms.subprocess, "call", quarto)
    result = invoke(store, kind, "new", "Attention")

    created = json.loads(result.stdout)
    assert created == store.get(f"{kind}/attention")
    assert created["record"]["status"] == "draft"
    assert calls[0][-3:] == ["--to", "typst", "--no-execute"]
    assert calls[1] == [
        "/bin/quarto",
        "render",
        str(store.path("frontend")),
        "--no-execute",
        "--profile",
        "preview",
        "--output-dir",
        "_site-preview",
    ]
    assert "Preview rendered" in result.stderr


@pytest.mark.parametrize("failure", ["missing-quarto", "render"])
def test_new_preserves_saved_draft_when_preview_refresh_fails(
    store, monkeypatch, failure
):
    from atlas import cms

    if failure == "render":
        monkeypatch.setattr(cms.shutil, "which", lambda _: "/bin/quarto")
        monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: None)
        monkeypatch.setattr(cms.subprocess, "call", lambda *_, **__: 7)
    result = invoke(store, "post", "new", "Attention")

    assert json.loads(result.stdout) == store.get("post/attention")
    assert "Created post/attention. Preview refresh failed" in result.stderr
    assert (
        "Install Quarto" if failure == "missing-quarto" else "exited with status 7"
    ) in result.stderr


def test_new_leaves_rendering_to_an_active_live_preview(store):
    from atlas import cms

    with cms.site_lock(store, "live-preview"):
        result = invoke(store, "collection", "new", "Attention")

    assert json.loads(result.stdout) == store.get("collection/attention")
    assert result.stderr == ""
    assert not store.path("frontend/collections/attention.qmd").exists()


@pytest.mark.parametrize("kind, missing_code", [("post", 4), ("collection", 2)])
def test_cms_open_launches_the_recorded_source_and_metadata(
    store, monkeypatch, kind, missing_code
):
    from atlas import cms

    record = run(store, kind, "new", "Attention")["record"]
    identity = record["id"]
    source = store.path(record["source_path"])
    renamed = source.rename(source.with_name(f"Custom source{source.suffix}"))
    record_path = store.record_path(identity)
    raw = decode(record_path.read_bytes())
    raw["source_path"] = renamed.relative_to(store.root).as_posix()
    record_path.write_bytes(encode(raw))
    calls = []

    def launch(command):
        calls.append(command)
        return 0

    monkeypatch.setattr(cms.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(cms.subprocess, "call", launch)

    invoke(store, "open", identity)
    metadata = store.path(f"content/{kind}s/attention.yaml")
    assert calls == [["/bin/code", str(renamed), str(metadata)]]

    renamed.unlink()
    result = invoke(store, "open", identity, code=missing_code)
    assert renamed.name in result.stderr
    assert len(calls) == 1


def publish(store, identity):
    image = store.root / "thumbnail.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    notebook_invoke(
        store,
        "edit-cell",
        identity,
        "--index",
        "0",
        "--file",
        "-",
        input="## Explanation\n\nMeaningful prose.",
    )
    run(store, "post", "edit", identity, "--thumbnail", str(image))
    return run(store, "post", "publish", identity)


def test_initialization_imports_yaml_and_bare_notebooks_once(workspace):
    result = run(workspace, "init")
    assert result["imported"] == {"post": 1, "collection": 1, "resume": 3}
    post = workspace.get("post/example")["record"]
    assert post["status"] == "published"
    assert post["thumbnail_path"] is None
    assert post["tags"] == ["Python"]
    raw = workspace.path("content/posts/example.ipynb").read_bytes()
    assert nb.source(nb.load(raw)["cells"][0]) == "## Original body\n\nWrite freely."
    assert workspace.path("backend/posts/example.yaml").exists()
    assert decode(workspace.path("content/posts/example.yaml").read_bytes()) == {
        "title": "Example",
        "short_description": "Sample",
        "tags": ["Python"],
    }
    assert not {"title", "short_description", "tags"} & set(
        decode(workspace.path("backend/posts/example.yaml").read_bytes())
    )
    assert workspace.path("backend/collections/guide.yaml").exists()
    assert workspace.path("backend/cms.yaml").exists()
    assert workspace.path("content/collections/guide.yaml").exists()
    assert "long_description" not in decode(
        workspace.path("content/collections/guide.yaml").read_bytes()
    )
    assert workspace.path("content/collections/guide.md").read_text() == "Introduction."
    assert (
        workspace.get("collection/guide")["record"]["source_path"]
        == "content/collections/guide.md"
    )
    assert workspace.path("content/resume.yaml").exists()
    assert not workspace.path("frontend/posts/example.qmd").exists()
    assert run(workspace, "init")["changed"] is False


def test_direct_collection_and_resume_edits_are_observed_without_rewriting_content(
    store,
):
    collection_id = "collection/guide"
    resume_id = "resume/employment-engineer-example"
    previous = {
        identity: store.get(identity) for identity in (collection_id, resume_id)
    }
    edited = {
        "content/collections/guide.yaml": b"# Editable collection text\ntitle: Hand-edited guide\nshort_description: A new summary\n",
        "content/collections/guide.md": b"Hand-edited introduction.\n",
        "content/resume/employment-engineer-example.yaml": b"# Editable resume text\ntitle: Hand-edited role\nsubtitle: 2026 -- Present\nbody: |\n  - A hand-edited accomplishment.\n",
        "content/resume.yaml": b"title: Hand-edited resume\nsummary: A hand-edited summary.\n",
    }
    for relative, raw in edited.items():
        store.path(relative).write_bytes(raw)
    with pytest.raises(Conflict):
        store.update(
            collection_id, {"post_ids": []}, previous[collection_id]["revision"]
        )
    generate(store, preview=True)
    for identity in (collection_id, resume_id):
        current = store.get(identity)["record"]
        assert current["updated_at"] != previous[identity]["record"]["updated_at"]
        assert current["source_digest"] == digest(
            store.path(current["source_path"]).read_bytes()
        )
        if identity == collection_id:
            assert current["metadata_digest"] == digest(
                store.path("content/collections/guide.yaml").read_bytes()
            )
    assert (
        "Hand-edited introduction"
        in store.path("frontend/collections/guide.qmd").read_text()
    )
    assert "Hand-edited role" in store.path("frontend/resume.qmd").read_text()
    assert "A hand-edited summary" in store.path("frontend/resume.qmd").read_text()
    observed = {
        identity: store.get(identity) for identity in (collection_id, resume_id)
    }
    generate(store, preview=True)
    assert all(store.get(identity) == observed[identity] for identity in observed)
    assert all(
        store.path(relative).read_bytes() == raw for relative, raw in edited.items()
    )


def test_failed_import_preserves_original_files(workspace):
    resume = workspace.path("frontend/resume.qmd")
    resume.write_text(resume.read_text() + "\n## Unknown\n\nDo not lose this.\n")
    original = workspace.path("frontend/posts/example.qmd").read_bytes()
    invoke(workspace, "init", code=2)
    assert not workspace.path("content/resume.yaml").exists()
    assert not workspace.path("content/posts/example.ipynb").exists()
    assert workspace.path("frontend/posts/example.qmd").read_bytes() == original


def test_resume_import_keeps_entries_with_repeated_headings(workspace):
    resume = workspace.path("frontend/resume.qmd")
    resume.write_text(
        resume.read_text().replace(
            "## Skills",
            "### Engineer · Example\n*2015 -- 2020*\n\n- An earlier role.\n\n## Skills",
        )
    )
    initialize(workspace)
    entries = [
        item["record"]
        for item in workspace.ls("resume")
        if item["record"]["section"] == "employment"
    ]
    assert len(entries) == 2
    assert entries[0]["id"] != entries[1]["id"]
    assert "Built useful" in entries[0]["body"]
    assert "An earlier role" in entries[1]["body"]


def test_post_creation_and_renaming_keep_identity_and_source(store):
    created = new_post(store)
    assert created["record"]["id"] == "post/attention"
    assert created["record"]["tags"] == ["python", "Python"]
    path = store.path("content/posts/attention.ipynb")
    original = path.read_bytes()
    changed = run(store, "post", "edit", "post/attention", "--title", "New title")
    assert changed["record"]["id"] == "post/attention"
    assert changed["record"]["source_path"] == "content/posts/attention.ipynb"
    assert path.read_bytes() == original
    assert decode(store.path("content/posts/attention.yaml").read_bytes()) == {
        "title": "New title",
        "short_description": "An explanation",
        "tags": ["python", "Python"],
    }
    assert changed["record"]["metadata_digest"] == digest(
        store.path("content/posts/attention.yaml").read_bytes()
    )
    assert changed["record"]["source_digest"] == created["record"]["source_digest"]
    assert new_post(store)["record"]["id"] != "post/attention"
    invoke(store, "post", "edit", "post/attention", "--tags", "a,,b", code=2)


@pytest.mark.parametrize("preview", [False, True])
def test_direct_post_yaml_edits_are_observed_without_rewriting_sources(store, preview):
    created = publish(store, new_post(store)["record"]["id"])
    path = store.path("content/posts/attention.yaml")
    notebook = store.path(created["record"]["source_path"])
    notebook_bytes = notebook.read_bytes()
    raw = (
        b"# Keep my comments and formatting\n"
        b"title: Hand-edited title\nshort_description: A hand-edited summary.\n"
        b"tags: [' python ', hand-edited, python]\n"
    )
    path.write_bytes(raw)
    edited = run(store, "post", "show", "post/attention")
    assert edited["record"]["title"] == "Hand-edited title"
    assert edited["record"]["tags"] == ["python", "hand-edited"]
    assert edited["record"]["status"] == "published"
    assert edited["revision"] != created["revision"]
    with pytest.raises(Conflict):
        store.update("post/attention", {"title": "Stale title"}, created["revision"])
    with pytest.raises(Conflict):
        store.write_notebook(
            "post/attention",
            notebook_bytes,
            created["revision"],
            digest(notebook_bytes),
        )
    generate(store, preview=preview)
    observed = store.get("post/attention")
    assert observed["record"]["updated_at"] != created["record"]["updated_at"]
    assert observed["record"]["metadata_digest"] == digest(raw)
    assert observed["record"]["source_digest"] == digest(notebook_bytes)
    projected = store.path("frontend/posts/attention.ipynb")
    meta, _ = split_document(nb.source(nb.load(projected.read_bytes())["cells"][0]))
    assert meta["title"] == "Hand-edited title"
    assert meta["description"] == "A hand-edited summary."
    assert meta["categories"] == ["python", "hand-edited"]
    assert not store.path("frontend/posts/attention.yaml").exists()
    before = projected.read_bytes()
    generate(store, preview=preview)
    assert store.get("post/attention") == observed
    assert projected.read_bytes() == before
    assert path.read_bytes() == raw
    assert notebook.read_bytes() == notebook_bytes


def test_cli_bookkeeping_preserves_direct_post_yaml_edits(store):
    new_post(store)
    path = store.path("content/posts/attention.yaml")
    raw = b"# My formatting\ntitle: My title\nshort_description: My summary\ntags: [new]\n"
    path.write_bytes(raw)
    edited = store.get("post/attention")
    run(store, "notes", "post/attention", "--file", "-", input="Private notes")
    assert path.read_bytes() == raw
    store.path("examples").mkdir()
    run(store, "post", "edit", "post/attention", "--code-path", "examples")
    assert path.read_bytes() == raw
    changed = store.update("post/attention", {"short_description": "CLI summary"})
    assert changed["record"]["title"] == "My title"
    assert changed["record"]["tags"] == ["new"]
    assert changed["record"]["metadata_digest"] == digest(path.read_bytes())
    assert changed["record"]["source_digest"] == edited["record"]["source_digest"]
    assert decode(path.read_bytes())["short_description"] == "CLI summary"


@pytest.mark.parametrize("regular_file", [False, True])
def test_post_edit_rejects_invalid_code_path_without_saving(store, regular_file):
    created = new_post(store)
    if regular_file:
        store.path("example.py").write_text("# not a directory\n")
    error = invoke(
        store, "post", "edit", "post/attention", "--code-path", "example.py", code=2
    )
    assert "code_path must be an existing directory" in error.output
    assert store.get("post/attention") == created


@pytest.mark.parametrize(
    "path", [".", "backend/posts", "content/posts", "frontend/posts"]
)
def test_post_rejects_code_path_that_exposes_cms_sources(store, path):
    created = new_post(store)
    error = invoke(store, "post", "edit", "post/attention", "--code-path", path, code=2)
    assert "code_path must not overlap CMS" in error.output
    assert store.get("post/attention") == created


@pytest.mark.parametrize("published", [False, True])
def test_missing_saved_code_path_blocks_check_and_sync_until_cleared(store, published):
    new_post(store)
    project = store.path("projects/demo")
    project.mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    if published:
        publish(store, "post/attention")
    project.rmdir()

    issues = run(store, "check", code=1)["diagnostics"]
    assert any(
        issue["id"] == "post/attention"
        and "code_path must be an existing directory" in issue["message"]
        for issue in issues
    )
    # Select the post in either preview or public mode.
    options = [] if published else ["--preview"]
    assert "projects/demo" in invoke(store, "sync", *options, code=2).output
    cleared = run(store, "post", "edit", "post/attention", "--code-path", "")
    assert cleared["record"]["code_path"] is None
    run(store, "sync", *options)


@pytest.mark.parametrize(
    "raw",
    [
        b"title: [broken",
        b"title: Title\ntitle: Duplicate\nshort_description: Summary\ntags: []\n",
        b"title: Title\nshort_description: Summary\n",  # Missing tags.
        b"title: Title\nshort_description: Summary\ntags: []\nstatus: published\n",
        b"title: 123\nshort_description: Summary\ntags: []\n",
        b"title: Title\nshort_description: null\ntags: []\n",
        b"title: Title\nshort_description: Summary\ntags: python\n",
        b"title: Title\nshort_description: Summary\ntags: [123]\n",
        None,
    ],
)
def test_invalid_direct_post_yaml_does_not_overwrite_sources_or_projection(store, raw):
    new_post(store)
    generate(store, preview=True)
    path = store.path("content/posts/attention.yaml")
    if raw is None:
        path.unlink()
    else:
        path.write_bytes(raw)
    backend = store.record_path("post/attention")
    projection = store.path("frontend/posts/attention.ipynb")
    before = backend.read_bytes(), projection.read_bytes()
    invoke(store, "sync", "--preview", code=2)
    invoke(store, "post", "edit", "post/attention", "--title", "Do not erase", code=2)
    assert (backend.read_bytes(), projection.read_bytes()) == before
    assert (path.read_bytes() if path.exists() else None) == raw


def legacy_collections(store, schema=4):
    """Construct collection YAML with an embedded introduction for upgrade tests."""
    records = [item["record"] for item in store.ls("collection")]
    for record in records:
        record.pop("metadata_digest")
        path, _ = store.content_source(record)
        raw = encode(
            {
                key: record[key]
                for key in (
                    "title",
                    "short_description",
                    "long_description",
                    "cover_caption",
                )
                if key != "cover_caption" or record[key]
            }
        )
        path.write_bytes(raw)
        store.path(record["source_path"]).unlink()
        record.update(
            source_path=path.relative_to(store.root).as_posix(),
            source_digest=digest(raw),
        )
        store.record_path(record["id"]).write_bytes(store.record_bytes(record))
    store.path("backend/cms.yaml").write_bytes(encode({"schema": schema}))
    return records


def legacy_posts(store):
    """Construct the previous on-disk layout for migration tests."""
    records = [item["record"] for item in store.ls("post")]
    for record in records:
        record.pop("metadata_digest")
        store.record_path(record["id"]).write_bytes(encode(record))
        store.content_source(record)[0].unlink()
    legacy_collections(store, schema=3)
    return records


def test_init_migrates_post_metadata_without_changing_identity_dates_or_notebooks(
    store,
):
    new_post(store)
    publish(store, "post/attention")
    originals = legacy_posts(store)
    sources = {
        r["source_path"]: store.path(r["source_path"]).read_bytes() for r in originals
    }
    assert "at cms init" in invoke(store, "post", "ls", code=2).stderr
    result = run(store, "init")
    assert result == {
        "initialized": True,
        "changed": True,
        "migrated": {"post": 2, "collection": 1},
    }
    assert decode(store.path("backend/cms.yaml").read_bytes()) == {"schema": 5}
    for original in originals:
        current = store.get(original["id"])["record"]
        assert {key: current[key] for key in original} == original
        path, _ = store.content_source(current)
        assert decode(path.read_bytes()) == {
            key: original[key] for key in ("title", "short_description", "tags")
        }
        assert current["metadata_digest"] == digest(path.read_bytes())
        assert not {"title", "short_description", "tags"} & set(
            decode(store.record_path(original["id"]).read_bytes())
        )
    assert all(store.path(path).read_bytes() == raw for path, raw in sources.items())
    generate(store, preview=True)
    assert all(
        store.get(r["id"])["record"]["updated_at"] == r["updated_at"] for r in originals
    )
    assert run(store, "init")["changed"] is False


@pytest.mark.parametrize("problem", ["existing_yaml", "malformed_record"])
def test_post_metadata_migration_validates_every_post_before_writing(store, problem):
    new_post(store, "Z-last")
    legacy_posts(store)
    if problem == "existing_yaml":
        store.path("content/posts/z-last.yaml").write_text(
            "# Keep this authored file\n"
        )
    else:
        path = store.record_path("post/z-last")
        record = decode(path.read_bytes())
        record["tags"] = "invalid"
        path.write_bytes(encode(record))
    before = {
        p: p.read_bytes()
        for d in ("content", "backend")
        for p in store.path(d).rglob("*")
        if p.is_file()
    }
    invoke(store, "init", code=2)
    after = {
        p: p.read_bytes()
        for d in ("content", "backend")
        for p in store.path(d).rglob("*")
        if p.is_file()
    }
    assert after == before


def test_post_metadata_migration_recovers_an_interrupted_save(store, monkeypatch):
    legacy_posts(store)
    install = store._install

    def fail_record(path, raw):
        if path == store.record_path("post/example"):
            raise OSError("simulated interruption")
        install(path, raw)

    monkeypatch.setattr(store, "_install", fail_record)
    with pytest.raises(OSError):
        initialize(store)
    assert store.path(".atlas/cms/pending.json").exists()
    monkeypatch.setattr(store, "_install", install)
    assert initialize(store)["changed"] is False
    assert store.get("post/example")["record"]["title"] == "Example"
    assert not store.path(".atlas/cms/pending.json").exists()


def test_new_post_preserves_an_existing_metadata_file(store):
    path = store.path("content/posts/attention.yaml")
    raw = b"# Pre-existing authored metadata\n"
    path.write_bytes(raw)
    invoke(store, "post", "new", "Attention", code=2)
    assert path.read_bytes() == raw
    assert not store.record_path("post/attention").exists()
    assert not store.path("content/posts/attention.ipynb").exists()


def test_collection_cli_edits_keep_yaml_and_markdown_separate(store):
    created = run(store, "collection", "new", "A course")
    identity = created["record"]["id"]
    metadata = store.path("content/collections/a-course.yaml")
    body = store.path("content/collections/a-course.md")
    assert created["record"]["source_path"] == "content/collections/a-course.md"
    assert body.read_bytes() == b""
    assert set(decode(metadata.read_bytes())) == {"title", "short_description"}
    raw_yaml = b"# Keep my comment\ntitle: A course\nshort_description: A summary\ncover_caption: '*A cover*'\n"
    metadata.write_bytes(raw_yaml)
    opened = run(
        store,
        "collection",
        "open",
        identity,
        "--file",
        "-",
        input="## Introduction\n\n[Reference](https://example.com).",
    )
    assert metadata.read_bytes() == raw_yaml
    assert body.read_text() == opened["record"]["long_description"]
    assert opened["record"]["source_digest"] == digest(body.read_bytes())
    raw_body = b"\n<!-- Keep my formatting -->\n\n**Directly edited**.\n\n"
    body.write_bytes(raw_body)
    renamed = run(store, "collection", "edit", identity, "--title", "Renamed course")
    assert body.read_bytes() == raw_body
    assert renamed["record"]["id"] == identity
    assert renamed["record"]["source_path"] == created["record"]["source_path"]
    assert renamed["record"]["cover_caption"] == "*A cover*"
    assert "long_description" not in decode(metadata.read_bytes())


@pytest.mark.parametrize("extension", ["md", "yaml"])
@pytest.mark.parametrize("preview", [False, True])
def test_direct_collection_sources_update_revision_dates_and_projection(
    store, extension, preview
):
    publish(store, "post/example")
    image = store.root / "thumbnail.png"
    run(store, "collection", "edit", "collection/guide", "--cover", str(image))
    created = run(store, "collection", "publish", "collection/guide")
    path = store.path(f"content/collections/guide.{extension}")
    raw = (
        b"<!-- Keep this -->\n\n## Direct introduction\n\n[My link](https://example.com).\n"
        if extension == "md"
        else b"# Keep this\ntitle: Direct title\nshort_description: Direct summary\n"
    )
    path.write_bytes(raw)
    edited = store.get("collection/guide")
    assert edited["revision"] != created["revision"]
    assert edited["record"]["status"] == "published"
    with pytest.raises(Conflict):
        store.update(
            "collection/guide", {"long_description": "Stale body"}, created["revision"]
        )
    generate(store, preview=preview)
    observed = store.get("collection/guide")
    changed_digest = "source_digest" if extension == "md" else "metadata_digest"
    other_digest = "metadata_digest" if extension == "md" else "source_digest"
    assert observed["record"][changed_digest] == digest(raw)
    assert observed["record"][other_digest] == created["record"][other_digest]
    assert observed["record"]["updated_at"] != created["record"]["updated_at"]
    page = store.path("frontend/collections/guide.qmd")
    assert (
        "## Direct introduction" if extension == "md" else "Direct title"
    ) in page.read_text()
    before = page.read_bytes()
    generate(store, preview=preview)
    assert store.get("collection/guide") == observed
    assert path.read_bytes() == raw
    assert page.read_bytes() == before


@pytest.mark.parametrize(
    "problem", ["missing_md", "invalid_utf8", "embedded_long_description"]
)
def test_invalid_collection_source_preserves_content_and_projection(store, problem):
    generate(store, preview=True)
    body = store.path("content/collections/guide.md")
    metadata = store.path("content/collections/guide.yaml")
    if problem == "missing_md":
        body.unlink()
    elif problem == "invalid_utf8":
        body.write_bytes(b"\xff")
    else:
        metadata.write_bytes(metadata.read_bytes() + b"long_description: Old layout\n")
    paths = [
        body,
        metadata,
        store.record_path("collection/guide"),
        store.path("frontend/collections/guide.qmd"),
    ]
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    invoke(store, "sync", "--preview", code=2)
    invoke(
        store,
        "collection",
        "open",
        "collection/guide",
        "--file",
        "-",
        input="Do not erase",
        code=2,
    )
    assert {p: p.read_bytes() if p.exists() else None for p in paths} == before


@pytest.mark.parametrize("caption", ["", "*Cover* by Artist"])
def test_init_migrates_collection_body_preserving_values_dates_and_post_sources(
    store, caption
):
    body = "First paragraph with [a link](https://example.com).\n\n## Résumé\n\n- A point.\n"
    store.update(
        "collection/guide", {"long_description": body, "cover_caption": caption}
    )
    original = legacy_collections(store)[0]
    post_files = {
        p: p.read_bytes()
        for d in ("backend/posts", "content/posts")
        for p in store.path(d).glob("*")
        if p.is_file()
    }
    assert "at cms init" in invoke(store, "collection", "ls", code=2).stderr
    assert run(store, "init")["migrated"] == {"collection": 1}
    current = store.get("collection/guide")["record"]
    assert {
        key: current[key]
        for key in original
        if key not in {"source_path", "source_digest"}
    } == {
        key: value
        for key, value in original.items()
        if key not in {"source_path", "source_digest"}
    }
    assert current["source_path"] == "content/collections/guide.md"
    assert store.path(current["source_path"]).read_text() == body
    assert current["source_digest"] == digest(body.encode())
    metadata = store.path("content/collections/guide.yaml")
    assert "long_description" not in decode(metadata.read_bytes())
    assert current["metadata_digest"] == digest(metadata.read_bytes())
    assert all(p.read_bytes() == raw for p, raw in post_files.items())
    generate(store, preview=True)
    assert (
        store.get("collection/guide")["record"]["updated_at"] == original["updated_at"]
    )
    assert run(store, "init")["changed"] is False


@pytest.mark.parametrize("schema", [3, 4])
@pytest.mark.parametrize("problem", ["existing_md", "malformed_yaml"])
def test_collection_migration_failure_preserves_all_legacy_sources(
    store, schema, problem
):
    run(store, "collection", "new", "Z-last")
    if schema == 3:
        legacy_posts(store)
    else:
        legacy_collections(store)
    if problem == "existing_md":
        store.path("content/collections/z-last.md").write_text(
            "Keep this authored body."
        )
    else:
        store.path("content/collections/z-last.yaml").write_text("broken: [yaml")
    before = {
        p: p.read_bytes()
        for d in ("backend", "content")
        for p in store.path(d).rglob("*")
        if p.is_file()
    }
    invoke(store, "init", code=2)
    after = {
        p: p.read_bytes()
        for d in ("backend", "content")
        for p in store.path(d).rglob("*")
        if p.is_file()
    }
    assert after == before


def test_collection_migration_recovers_yaml_markdown_and_backend_together(
    store, monkeypatch
):
    original = legacy_collections(store)[0]
    install = store._install

    def fail_record(path, raw):
        if path == store.record_path("collection/guide"):
            raise OSError("simulated interruption")
        install(path, raw)

    monkeypatch.setattr(store, "_install", fail_record)
    with pytest.raises(OSError):
        initialize(store)
    assert store.path(".atlas/cms/pending.json").exists()
    monkeypatch.setattr(store, "_install", install)
    assert initialize(store)["changed"] is False
    assert (
        store.get("collection/guide")["record"]["long_description"]
        == original["long_description"]
    )
    assert not store.path(".atlas/cms/pending.json").exists()


@pytest.mark.parametrize("extension", ["md", "yaml"])
def test_new_collection_preserves_existing_authored_sources(store, extension):
    path = store.path(f"content/collections/course.{extension}")
    path.write_bytes(b"Keep this file.")
    invoke(store, "collection", "new", "Course", code=2)
    assert path.read_bytes() == b"Keep this file."
    other = "yaml" if extension == "md" else "md"
    assert not store.path(f"content/collections/course.{other}").exists()
    assert not store.record_path("collection/course").exists()


def test_sync_injects_metadata_without_mutating_source_and_is_deterministic(store):
    new_post(store)
    notebook_invoke(
        store,
        "edit-cell",
        "post/attention",
        "--index",
        "0",
        "--file",
        "-",
        input="## First heading\n\nMy actual prose.",
    )
    canonical = store.path("content/posts/attention.ipynb")
    value = nb.load(canonical.read_bytes())
    code = nb.cell("raise RuntimeError('must never execute')", "code")
    code.update(
        execution_count=7,
        outputs=[
            {"output_type": "stream", "name": "stdout", "text": ["stored output\n"]}
        ],
    )
    value["cells"].append(code)
    value["cells"][0]["attachments"] = {"inline.png": {"image/png": "cG5n"}}
    canonical.write_bytes(nb.dump(value))
    before = canonical.read_bytes()
    run(store, "sync", "--preview")
    output = store.path("frontend/posts/attention.ipynb")
    generated = nb.load(output.read_bytes())
    metadata, _ = split_document(nb.source(generated["cells"][0]))
    assert metadata["title"] == "Attention"
    assert metadata["categories"] == ["python", "Python"]
    assert metadata["description"] == "An explanation"
    assert "toc" not in metadata
    assert "toc-depth" not in metadata
    assert metadata["draft"] is True
    assert "date" in metadata and "date-modified" in metadata
    assert generated["cells"][1:] == value["cells"]
    assert canonical.read_bytes() == before
    generated_bytes = output.read_bytes()
    run(store, "sync", "--preview")
    assert output.read_bytes() == generated_bytes
    assert not store.path("frontend/posts/attention.yaml").exists()


@pytest.fixture
def git_store(store):
    subprocess.run(["git", "init", "-q", str(store.root)], check=True)
    return store


@pytest.fixture
def browser_store(git_store):
    return git_store


def git(store, *args):
    subprocess.run(["git", *args], cwd=store.root, check=True, capture_output=True)


def commit_sources(store, *paths):
    git(store, "add", "--force", "--", *paths)
    git(
        store,
        "-c",
        "user.name=Atlas Test",
        "-c",
        "user.email=atlas@example.test",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Record source fixtures",
    )


def test_empty_code_path_directory_has_an_empty_browser(git_store):
    store = git_store
    new_post(store)
    project = store.path("examples/demo")
    project.mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "examples/demo")
    run(store, "sync", "--preview")
    output = store.path("frontend/posts/attention/source")
    assert "No eligible committed files found." in (output / "index.qmd").read_text()


def test_source_browser_never_projects_ignored_files(browser_store):
    store = browser_store
    new_post(store)
    project = store.path("projects/demo")
    (project / "internal").mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    readme = project / "README.md"
    readme.write_text("# Initially visible\n")
    (project / "public.py").write_text("# unignored by a negated rule\n")
    (project / "internal/notes.py").write_text("NESTED_IGNORE_SENTINEL")
    (project / "excluded.txt").write_text("REPO_EXCLUDE_SENTINEL")
    (project / "global.txt").write_text("GLOBAL_EXCLUDE_SENTINEL")
    commit_sources(store, "projects/demo")

    output = store.path("frontend/posts/attention/source")
    run(store, "sync", "--preview")
    assert (output / "README.md.qmd").is_file()

    store.path(".gitignore").write_text("/projects/demo/README.md\n")
    (project / ".gitignore").write_text("*.py\n!public.py\ninternal/\n")
    store.path(".git/info/exclude").write_text("/projects/demo/excluded.txt\n")
    global_excludes = store.path("git-global-exclude")
    global_excludes.write_text("/projects/demo/global.txt\n")
    git(store, "config", "core.excludesFile", str(global_excludes))

    run(store, "sync", "--preview")
    assert not (output / "README.md.qmd").exists()
    assert not (output / "file~raw~README.md.qmd").exists()

    publish(store, "post/attention")
    for options in (["--preview"], []):
        run(store, "sync", *options)
        index = (output / "index.qmd").read_text()
        assert "public.py" in index
        for name in (
            "README.md",
            "notes.py",
            "excluded.txt",
            "global.txt",
            ".gitignore",
        ):
            assert name not in index
        assert {p.name for p in output.glob("*.qmd")} == {"index.qmd", "public.py.qmd"}


def test_source_browser_checks_literal_gitignore_for_colon_prefixed_path(browser_store):
    store = browser_store
    new_post(store)
    project = store.path(":project")
    project.mkdir()
    (project / "ignored.txt").write_text("never project this file\n")
    (project / "public.txt").write_text("public contents\n")
    commit_sources(store, "./:project")
    store.path(".gitignore").write_text("/:project/ignored.txt\n")
    run(store, "post", "edit", "post/attention", "--code-path", ":project")
    run(store, "sync", "--preview")
    output = store.path("frontend/posts/attention/source")
    assert {path.name for path in output.iterdir()} == {"index.qmd", "public.txt.qmd"}


def test_source_browser_discovers_tree_and_follows_post_publication(browser_store):
    store = browser_store
    new_post(store)
    project = store.path("projects/demo")
    (project / "examples").mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    file = project / "examples/main.py"
    file.write_text(
        "raise RuntimeError('never execute')\n"
        "# <script>alert(1)</script>\n"
        "# {{< include /missing-private-file.qmd >}}\n"
        "# ```\n"
    )
    (project / "settings.toml").write_text("[settings]\nenabled = true\n")
    (project / "examples/__init__.py").write_text("# package marker\n")
    (project / "examples/second").mkdir()
    (project / "examples/second/main.py").write_text("# another example\n")
    (project / "README.md").write_text("# Sample project\n")
    commit_sources(store, "projects/demo")
    canonical = store.path("content/posts/attention.ipynb")
    authored = canonical.read_bytes()
    relative = "examples/main.py"
    run(store, "sync")
    assert not store.path("frontend/posts/attention/source/index.qmd").exists()
    run(store, "sync", "--preview")

    output = store.path("frontend/posts/attention/source")
    generated = store.path("frontend/posts/attention.ipynb")
    index_meta, index = split_document((output / "index.qmd").read_text())
    assert index_meta["draft"] is True
    assert '<div class="source-tree"><ul>' in index
    assert 'id="folder-examples" class="source-folder"' in index
    assert 'id="folder-examples:second" class="source-folder"' in index
    assert 'href="./examples/second/main.py.html"' in index
    assert 'href="./examples/main.py.html"' in index
    assert 'href="./README.md.html"' in index
    assert "../../attention.html" in index
    file_meta, content = split_document((output / f"{relative}.qmd").read_text())
    assert index_meta["grid"] == file_meta["grid"] == {"body-width": "1053px"}
    assert content.count("[← All project files](../index.html)") == 1
    assert "[Skip source listing](#end-of-file)" in content
    assert '::: {#end-of-file tabindex="-1"}' in content
    assert 'id="L-2"' in content and 'href="#L-2"' in content
    assert "&lt;script&gt;" in content and "<script>" not in content
    assert "{{<" not in content and "&#96;&#96;&#96;" in content
    assert "missing-private-file.qmd" in content
    assert (output / "settings.toml.qmd").is_file()
    cells = nb.load(generated.read_bytes())["cells"]
    metadata, _ = split_document(nb.source(cells[0]))
    link = "[📁 `source`](./attention/source/index.html){.source-browser-link}"
    assert metadata["margin-header"] == link
    assert nb.source(cells[1]) == f"::: {{.d-md-none}}\n{link}\n:::"
    assert canonical.read_bytes() == authored

    publish(store, "post/attention")
    run(store, "sync")
    assert (output / f"{relative}.qmd").is_file()
    assert (output / "examples/file~__init__.py.qmd").is_file()
    assert b"source-browser-link" in generated.read_bytes()

    run(store, "post", "edit", "post/attention", "--code-path", "")
    run(store, "sync")
    assert not list(output.rglob("*.qmd"))
    assert b"source-browser-link" not in generated.read_bytes()


def test_source_browser_renders_markdown_with_project_links(browser_store):
    store = browser_store
    new_post(store)
    project = store.path("projects/demo")
    (project / "_examples").mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    (project / "_examples/setup.md").write_text(
        "# Quick Start\n\n[Script](__init__.py#L-1) · [Examples](./)\n\n"
        "| Field | Value |\n| --- | --- |\n| One | Two |\n\n"
        "[Private](../secret.txt) · [Outside](../../secret.txt) · "
        "[Root](/secret.txt) · [External](https://example.com) · "
        "[Protocol-relative](//example.com) · [Hostless](https:secret.txt)\n\n"
        "[Readme <tel:5550100>](../README.md) followed by ordinary text.\n\n"
        "## Title Block Header\n\n[Jump](#title-block-header)\n\n"
        "![Diagram](https://example.com/trace.png)\n\n"
        "<script>never_render()</script>\n\n"
        "{{< include ../secret.txt >}}\n\n"
        "```{python}\nraise RuntimeError('never run')\n```\n"
    )
    (project / "_examples/__init__.py").write_text("# sample\n")
    (project / "secret.txt").write_text("ignored\n")
    store.path(".gitignore").write_text("/projects/demo/secret.txt\n")
    (project / "README.md").write_text(
        "[Quick Start](_examples/setup.md#quick-start)\n"
    )
    commit_sources(store, "projects/demo")
    run(store, "sync", "--preview")
    output = store.path("frontend/posts/attention/source")
    _, body = split_document((output / "file~_examples/setup.md.qmd").read_text())
    assert "[View source](./file~raw~setup.md.html)" in body
    assert '<h1 id="source-heading-quick-start">Quick Start</h1>' in body
    assert '<a href="file~__init__.py.html#L-1">Script</a>' in body
    assert '<a href="../index.html#folder-file~_examples">Examples</a>' in body
    assert "<table>" in body
    assert '<a href="https://example.com">External</a>' in body
    assert "Private · Outside · Root" in body
    assert "<img" not in body and "trace.png" not in body and "Diagram" in body
    assert "Protocol-relative · Hostless" in body
    assert "https:secret.txt" not in body
    assert (
        '<a href="../README.md.html">Readme tel:5550100</a> followed by ordinary text.'
        in body
    )
    assert '<h2 id="source-heading-title-block-header">Title Block Header</h2>' in body
    assert '<a href="#source-heading-title-block-header">Jump</a>' in body
    assert "&lt;script&gt;" in body and "<script>" not in body
    assert "{{<" not in body and "&#123;&#123;&lt; include" in body
    assert "```{python}" not in body and "never run" in body
    assert (
        'href="file~_examples/setup.md.html#source-heading-quick-start"'
        in (output / "README.md.qmd").read_text()
    )
    source = (output / "file~_examples/file~raw~setup.md.qmd").read_text()
    assert "[View rendered](./setup.md.html)" in source
    assert 'id="L-1"' in source


def test_source_browser_omits_opaque_files_and_preserves_unusual_names(
    browser_store,
    monkeypatch,
):
    from atlas import cms_source

    monkeypatch.setattr(cms_source, "TEXT_LIMIT", 1024)
    store = browser_store
    new_post(store)
    project = store.path("projects/demo")
    project.mkdir(parents=True)
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    private = store.path("projects/private.py")
    private.write_text("# unrelated project\n")
    (project / "link.py").symlink_to(private)
    (project / "picture.png").write_bytes(b"\x00\xff")
    (project / "invalid.txt").write_bytes(b"\xff")
    (project / "huge.txt").write_bytes(b"a" * 1025)
    (project / "index").write_text("not the browser index\n")
    (project / "A <tag>.html").write_text("<script>alert(1)</script>\n")
    (project / "README.md").write_text("# Summary\n")
    (project / "README.md.source").write_text("another file\n")
    nested = Store(project / "nested-checkout")
    nested.root.mkdir()
    git(nested, "init", "-q")
    nested.path("nested-only.txt").write_text("Nested repository data\n")
    commit_sources(nested, "nested-only.txt")
    commit_sources(store, "projects/demo")
    run(store, "sync", "--preview")

    output = store.path("frontend/posts/attention/source")
    index = (output / "index.qmd").read_text()
    assert "&lt;tag&gt;" in index and "<tag>" not in index
    unusual = cms_source.source_page(PurePosixPath("A <tag>.html"))
    unusual_page = (output / f"{unusual}.qmd").read_text()
    assert "&#60;tag&#62;" in unusual_page and "<tag>" not in unusual_page
    assert (output / "file~index.qmd").is_file()
    assert (output / "file~raw~README.md.qmd").is_file()
    assert "another" in (output / "README.md.source.qmd").read_text()
    for name in (
        "link.py",
        "private.py",
        "picture.png",
        "invalid.txt",
        "huge.txt",
        "nested-checkout",
    ):
        assert name not in index
        assert not (output / f"{name}.qmd").exists()


@pytest.mark.parametrize("swap_parent", [True, False])
def test_source_browser_excludes_replaced_paths(browser_store, swap_parent):
    from atlas.cms_source import source_files

    store = browser_store
    project = store.path("project")
    directory = project / "nested"
    directory.mkdir(parents=True)
    sample = directory / "sample.txt"
    sample.write_text("safe")
    commit_sources(store, "project")
    outside = store.path("private")
    outside.mkdir()
    (outside / "sample.txt").write_text("not for the browser")
    records = [{"id": "post/example", "code_path": "project"}]
    assert source_files(store, records)["post/example"] == {
        PurePosixPath("nested/sample.txt"): "safe"
    }
    if swap_parent:
        directory.rename(project / "backup")
        directory.symlink_to(outside)
    else:
        sample.unlink()
        sample.symlink_to(outside / "sample.txt")
    assert source_files(store, records)["post/example"] == {}


def test_source_browser_reads_only_head_and_reserves_its_projection(browser_store):
    store = browser_store
    new_post(store)
    project = store.path("project")
    project.mkdir()
    tracked = project / "committed.txt"
    tracked.write_text("REVIEWED_CONTENT\n")
    commit_sources(store, "project")
    tracked.write_text("STAGED_REPLACEMENT\n")
    (project / "staged.txt").write_text("STAGED_ADDITION\n")
    git(store, "add", "project")
    tracked.write_text("WORKTREE_REPLACEMENT\n")
    (project / "untracked.txt").write_text("WORKTREE_ADDITION\n")
    (project / "local.txt").write_text("IGNORED_ADDITION\n")
    store.path(".gitignore").write_text(
        "/project/local.txt\n/content/posts/figures/local.txt\n"
    )
    sidecar = store.path("content/posts/attention/source/committed.txt.qmd")
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("SIDECAR_OVERRIDE\n")
    figures = store.path("content/posts/figures")
    figures.mkdir()
    (figures / "local.txt").write_text("IGNORED_SIDECAR\n")
    (figures / "public.svg").write_text("<svg/>")
    run(store, "post", "edit", "post/attention", "--code-path", "project")
    run(store, "sync", "--preview")
    browser = store.path("frontend/posts/attention/source")
    assert {p.name for p in browser.iterdir()} == {"index.qmd", "committed.txt.qmd"}
    body = (browser / "committed.txt.qmd").read_text()
    assert "REVIEWED_CONTENT" in body
    for marker in ("STAGED_REPLACEMENT", "WORKTREE_REPLACEMENT", "SIDECAR_OVERRIDE"):
        assert marker not in body
    assert store.path("frontend/posts/figures/public.svg").exists()
    assert not store.path("frontend/posts/figures/local.txt").exists()


def test_source_browser_does_not_run_the_secret_scanner(git_store, monkeypatch):
    from atlas import cms_source

    store = git_store
    new_post(store)
    project = store.path("project")
    project.mkdir()
    (project / "example.py").write_text("# A committed source file\n")
    commit_sources(store, "project")
    run(store, "post", "edit", "post/attention", "--code-path", "project")
    publish(store, "post/attention")

    def unexpected_scan(*args):
        pytest.fail("CMS source projection should not scan for secrets")

    monkeypatch.setattr(cms_source, "secret_findings", unexpected_scan)
    report = run(store, "check", code=1)
    assert {item["id"] for item in report["diagnostics"]} == {"collection/guide"}
    run(store, "sync")
    output = store.path("frontend/posts/attention/source/example.py.qmd")
    assert output.is_file()


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("hidden", "private path"),
        ("symlink", "link or special file"),
        ("hardlink", "link or special file"),
        ("raw-notebook", "unrendered source file"),
        ("preview", "draft preview output"),
        ("stale-browser-page", "unapproved source page"),
        ("malformed-browser-page", "unapproved source page"),
        ("ignored-static-asset", "Git-ignored asset"),
    ],
)
def test_pages_artifact_rejects_unsafe_output(git_store, case, message):
    from atlas.cms_site import verify_pages_artifact

    store = git_store
    artifact = store.path("frontend/_site")
    artifact.mkdir()
    index = artifact / "index.html"
    index.write_text("<h1>Public site</h1>")
    if case == "hidden":
        (artifact / ".env").write_text("LOCAL_ONLY")
    elif case == "symlink":
        (artifact / "download").symlink_to(store.root)
    elif case == "hardlink":
        os.link(index, artifact / "copy.html")
    elif case == "raw-notebook":
        (artifact / "analysis.ipynb").write_text("{}")
    elif case == "preview":
        (artifact / "_site-preview").mkdir()
    elif case in {"stale-browser-page", "malformed-browser-page"}:
        name = (
            r"bad\PRIVATE_ARTIFACT_CANARY.html"
            if case == "malformed-browser-page"
            else "stale.html"
        )
        stale = artifact / "posts/old/source" / name
        stale.parent.mkdir(parents=True)
        stale.write_text("OLD_ARTIFACT")
    elif case == "ignored-static-asset":
        asset = store.path("frontend/assets/attachment.txt")
        asset.parent.mkdir(parents=True)
        asset.write_text("PRIVATE_ASSET")
        commit_sources(store, "frontend/assets")
        store.path(".gitignore").write_text("/frontend/assets/attachment.txt\n")
        (artifact / "assets").mkdir()
        shutil.copyfile(asset, artifact / "assets/attachment.txt")
    with pytest.raises(ValueError, match=message) as error:
        verify_pages_artifact(store)
    assert "PRIVATE_ARTIFACT_CANARY" not in str(error.value)


@pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="Gitleaks is not installed"
)
@pytest.mark.parametrize("in_filename", [True, False])
def test_pages_artifact_rejects_possible_secrets(git_store, in_filename):
    from atlas.cms_site import verify_pages_artifact

    artifact = git_store.path("frontend/_site")
    artifact.mkdir()
    token = "jina_" + "aA0bB1cC2dD3eE4fF5" * 3
    (artifact / "index.html").write_text("<h1>Public site</h1>")
    if in_filename:
        (artifact / f"{token}.txt").write_text("Ordinary contents")
    else:
        (artifact / "search.json").write_text(json.dumps([{"text": token}]))
    with pytest.raises(ValueError, match="possible secrets in 1 output path") as error:
        verify_pages_artifact(git_store)
    assert token not in str(error.value)


def test_pages_artifact_build_stops_when_source_scanning_is_unavailable(
    git_store, monkeypatch
):
    from atlas import cms, cms_source

    store = git_store
    (store.root / "example.py").write_text("# Outside any browser project\n")

    def unexpected_render():
        pytest.fail("Pages build should stop before looking up Quarto")

    monkeypatch.setattr(cms, "quarto_executable", unexpected_render)
    monkeypatch.setattr(cms_source.shutil, "which", lambda _: None)
    result = invoke(store, "build", "--for-pages", code=2)
    assert "Install Gitleaks" in result.stderr
    assert not store.path("frontend/_site").exists()
    result = invoke(store, "build", "--for-pages", "--preview", code=2)
    assert "requires a public build" in result.stderr


@pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="Gitleaks is not installed"
)
def test_pages_artifact_build_rejects_repository_findings_before_render(git_store):
    key = "jina_" + "aA0bB1cC2dD3eE4fF5" * 3
    git_store.path("draft-not-published.txt").write_text(key)

    for args in [("scan-secrets",), ("build", "--for-pages")]:
        result = invoke(git_store, *args, code=2)
        assert "draft-not-published.txt" in result.stderr
        assert "atlas-jina-api-key" in result.stderr
        assert key not in result.stderr
    assert not git_store.path("frontend/_site").exists()
    result = invoke(git_store, "scan-secrets", "--staged")
    assert "Repository secret scan passed" in result.stdout


@pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="Gitleaks is not installed"
)
def test_workspace_secret_scan_keeps_local_exclusions_out_of_repository_scans(
    git_store, monkeypatch
):
    git_store.path(".gitignore").write_text(".env\n.venv/\nlocal/\n")
    local = git_store.path(".env")
    key = "jina_" + "aA0bB1cC2dD3eE4fF5" * 3
    local.write_text(key)
    dependency = git_store.path(".venv/dependency.py")
    dependency.parent.mkdir()
    dependency.write_text(key)

    invoke(git_store, "scan-secrets")
    invoke(git_store, "scan-secrets", "--staged")
    result = invoke(git_store, "scan-secrets", "--workspace")
    assert "Workspace secret scan passed." in result.stdout

    other = git_store.path("local/settings.txt")
    other.parent.mkdir()
    other.write_text(key)
    result = invoke(git_store, "scan-secrets", "--workspace", code=2)
    assert "local/settings.txt: atlas-jina-api-key" in result.stderr
    assert key not in result.stderr
    result = invoke(git_store, "scan-secrets", "--workspace", "--staged", code=2)
    assert "--workspace and --staged cannot be combined" in result.stderr
    other.unlink()
    result = invoke(git_store, "scan-secrets", "--workspace")
    assert "Workspace secret scan passed." in result.stdout

    git(git_store, "add", "-f", ".env", ".venv/dependency.py")

    def unexpected_render():
        pytest.fail("Pages build should reject secrets before looking up Quarto")

    monkeypatch.setattr("atlas.cms.quarto_executable", unexpected_render)
    for args in [
        ("scan-secrets",),
        ("scan-secrets", "--staged"),
        ("build", "--for-pages"),
    ]:
        result = invoke(git_store, *args, code=2)
        assert ".env: atlas-jina-api-key" in result.stderr
        assert ".venv/dependency.py: atlas-jina-api-key" in result.stderr
        assert key not in result.stderr
    assert not git_store.path("frontend/_site").exists()


@pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="Gitleaks is not installed"
)
def test_pages_artifact_build_rejects_a_secret_introduced_by_render(
    git_store, monkeypatch
):
    from atlas import cms

    store = git_store
    key = "jina_" + "aA0bB1cC2dD3eE4fF5" * 3
    monkeypatch.setattr(cms, "quarto_executable", lambda: "/bin/quarto")
    monkeypatch.setattr(
        cms, "prepare_site", lambda *args, **kwargs: {"site": "frontend"}
    )

    def render(command, *, cwd, stdout):
        assert "--no-execute" in command
        artifact = store.path("frontend/_site")
        artifact.mkdir()
        (artifact / "index.html").write_text(f"<p>{key}</p>")
        return 0

    monkeypatch.setattr(cms.subprocess, "call", render)
    result = invoke(store, "build", "--for-pages", code=2)
    assert "possible secrets in 1 output path" in result.stderr
    assert key not in result.stderr


@pytest.mark.skipif(
    not (shutil.which("quarto") and shutil.which("gitleaks")),
    reason="Quarto and Gitleaks are required",
)
def test_build_and_sync_remove_stale_source_from_both_render_profiles(
    git_store, monkeypatch
):
    from atlas import cms

    store = git_store
    new_post(store)
    project = store.path("project")
    project.mkdir()
    (project / "manual").mkdir()
    (project / "manual/guide.md").write_text(
        "# Previously browsable\n\nSTALE_MARKDOWN_CANARY\n"
    )
    (project / "settings.txt").write_text("STALE_SETTINGS_CANARY\n")
    (project / "useful.txt").write_text("ACTIVE_TEXT_CANARY\n")
    Image.new("RGB", (2, 2), "blue").save(project / "diagram.png")
    notebook = nb.notebook("# Hybrid search\n\n[Jump to the example](#example)")
    notebook["metadata"]["private"] = "PRIVATE_NOTEBOOK_METADATA"
    notebook["cells"][0]["attachments"] = {
        "inline.png": {"image/png": "PRIVATE_ATTACHMENT"}
    }
    setup_cell = nb.cell(
        'jina_api_key = "your_jina_api_key_here"\n'
        'raise RuntimeError("Notebook rendering must never execute this cell")',
        "code",
    )
    setup_cell["outputs"] = [
        {
            "output_type": "stream",
            "name": "stdout",
            "text": ['SAVED_OUTPUT_CANARY <script id="fixture-output">void 0</script>'],
        },
        {
            "output_type": "execute_result",
            "data": {"text/plain": "SAVED_RESULT_CANARY", "text/html": "PRIVATE_HTML"},
        },
        {
            "output_type": "display_data",
            "data": {
                "text/markdown": "**Saved Markdown output**",
                "image/png": "PRIVATE_IMAGE",
            },
        },
        {
            "output_type": "error",
            "traceback": ["\x1b[31mSAVED_ERROR_CANARY\x1b[0m"],
        },
    ]
    notebook["cells"].append(nb.cell("## Example"))
    notebook["cells"].append(setup_cell)
    (project / "hybrid.ipynb").write_bytes(nb.dump(notebook))
    ignored = project / "ignored.qmd"
    ignored.write_text("IGNORED_INCLUDE_CANARY\n")
    store.path(".gitignore").write_text("/project/ignored.qmd\n")
    (project / "instructions.md").write_text(
        "# Instructions\n\n"
        f"{{{{< include {ignored} >}}}}\n\n"
        '<script id="fixture-active-script">void 0</script>\n\n'
        "[Outside file](ignored.qmd) · [Diagram](diagram.png)\n"
    )
    commit_sources(store, "project")
    run(store, "post", "edit", "post/attention", "--code-path", "project")
    publish(store, "post/attention")
    new_post(store, "Unpublished")
    run(store, "post", "edit", "post/unpublished", "--code-path", "project")
    monkeypatch.setenv("QUARTO", shutil.which("quarto"))
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: None)

    def render(command, *, cwd, stdout):
        return subprocess.run(
            command, cwd=cwd, capture_output=True, check=True
        ).returncode

    monkeypatch.setattr(cms.subprocess, "call", render)
    invoke(store, "build", "--for-pages")
    assert not store.path("frontend/_site/posts/unpublished.html").exists()
    assert not store.path("frontend/_site/posts/unpublished").exists()
    invoke(store, "build", "--preview")
    for site in ("_site", "_site-preview"):
        browser = store.path(f"frontend/{site}/posts/attention/source")
        assert (
            b"STALE_MARKDOWN_CANARY" in (browser / "manual/guide.md.html").read_bytes()
        )
        assert (
            b"STALE_MARKDOWN_CANARY"
            in (browser / "manual/file~raw~guide.md.html").read_bytes()
        )
        assert b"STALE_SETTINGS_CANARY" in (browser / "settings.txt.html").read_bytes()
        assert (browser / "useful.txt.html").is_file()
        assert not list(browser.rglob("*diagram*"))
        assert "diagram.png" not in (browser / "index.html").read_text()
        notebook_view = (browser / "hybrid.ipynb.html").read_bytes()
        assert b"your_jina_api_key_here" in notebook_view
        assert (
            b'<h1 id="source-heading-hybrid-search">Hybrid search</h1>' in notebook_view
        )
        assert b'href="#source-heading-example"' in notebook_view
        assert b'<div class="source-preview"' in notebook_view
        assert b"Notebook rendering must never execute this cell" in notebook_view
        assert b'<div class="cell-output mb-3">' in notebook_view
        assert notebook_view.index(b"your_jina_api_key_here") < notebook_view.index(
            b"SAVED_OUTPUT_CANARY"
        )
        assert b"SAVED_RESULT_CANARY" in notebook_view
        assert b"<strong>Saved Markdown output</strong>" in notebook_view
        assert b"SAVED_ERROR_CANARY" in notebook_view and b"\x1b" not in notebook_view
        assert b'<script id="fixture-output">' not in notebook_view
        assert b"PRIVATE_" not in notebook_view
        instructions = (browser / "instructions.md.html").read_bytes()
        assert b"Diagram" in instructions and b"diagram.png" not in instructions
        for page in browser.rglob("*.html"):
            assert b"data:application/octet-stream;base64," not in page.read_bytes()
        # A future-dated render is stale when its projection changes too.
        future = 4_102_444_800  # 2100-01-01 UTC
        os.utime(browser / "settings.txt.html", (future, future))
        (browser / "old-download.bin").write_bytes(b"STALE_RESOURCE_CANARY")

    store.path(".gitignore").write_text("/project/ignored.qmd\n/project/manual/\n")
    (project / "settings.txt").write_text("UPDATED_SETTINGS_CANARY\n")
    commit_sources(store, "project/settings.txt")
    run(store, "sync")
    assert not store.path("frontend/posts/attention/source/manual").exists()
    for site in ("_site", "_site-preview"):
        browser = store.path(f"frontend/{site}/posts/attention/source")
        assert {p.name for p in browser.iterdir()} == {
            "hybrid.ipynb.html",
            "useful.txt.html",
            "instructions.md.html",
            "file~raw~instructions.md.html",
        }

    invoke(store, "build", "--for-pages")
    invoke(store, "build", "--preview")
    for site in ("_site", "_site-preview"):
        output = store.path(f"frontend/{site}")
        browser = output / "posts/attention/source"
        assert (
            b"UPDATED_SETTINGS_CANARY" in (browser / "settings.txt.html").read_bytes()
        )
        assert "guide.md" not in (browser / "index.html").read_text()
        assert (
            b'<script id="fixture-active-script">'
            not in (browser / "instructions.md.html").read_bytes()
        )
        for path in output.rglob("*"):
            if path.is_file():
                rendered = path.read_bytes()
                assert b"STALE_" not in rendered, path.relative_to(output)
                assert b"IGNORED_INCLUDE_CANARY" not in rendered, path.relative_to(
                    output
                )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_quarto_renders_source_shortcut_above_outline(browser_store):
    store = browser_store
    new_post(store)
    store.path("project").mkdir()
    store.path("project/example.py").write_text("# Example source\n")
    commit_sources(store, "project")
    run(store, "post", "edit", "post/attention", "--code-path", "project")
    publish(store, "post/attention")
    run(store, "sync")

    subprocess.run(
        ["quarto", "render", "posts/attention.ipynb", "--no-execute", "--toc"],
        cwd=store.path("frontend"),
        capture_output=True,
        check=True,
    )
    rendered = store.path("frontend/_site/posts/attention.html").read_text()
    desktop, mobile = re.findall(
        r'<a\b(?=[^>]*href="[^"]*attention/source/index\.html")'
        r'(?=[^>]*class="source-browser-link")[^>]*>📁 <code>source</code></a>',
        rendered,
    )
    header = rendered.index('class="quarto-margin-header"')
    outline = rendered.index('id="toc-title"')
    fallback = rendered.index('class="d-md-none"', outline)
    body = rendered.index("Meaningful prose.", fallback)
    assert header < rendered.index(desktop, header) < outline
    assert fallback < rendered.index(mobile, fallback) < body


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_quarto_renders_source_filename_as_literal_text(browser_store):
    from atlas.cms_source import source_page

    store = browser_store
    new_post(store)
    project = store.path("project")
    project.mkdir()
    filename = PurePosixPath("A <em> marker.txt")
    (project / filename).write_text("file contents\n")
    commit_sources(store, "project")
    run(store, "post", "edit", "post/attention", "--code-path", "project")
    publish(store, "post/attention")
    run(store, "sync")
    page = source_page(filename)
    directory = store.path("frontend/posts/attention/source")
    subprocess.run(
        ["quarto", "render", f"{page}.qmd", "--no-execute"],
        cwd=directory,
        capture_output=True,
        check=True,
    )
    rendered = next((store.root / "frontend").rglob(f"{page}.html")).read_text()
    assert "A &lt;em&gt; marker.txt" in rendered
    assert "A <em>" not in rendered


def test_private_edits_preserve_public_dates_and_generated_bytes(store):
    created = new_post(store)
    run(store, "sync", "--preview")
    path = store.path("frontend/posts/attention.ipynb")
    before = path.read_bytes()
    run(store, "notes", "post/attention", "--file", "-", input="PRIVATE_SCRATCH")
    run(store, "todos", "post/attention", "--add", "PRIVATE_TASK")
    changed = run(store, "todos", "post/attention", "--index", "0", "--done")
    assert changed["record"]["updated_at"] == created["record"]["updated_at"]
    assert changed["revision"] != created["revision"]
    run(store, "sync", "--preview")
    assert path.read_bytes() == before
    assert b"PRIVATE_" not in path.read_bytes()
    assert b"source_digest" not in path.read_bytes()
    assert run(store, "todos", "post/attention")["internal_todos"][0]["done"] is True


def test_sync_preserves_a_leading_markdown_horizontal_rule(store):
    created = new_post(store)
    source = store.path(created["record"]["source_path"])
    value = nb.notebook("---\n\nAn ordinary opening rule, without YAML metadata.")
    source.write_bytes(nb.dump(value))
    generate(store, preview=True)
    generated = nb.load(store.path("frontend/posts/attention.ipynb").read_bytes())
    assert generated["cells"][1] == value["cells"][0]
    assert source.read_bytes() == nb.dump(value)


def test_collections_keep_order_and_never_own_posts(store):
    new_post(store, "One")
    new_post(store, "Two")
    run(store, "collection", "new", "Course")
    run(store, "collection", "add", "collection/course", "post/one")
    run(store, "collection", "add", "collection/course", "post/two")
    changed = run(
        store, "collection", "move", "collection/course", "post/two", "--position", "0"
    )
    assert changed["record"]["post_ids"] == ["post/two", "post/one"]
    invoke(store, "collection", "add", "collection/course", "post/two", code=2)
    invoke(store, "collection", "add", "collection/course", "post/unknown", code=4)
    run(store, "post", "edit", "post/two", "--title", "Renamed second post")
    assert (
        store.get("collection/course")["record"]["updated_at"]
        == changed["record"]["updated_at"]
    )
    run(store, "sync", "--preview")
    page = store.path("frontend/collections/course.qmd").read_text()
    assert page.index("| 1 | [Renamed second post]") < page.index("| 2 | [One]")
    run(store, "collection", "remove", "collection/course", "post/two")
    assert store.get("post/two")["record"]["title"] == "Renamed second post"


def test_removing_a_post_detaches_references_and_preserves_images(store):
    new_post(store, "One")
    new_post(store, "Two")
    run(store, "collection", "new", "Course")
    run(store, "collection", "add", "collection/course", "post/one")
    run(store, "post", "edit", "post/two", "--related", "post/one")
    source = store.get("post/one")["record"]["source_path"]
    image = store.root / "thumbnail.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    run(store, "post", "edit", "post/one", "--thumbnail", str(image))
    thumbnail = store.get("post/one")["record"]["thumbnail_path"]
    removed = run(store, "post", "rm", "post/one", "--yes")
    assert removed == {
        "removed": "post/one",
        "detached_collections": ["collection/course"],
        "detached_posts": ["post/two"],
    }
    assert not store.record_path("post/one").exists()
    assert not store.path(source).exists()
    assert not store.path("content/posts/one.yaml").exists()
    assert store.path(thumbnail).exists()
    assert store.get("collection/course")["record"]["post_ids"] == []
    assert store.get("post/two")["record"]["related_post_ids"] == []


@pytest.mark.parametrize("identity", ["post/one", "post/two"])
def test_removing_a_post_rejects_shared_notebook_sources(store, identity):
    new_post(store, "One")
    publish(store, "post/one")
    new_post(store, "Two")
    run(store, "collection", "new", "Course")
    for member in ("post/one", "post/two"):
        run(store, "collection", "add", "collection/course", member)
    run(store, "post", "edit", "post/two", "--related", "post/one")
    second = decode(store.record_path("post/two").read_bytes())
    second["source_path"] = store.get("post/one")["record"]["source_path"]
    store.record_path("post/two").write_bytes(encode(second))
    before = {
        path: path.read_bytes()
        for directory in ("backend", "content")
        for path in store.path(directory).rglob("*")
        if path.is_file()
    }

    result = invoke(store, "post", "rm", identity, "--yes", code=2)

    assert "belong to only one post" in result.stderr
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_removing_a_collection_preserves_member_posts(store):
    new_post(store, "One")
    run(store, "collection", "new", "Course")
    run(store, "collection", "add", "collection/course", "post/one")
    source = store.get("collection/course")["record"]["source_path"]
    assert run(store, "collection", "rm", "collection/course", "--yes") == {
        "removed": "collection/course"
    }
    assert not store.record_path("collection/course").exists()
    assert not store.path(source).exists()
    assert not store.path("content/collections/course.yaml").exists()
    assert store.get("post/one")["record"]["title"] == "One"


@pytest.mark.parametrize("published_count", [0, 1, 2])
@pytest.mark.parametrize("preview", [False, True])
def test_check_and_sync_report_duplicate_notebook_sources(
    store, published_count, preview
):
    new_post(store, "One")
    new_post(store, "Two")
    for identity in ("post/one", "post/two")[:published_count]:
        publish(store, identity)
    run(store, "sync", "--preview")
    projection = store.path("frontend/posts/two.ipynb")
    previous_projection = projection.read_bytes()
    second = decode(store.record_path("post/two").read_bytes())
    second["source_path"] = store.get("post/one")["record"]["source_path"]
    store.record_path("post/two").write_bytes(encode(second))
    result = invoke(store, "check", code=1)
    diagnostics = json.loads(result.stdout)["diagnostics"]
    assert {
        item["id"]
        for item in diagnostics
        if "belong to only one post" in item["message"]
    } == {"post/one", "post/two"}
    before = {path: path.read_bytes() for path in store.path("backend").rglob("*.yaml")}

    result = invoke(store, "sync", *(["--preview"] if preview else []), code=2)

    assert "belong to only one post" in result.stderr
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert projection.read_bytes() == previous_projection


def test_check_reads_each_record_a_bounded_number_of_times(store, monkeypatch):
    for index in range(6):
        new_post(store, f"Extra {index}")
    counts = Counter()
    original = Store.get

    def counting(self, identity):
        counts[identity] += 1
        return original(self, identity)

    monkeypatch.setattr(Store, "get", counting)
    invoke(store, "check", code=1)
    assert max(counts.values()) <= 2


def test_collection_cover_captions_support_markdown_replacement_and_clearing(store):
    identity = "collection/guide"
    source = store.path("content/collections/guide.yaml")
    original = store.get(identity)
    assert "cover_caption" not in decode(source.read_bytes())
    assert original["record"]["cover_caption"] == ""
    image = store.root / "cover.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    caption = "*Crouching Figure of Atlas* by Baldassare Tommaso Peruzzi (1481–1536)"
    changed = run(
        store,
        "collection",
        "edit",
        identity,
        "--cover",
        str(image),
        "--cover-caption",
        caption,
        "--expected-revision",
        original["revision"],
    )
    assert decode(source.read_bytes())["cover_caption"] == caption
    assert "cover_caption" not in decode(store.record_path(identity).read_bytes())
    assert changed["record"]["metadata_digest"] == digest(source.read_bytes())
    assert changed["record"]["updated_at"] != original["record"]["updated_at"]
    assert (
        run(store, "collection", "edit", identity, "--cover-caption", caption)
        == changed
    )
    invoke(
        store,
        "collection",
        "edit",
        identity,
        "--cover-caption",
        "Stale credit",
        "--expected-revision",
        original["revision"],
        code=3,
    )
    assert store.get(identity) == changed
    Image.new("RGB", (8, 8), "red").save(image)
    replacement = run(store, "collection", "edit", identity, "--cover", str(image))
    assert replacement["record"]["cover_caption"] == caption
    run(store, "sync", "--preview")
    page = store.path("frontend/collections/guide.qmd")
    assert f"![{caption}](../assets/cms/" in page.read_text()
    cleared = run(store, "collection", "edit", identity, "--cover-caption", "")
    assert cleared["record"]["cover_caption"] == ""
    assert "cover_caption" not in decode(source.read_bytes())
    run(store, "sync", "--preview")
    assert "![](../assets/cms/" in page.read_text()
    assert caption not in page.read_text()


@pytest.mark.parametrize("caption", [None, 42, "First line\nSecond line", "A\rB"])
def test_invalid_cover_caption_leaves_content_and_metadata_unchanged(store, caption):
    original = store.get("collection/guide")
    source = store.path("content/collections/guide.yaml")
    raw = source.read_bytes()
    with pytest.raises(ValueError, match="single-line Markdown"):
        store.update("collection/guide", {"cover_caption": caption})
    assert store.get("collection/guide") == original
    assert source.read_bytes() == raw


def test_publication_and_public_projection_filter_drafts(store):
    new_post(store, "Public")
    new_post(store, "Private")
    blocked = invoke(store, "post", "publish", "post/public", code=2)
    assert "A notebook with meaningful content is required" in blocked.stderr
    notebook_invoke(
        store,
        "edit-cell",
        "post/public",
        "--index",
        "0",
        "--content",
        "Meaningful prose.",
    )
    diagnostics = run(store, "check", code=1)["diagnostics"]
    assert not any(diagnostic["id"] == "post/public" for diagnostic in diagnostics)
    published = run(store, "post", "publish", "post/public")["record"]
    assert published["status"] == "published"
    assert published["thumbnail_path"] is None
    run(store, "post", "edit", "post/public", "--related", "post/private")
    run(store, "collection", "new", "Reading", "--description", "Read in order")
    run(
        store,
        "collection",
        "open",
        "collection/reading",
        "--file",
        "-",
        input="A useful introduction.",
    )
    run(store, "collection", "add", "collection/reading", "post/private")
    run(store, "collection", "add", "collection/reading", "post/public")
    blocked = invoke(store, "collection", "publish", "collection/reading", code=2)
    assert "A collection cover is required" in blocked.stderr
    cover = store.root / "cover.png"
    Image.new("RGB", (8, 8), "blue").save(cover)
    run(
        store,
        "collection",
        "edit",
        "collection/reading",
        "--cover",
        str(cover),
        "--cover-caption",
        "*Public cover* by the artist",
    )
    run(store, "collection", "publish", "collection/reading")
    assert store.get("post/private")["record"]["status"] == "draft"
    run(store, "sync", "--preview")
    assert store.path("frontend/posts/private.ipynb").exists()
    run(store, "sync")
    assert not store.path("frontend/posts/private.ipynb").exists()
    page = store.path("frontend/collections/reading.qmd").read_text()
    assert "![*Public cover* by the artist](../assets/cms/" in page
    assert "[Private]" not in page
    assert "| 1 | [Public]" in page
    previous = store.path("frontend/posts/public.ipynb").read_bytes()
    meta, _ = split_document(nb.source(nb.load(previous)["cells"][0]))
    assert meta["draft"] is False
    assert "image" not in meta
    assert b"Related:" not in previous
    run(store, "post", "draft", "post/public")
    invoke(store, "sync", code=2)  # Published collection now has no published members.
    assert store.path("frontend/posts/public.ipynb").read_bytes() == previous


def test_stale_record_revision_is_rejected(store):
    created = new_post(store)
    run(store, "post", "edit", "post/attention", "--title", "New")
    invoke(
        store,
        "post",
        "edit",
        "post/attention",
        "--title",
        "Stale",
        "--expected-revision",
        created["revision"],
        code=3,
    )
    assert store.get("post/attention")["record"]["title"] == "New"


def test_direct_notebook_write_during_editor_is_rejected(store, monkeypatch):
    new_post(store)
    path = store.path("content/posts/attention.ipynb")

    def edit(*args, **kwargs):
        path.write_bytes(nb.dump(nb.notebook("External writer")))
        return "My new prose"

    monkeypatch.setattr("atlas.notebook_cli.source_input", edit)
    notebook_invoke(store, "edit-cell", "post/attention", "--index", "0", code=3)
    assert nb.source(nb.load(path.read_bytes())["cells"][0]) == "External writer"


def test_malformed_metadata_during_edit_preserves_authored_text(store, monkeypatch):
    new_post(store)

    def edit(*_):
        store.record_path("post/attention").write_text("broken: [yaml")
        return "My unsaved prose"

    monkeypatch.setattr("atlas.notebook_cli.source_input", edit)
    notebook_invoke(store, "edit-cell", "post/attention", "--index", "0", code=2)
    assert (
        next(store.path(".atlas/cms/edits").glob("*.txt")).read_text()
        == "My unsaved prose"
    )


def test_failed_resume_creation_preserves_the_entered_body(store):
    invoke(
        store,
        "resume",
        "add",
        "New role",
        "--section",
        "unknown",
        "--file",
        "-",
        input="My entered résumé body",
        code=2,
    )
    assert (
        next(store.path(".atlas/cms/edits").glob("*.txt")).read_text()
        == "My entered résumé body"
    )


def test_resume_entry_edit_order_and_profile(store):
    added = run(
        store,
        "resume",
        "add",
        "New role",
        "--section",
        "employment",
        "--subtitle",
        "2026 -- Present",
        "--file",
        "-",
        input="- Built something new.",
    )
    identity = added["record"]["id"]
    run(store, "resume", "move", identity, "--position", "0")
    run(
        store,
        "resume",
        "open",
        identity,
        "--file",
        "-",
        input="- Revised accomplishment.",
    )
    run(store, "resume", "profile", "--summary", "A new summary.")
    run(store, "sync", "--preview")
    page = store.path("frontend/resume.qmd").read_text()
    assert "A new summary." in page
    assert page.index("### New role") < page.index("### Engineer")
    assert "Revised accomplishment" in page
    run(store, "resume", "rm", identity, "--yes")
    assert not store.record_path(identity).exists()
    assert not store.path(added["record"]["source_path"]).exists()


def test_resume_import_preserves_every_fact_and_existing_markup(workspace):
    original = split_document(workspace.path("frontend/resume.qmd").read_text())[1]
    initialize(workspace)
    generate(workspace, preview=True)
    generated = split_document(workspace.path("frontend/resume.qmd").read_text())[1]
    assert re.sub(r"\s+", " ", generated) == re.sub(r"\s+", " ", original)


def test_resume_pdf_projection_shares_authored_content_and_order(store):
    template = store.path("frontend/_cms/resume-pdf.qmd")
    template.write_text(
        "---\nformat: typst\n---\n\nPDF contacts.\n\n"
        "{{cms:summary}}\n\n{{cms:entries}}\n"
    )
    store.new(
        "resume",
        "First role",
        section="employment",
        subtitle="2026 -- Present",
        body="- [A project](https://example.com).",
    )
    run(store, "resume", "move", "resume/first-role", "--position", "0")
    run(
        store,
        "resume",
        "profile",
        "--title",
        "Updated résumé",
        "--summary",
        "New summary.",
    )
    generate(store, preview=True)
    meta, pdf = split_document(store.path(".atlas/cms/resume.qmd").read_text())
    web = store.path("frontend/resume.qmd").read_text()
    assert meta == {"format": "typst", "title": "Updated résumé"}
    for text in (
        "New summary.",
        "2026 -- Present",
        "- [A project](https://example.com).",
    ):
        assert text in pdf and text in web
    assert pdf.index("### First role") < pdf.index("### Engineer")
    assert "::: {.resume-subtitle}\n\n2026 -- Present\n\n:::" in pdf
    assert ".resume-subtitle" not in web
    assert "PDF contacts." in pdf
    assert "assets/resume.pdf" not in pdf
    assert "<script" not in pdf
    assert "{{cms:" not in pdf


@pytest.mark.parametrize("command", ["build", "build-preview", "preview"])
def test_build_and_preview_regenerate_pdf_before_rendering_site(
    store, monkeypatch, command
):
    from atlas import cms

    download = store.path("frontend/assets/resume.pdf")
    download.parent.mkdir(parents=True, exist_ok=True)
    download.write_bytes(b"Previous download")
    resources = {
        "_cms/resume-pdf/layout.lua": b"-- Local PDF layout filter",
        "_cms/resume-pdf/fonts/body.otf": b"Body font",
        "assets/fonts/name.ttf": b"Name font",
    }
    for relative, data in resources.items():
        path = store.path("frontend/" + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    monkeypatch.setenv("QUARTO", "custom-quarto")

    def which(name):
        assert name == "custom-quarto"
        return "/bin/custom-quarto"

    monkeypatch.setattr(cms.shutil, "which", which)
    calls = []

    def quarto(args, cwd, *, stdout=None):
        calls.append(args)
        assert args[0] == "/bin/custom-quarto"
        assert "--no-execute" in args
        if "typst" in args:
            source = Path(args[2])
            assert Path(cwd) == source.parent
            assert "_quarto.yml" not in {p.name for p in source.parent.iterdir()}
            for relative, data in resources.items():
                assert (source.parent / relative).read_bytes() == data
            pdf = b"%PDF-1.7\n" + source.read_bytes()
            source.with_suffix(".pdf").write_bytes(pdf)
        else:
            assert Path(cwd) == store.root
            assert args[1] == ("preview" if command == "preview" else "render")
            assert args[2] == str(store.path("frontend"))
            assert download.read_bytes().startswith(b"%PDF-")
            assert ("--profile" in args) == (command != "build")
            if command == "preview":
                assert args[args.index("--port") + 1] == "4300"
                assert args[args.index("--render") + 1] == "none"
        return 0

    class FinishedPreview:
        pid = 123
        returncode = 0

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    def popen(args, cwd, *, start_new_session):
        assert command == "preview"
        assert start_new_session
        quarto(args, cwd)
        return FinishedPreview()

    monkeypatch.setattr(cms.subprocess, "call", quarto)
    monkeypatch.setattr(cms.subprocess, "Popen", popen)
    monkeypatch.setattr(cms, "preview_group_running", lambda _: False)
    args = {
        "build": ["build"],
        "build-preview": ["build", "--preview"],
        "preview": ["preview", "--port", "4300"],
    }[command]
    invoke(store, *args)
    assert len(calls) == 2 and "typst" in calls[0]
    first = download.read_bytes()
    modified = download.stat().st_mtime_ns
    cache = store.path(".atlas/cms/resume-pdf.cache.yaml").read_bytes()
    records = {
        path: path.read_bytes() for path in store.path("backend/resume").glob("*.yaml")
    }
    invoke(store, *args)
    assert len(calls) == 3 and "typst" not in calls[-1]
    assert download.read_bytes() == first
    assert download.stat().st_mtime_ns == modified
    assert store.path(".atlas/cms/resume-pdf.cache.yaml").read_bytes() == cache
    assert all(path.read_bytes() == raw for path, raw in records.items())
    run(store, "resume", "profile", "--summary", "A freshly edited summary.")
    run(
        store,
        "resume",
        "open",
        "resume/employment-engineer-example",
        "--file",
        "-",
        input="- A freshly edited accomplishment.",
    )
    invoke(store, *args)
    assert len(calls) == 5 and "typst" in calls[-2]
    assert download.read_bytes() != first
    assert b"A freshly edited summary." in download.read_bytes()
    assert b"A freshly edited accomplishment." in download.read_bytes()
    assert not list(store.path(".atlas/cms").glob("resume-pdf-*"))


def test_quick_preview_skips_source_browser_and_removes_stale_preview_pages(
    browser_store, monkeypatch
):
    from atlas import cms

    store = browser_store
    new_post(store)
    project = store.path("projects/demo")
    project.mkdir(parents=True)
    (project / "main.py").write_text("print('example')\n")
    commit_sources(store, "projects/demo")
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    run(store, "sync", "--preview")
    assert store.path("frontend/posts/attention/source/main.py.qmd").is_file()
    preview_dir = store.path("frontend/_site-preview")
    stale = preview_dir / "posts/attention/source/main.py.html"
    current = preview_dir / "posts/attention.html"
    old_post = preview_dir / "posts/removed.html"
    public = store.path("frontend/_site/posts/attention/source/main.py.html")
    for path in (stale, current, old_post, public):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Rendered page.")
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: None)

    class FinishedPreview:
        pid = 123
        returncode = 0

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    def start_preview(*args, **kwargs):
        assert not stale.exists()
        assert not old_post.exists()
        assert current.is_file()
        assert public.is_file()
        assert not store.path("frontend/posts/attention/source/main.py.qmd").exists()
        assert (
            b"source-browser-link"
            not in store.path("frontend/posts/attention.ipynb").read_bytes()
        )
        return FinishedPreview()

    monkeypatch.setattr(cms, "quarto_executable", lambda: "/bin/quarto")
    monkeypatch.setattr(cms.subprocess, "Popen", start_preview)
    monkeypatch.setattr(cms, "preview_group_running", lambda _: False)
    invoke(store, "preview", "--no-source-browser")


def test_preview_snapshot_tracks_only_recursive_visible_source_files(tmp_path):
    from atlas import cms

    store = Store(tmp_path)
    watched = [
        "content/posts/nested/post.ipynb",
        "content/collections/guide.yaml",
        "backend/posts/post.yaml",
        "frontend/_cms/resume-pdf/layout.lua",
        "frontend/assets/fonts/nested/body.otf",
    ]
    ignored = [
        "content/.draft.yaml",
        "content/posts/.hidden/post.ipynb",
        "backend/.lock",
        "frontend/_cms/.hidden/template.qmd",
        "frontend/assets/fonts/.cache/font.otf",
        "frontend/posts/post.qmd",
        "frontend/assets/resume.pdf",
        "frontend/_site-preview/index.html",
        ".atlas/cms/resume.qmd",
    ]
    for relative in watched + ignored:
        path = store.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    store.path("content/linked.yaml").symlink_to(store.path(watched[1]))
    store.path("content/linked-directory").symlink_to(
        store.path("backend"), target_is_directory=True
    )
    store.path("backend/broken.yaml").symlink_to(store.path("missing"))

    snapshot = cms.preview_snapshot(store)

    assert set(snapshot) == set(watched)
    for relative in watched:
        stat = store.path(relative).stat()
        assert snapshot[relative] == (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    store.path(watched[0]).write_text("Edited notebook")
    assert cms.preview_snapshot(store)[watched[0]] != snapshot[watched[0]]
    store.path(watched[1]).unlink()
    created = store.path("content/collections/new.md")
    created.write_text("New introduction")
    changed = cms.preview_snapshot(store)
    assert watched[1] not in changed
    assert "content/collections/new.md" in changed


def test_preview_snapshot_tolerates_missing_source_directories(tmp_path):
    from atlas import cms

    assert cms.preview_snapshot(Store(tmp_path)) == {}


@pytest.fixture
def preview_clock(monkeypatch):
    from atlas import cms

    class Clock:
        tick = 0
        stop = 12
        edits = {}
        processes = []

        def monotonic(self):
            return self.tick * 0.25

        def sleep(self, duration):
            assert duration == 0.25
            self.tick += 1
            assert self.tick <= self.stop, "watcher did not stop with Quarto"
            if self.tick in self.edits:
                self.edits[self.tick]()

        def start(self, *args, **kwargs):
            assert all(process.poll() is not None for process in self.processes)
            process = Preview(len(self.processes) + 1)
            self.processes.append(process)
            return process

    class Preview:
        returncode = None
        terminating = False

        def __init__(self, pid):
            self.pid = pid

        def poll(self):
            if self.returncode is None and clock.tick >= clock.stop:
                self.returncode = 0
            return self.returncode

        def wait(self, timeout=None):
            if self.terminating:
                self.returncode = -cms.signal.SIGTERM
            assert self.returncode is not None
            return self.returncode

    def kill_group(pid, signal):
        assert signal == cms.signal.SIGTERM
        process = clock.processes[pid - 1]
        assert not process.terminating
        process.terminating = True

    clock = Clock()
    monkeypatch.setattr(cms.time, "sleep", clock.sleep)
    monkeypatch.setattr(cms.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(cms.os, "killpg", kill_group)
    monkeypatch.setattr(cms, "preview_group_running", lambda _: False)
    return clock


@pytest.mark.parametrize(
    "relative",
    [
        "content/posts/example.ipynb",
        "backend/posts/example.yaml",
        "frontend/_cms/resume-pdf/layout.lua",
        "frontend/assets/fonts/body.otf",
    ],
)
def test_preview_watcher_debounces_source_edits_and_refreshes_pdf(
    store, monkeypatch, preview_clock, relative
):
    from atlas import cms

    path = store.path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)

    def save(text):
        if path.suffix == ".ipynb":
            path.write_bytes(nb.dump(nb.notebook(text)))
        elif path.suffix == ".yaml":
            record = decode(path.read_bytes())
            record["internal_notes"] = text
            path.write_bytes(encode(record))
        else:
            path.write_text(text)

    save("Initial source")
    preview_clock.edits = {
        1: lambda: save("First save"),
        2: lambda: save("Second save"),
    }
    calls = []
    process = preview_clock.start()

    def regenerate(
        actual_store,
        preview,
        *,
        watch_snapshot,
        source_browser,
        require_source_browser,
        before_install,
    ):
        assert actual_store is store and preview is True
        assert source_browser is True
        assert require_source_browser is False
        assert process.poll() is None
        calls.append(("generate", preview_clock.monotonic()))
        return generate(
            actual_store,
            preview,
            watch_snapshot=watch_snapshot,
            before_install=before_install,
        )

    commit = store.commit

    def commit_projection(changes):
        if store.path("frontend/resume.qmd") in changes:
            assert process.poll() == -cms.signal.SIGTERM
        return commit(changes)

    def render(actual_store, executable):
        assert actual_store is store and executable == "/bin/quarto"
        assert process.poll() == -cms.signal.SIGTERM
        calls.append(("pdf", preview_clock.monotonic()))

    monkeypatch.setattr(cms, "generate", regenerate)
    monkeypatch.setattr(store, "commit", commit_projection)
    monkeypatch.setattr(cms, "render_resume_pdf", render)
    assert cms.watch_preview(store, "/bin/quarto", process) is not None

    assert [kind for kind, _ in calls] == ["generate", "pdf"]
    assert calls[0][1] >= 1.0  # Half a second after the final save.
    assert calls[1][1] == calls[0][1]


@pytest.mark.parametrize("existing_page", [False, True])
def test_preview_watcher_restarts_for_changed_source_pages(
    browser_store, monkeypatch, preview_clock, existing_page
):
    from atlas import cms

    store = browser_store
    new_post(store)
    file = store.path("projects/demo/main.py")
    file.parent.mkdir(parents=True)
    if existing_page:
        file.write_text("# Old contents\n")
        commit_sources(store, "projects/demo")
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    generate(store, preview=True)
    stale = store.path("frontend/_site-preview/posts/attention/source/main.py.html")
    if existing_page:
        stale.parent.mkdir(parents=True)
        stale.write_text("Old rendered contents")
    preview_clock.edits = {
        1: lambda: (
            file.write_text("print('sample')\n"),
            commit_sources(store, "projects/demo"),
            store.path(".gitignore").write_text("# refresh the source index\n"),
        )
    }
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *args: None)
    assert cms.watch_preview(store, "/bin/quarto", preview_clock.start()) is not None
    assert not stale.exists()
    assert (
        "sample"
        in store.path("frontend/posts/attention/source/main.py.qmd").read_text()
    )


def test_preview_watcher_removes_newly_ignored_source_pages(
    browser_store, monkeypatch, preview_clock
):
    from atlas import cms

    store = browser_store
    new_post(store)
    file = store.path("projects/demo/README.md")
    file.parent.mkdir(parents=True)
    file.write_text("# Sample\n")
    commit_sources(store, "projects/demo")
    run(store, "post", "edit", "post/attention", "--code-path", "projects/demo")
    generate(store, preview=True)
    page = store.path("frontend/posts/attention/source/README.md.qmd")
    assert page.is_file()
    preview_clock.edits = {
        1: lambda: store.path(".gitignore").write_text("/projects/demo/README.md\n")
    }
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *args: None)
    assert cms.watch_preview(store, "/bin/quarto", preview_clock.start()) is not None
    assert not page.exists()


def test_preview_watcher_ignores_generated_output_and_hidden_edits(
    store, monkeypatch, preview_clock
):
    from atlas import cms

    generated = store.path("frontend/assets/resume.pdf")
    generated.parent.mkdir(parents=True, exist_ok=True)
    hidden = store.path("content/.editor-save")
    preview_clock.edits = {
        1: lambda: generated.write_bytes(b"Updated download"),
        2: lambda: hidden.write_text("Editor state"),
    }
    calls = []
    monkeypatch.setattr(cms, "generate", lambda *_, **__: calls.append("generate"))
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: calls.append("pdf"))

    assert cms.watch_preview(store, "/bin/quarto", preview_clock.start()) is None

    assert calls == []
    assert preview_clock.tick == preview_clock.stop


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_preview_watcher_detects_source_creation_and_deletion(
    store, monkeypatch, preview_clock, operation
):
    from atlas import cms

    path = store.path("content/collections/new.md")
    if operation == "delete":
        path.write_text("Existing source")
    preview_clock.edits = {
        1: (
            path.unlink
            if operation == "delete"
            else lambda: path.write_text("New source")
        )
    }
    calls = []

    def regenerate(*_, before_install, **__):
        calls.append("generate")
        before_install()

    monkeypatch.setattr(cms, "generate", regenerate)
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: calls.append("pdf"))

    assert cms.watch_preview(store, "/bin/quarto", preview_clock.start()) is not None

    assert calls == ["generate", "pdf"]


def test_preview_watcher_picks_up_draft_created_during_a_refresh(
    store, monkeypatch, preview_clock
):
    from atlas import cms

    path = store.path("content/posts/example.ipynb")
    preview_clock.edits = {1: lambda: path.write_bytes(nb.dump(nb.notebook("Edited")))}
    rendered = []

    def render(actual_store, _):
        rendered.append(actual_store.path("frontend/collections/second.qmd").exists())
        if len(rendered) == 1:
            actual_store.new("collection", "Second")

    monkeypatch.setattr(cms, "render_resume_pdf", render)
    snapshot = cms.watch_preview(store, "/bin/quarto", preview_clock.start())

    assert rendered == [False]
    assert "backend/collections/second.yaml" not in snapshot
    snapshot = cms.watch_preview(store, "/bin/quarto", preview_clock.start(), snapshot)

    assert rendered == [False, True]
    assert snapshot == cms.preview_snapshot(store)


@pytest.mark.parametrize("phase", ["install", "pdf"])
@pytest.mark.parametrize("failure", ["validation", "os", "yaml", "exit"])
def test_preview_restarts_after_refresh_error_if_quarto_was_stopped(
    store, monkeypatch, preview_clock, phase, failure
):
    from atlas import cms

    errors = {
        "validation": ValueError("Invalid saved source"),
        "os": OSError("Source temporarily unavailable"),
        "yaml": cms.yaml.YAMLError("Malformed saved YAML"),
        "exit": cms.typer.Exit(7),
    }
    path = store.path("content/resume.yaml")
    profile = decode(path.read_bytes())
    preview_clock.edits = {
        1: lambda: path.write_bytes(encode(profile | {"summary": "Edited summary"}))
    }
    commit = Store.commit
    failed = False

    def commit_projection(actual_store, changes):
        nonlocal failed
        if (
            phase == "install"
            and preview_clock.processes
            and store.path("frontend/resume.qmd") in changes
            and not failed
        ):
            assert preview_clock.processes[-1].poll() == -cms.signal.SIGTERM
            failed = True
            raise errors[failure]
        return commit(actual_store, changes)

    def render(*_):
        nonlocal failed
        if phase == "pdf" and preview_clock.processes and not failed:
            assert preview_clock.processes[-1].poll() == -cms.signal.SIGTERM
            failed = True
            raise errors[failure]

    monkeypatch.setattr(Store, "commit", commit_projection)
    monkeypatch.setattr(cms, "render_resume_pdf", render)
    monkeypatch.setattr(cms, "quarto_executable", lambda: "/bin/quarto")
    monkeypatch.setattr(cms.subprocess, "Popen", preview_clock.start)

    result = invoke(store, "preview")

    assert "Preview sync failed" in result.stderr
    assert [process.returncode for process in preview_clock.processes] == [
        -cms.signal.SIGTERM,
        0,
    ]


def test_preview_restarts_on_same_port_for_each_saved_batch(
    store, monkeypatch, preview_clock
):
    from atlas import cms

    notebook = store.path("content/posts/example.ipynb")
    profile_path = store.path("content/resume.yaml")
    profile = decode(profile_path.read_bytes())
    marker = store.path("frontend/_site-preview/atlas-preview-generation.json")
    generations = []

    def save(batch):
        notebook.write_bytes(nb.dump(nb.notebook(f"Notebook batch {batch}")))
        profile_path.write_bytes(encode(profile | {"summary": f"Résumé batch {batch}"}))

    preview_clock.edits = {1: lambda: save(1), 6: lambda: save(2)}
    monkeypatch.setattr(cms, "quarto_executable", lambda: "/bin/quarto")
    rendered = []
    commit = Store.commit
    kill_group = cms.os.killpg

    def stop_group(pid, signal):
        assert not marker.exists()
        kill_group(pid, signal)

    def commit_projection(actual_store, changes):
        if store.path("frontend/resume.qmd") in changes:
            assert not marker.exists()
        return commit(actual_store, changes)

    def render(*_):
        assert not marker.exists()
        rendered.append(len(preview_clock.processes))

    def start(args, cwd, *, start_new_session):
        batch = len(preview_clock.processes)
        assert cwd == store.root and start_new_session
        generation = json.loads(marker.read_text())["generation"]
        assert re.fullmatch(r"[0-9a-f]{32}", generation)
        generations.append(generation)
        assert args == [
            "/bin/quarto",
            "preview",
            str(store.path("frontend")),
            "--profile",
            "preview",
            "--output-dir",
            "_site-preview",
            "--port",
            "4300",
            "--render",
            "none",
            "--no-execute",
            *(["--no-browser"] if batch else []),
        ]
        assert rendered[-1] == batch
        if batch:
            assert (
                f"Notebook batch {batch}"
                in store.path("frontend/posts/example.ipynb").read_text()
            )
            assert (
                f"Résumé batch {batch}" in store.path("frontend/resume.qmd").read_text()
            )
        return preview_clock.start()

    monkeypatch.setattr(cms.os, "killpg", stop_group)
    monkeypatch.setattr(Store, "commit", commit_projection)
    monkeypatch.setattr(cms, "render_resume_pdf", render)
    monkeypatch.setattr(cms.subprocess, "Popen", start)
    invoke(store, "preview", "--port", "4300")

    assert [process.returncode for process in preview_clock.processes] == [
        -cms.signal.SIGTERM,
        -cms.signal.SIGTERM,
        0,
    ]
    assert len(set(generations)) == 3
    assert not marker.exists()
    assert not store.path("frontend/_site/atlas-preview-generation.json").exists()


@pytest.mark.parametrize("phase", ["validation", "staging"])
def test_preview_watcher_recovers_from_malformed_authored_yaml(
    store, monkeypatch, preview_clock, capsys, phase
):
    from atlas import cms

    generate(store, True)
    target = store.path("frontend/resume.qmd")
    previous = target.read_bytes()
    profile_path = store.path("content/resume.yaml")
    summary = "A corrected summary from the editor."
    valid_profile = encode(decode(profile_path.read_bytes()) | {"summary": summary})
    if phase == "validation":
        source = profile_path
        valid_source = valid_profile
        malformed_source = "summary: [unfinished YAML"
    else:
        source = store.path("frontend/_cms/resume-pdf.qmd")
        valid_source = document({"format": "typst"}, "{{cms:summary}}")
        malformed_source = "---\nformat: [unfinished YAML\n---\n"
    marker = cms.preview_generation_marker(store)
    cms.write_preview_generation(marker)
    generation = marker.read_bytes()
    process = preview_clock.start()
    rendered = []

    def verify_failed_save_preserves_output():
        assert process.poll() is None
        assert target.read_bytes() == previous
        assert marker.read_bytes() == generation
        assert rendered == []

    def fix_save():
        source.write_bytes(valid_source)
        if phase == "staging":
            profile_path.write_bytes(valid_profile)

    preview_clock.stop = 16
    preview_clock.edits = {
        1: lambda: source.write_text(malformed_source),
        8: verify_failed_save_preserves_output,
        9: fix_save,
    }
    monkeypatch.setattr(
        cms, "render_resume_pdf", lambda *_: rendered.append(target.read_text())
    )

    assert cms.watch_preview(store, "/bin/quarto", process) is not None

    assert process.poll() == -cms.signal.SIGTERM
    assert not marker.exists()
    assert len(rendered) == 1
    assert summary in rendered[0]
    assert summary in target.read_text()
    assert capsys.readouterr().err.strip()


@pytest.mark.parametrize("timeout", [False, True])
def test_preview_interrupt_terminates_child_and_kills_after_timeout(
    store, monkeypatch, timeout
):
    from atlas import cms

    calls = []
    marker = store.path("frontend/_site-preview/atlas-preview-generation.json")

    class Preview:
        pid = 123

        def poll(self):
            return None

        def wait(self, timeout=None):
            calls.append("wait")
            if timeout is not None and timeout_requested:
                raise cms.subprocess.TimeoutExpired("quarto", timeout)
            return 0

    timeout_requested = timeout
    process = Preview()
    monkeypatch.setattr(cms.shutil, "which", lambda _: "/bin/quarto")
    monkeypatch.setattr(
        cms, "generate", lambda *_, **__: {"site": str(store.path("frontend"))}
    )
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: None)
    monkeypatch.setattr(cms.subprocess, "Popen", lambda *_, **__: process)

    def kill_group(pid, sig):
        assert pid == process.pid
        assert not marker.exists()
        calls.append(sig)

    monkeypatch.setattr(cms.os, "killpg", kill_group)
    monkeypatch.setattr(cms, "preview_group_running", lambda _: False)

    def interrupt(
        actual_store,
        executable,
        actual_process,
        previous,
        *,
        source_browser,
        generation,
    ):
        assert actual_store.root == store.root and actual_process is process
        assert executable == "/bin/quarto"
        assert source_browser is True
        assert json.loads(marker.read_text())["generation"] == generation
        assert marker.is_file()
        raise KeyboardInterrupt

    monkeypatch.setattr(cms, "watch_preview", interrupt)
    invoke(store, "preview", code=130)

    assert calls == (
        [cms.signal.SIGTERM, "wait", cms.signal.SIGKILL, "wait"]
        if timeout
        else [cms.signal.SIGTERM, "wait"]
    )


@pytest.mark.parametrize("already_exited", [False, True])
def test_stop_preview_waits_for_server_after_launcher_exits(
    monkeypatch, already_exited
):
    from atlas import cms

    calls = []

    class Launcher:
        pid = 123

        def poll(self):
            return 0 if already_exited else None

        def wait(self, timeout):
            calls.append("launcher stopped")

    states = iter([True, True, False] if already_exited else [True, False])
    monkeypatch.setattr(
        cms, "preview_group_running", lambda pid: pid == Launcher.pid and next(states)
    )
    monkeypatch.setattr(cms.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    monkeypatch.setattr(cms.time, "sleep", lambda _: calls.append("waiting for server"))

    cms.stop_preview(Launcher())

    assert calls == [
        (Launcher.pid, cms.signal.SIGTERM),
        "launcher stopped",
        "waiting for server",
    ]


@pytest.mark.parametrize("state, running", [("Sl", True), ("Zl", True), ("Z", False)])
def test_preview_group_waits_for_live_threads(monkeypatch, state, running):
    from atlas import cms

    monkeypatch.setattr(
        cms.subprocess, "check_output", lambda *_, **__: f" 456 Sl\n 123 {state}\n"
    )

    assert cms.preview_group_running(123) is running


@pytest.mark.parametrize(
    "change",
    ["template", "layout", "font", "removed_font", "pdf", "missing_pdf", "cache"],
)
def test_resume_pdf_cache_rebuilds_after_input_or_output_changes(
    store, monkeypatch, change
):
    from atlas import cms

    resources = {
        "frontend/_cms/resume-pdf.qmd": b"---\nformat: typst\n---\n{{cms:entries}}",
        "frontend/_cms/resume-pdf/layout.lua": b"-- Layout",
        "frontend/assets/fonts/name.ttf": b"Name font",
    }
    for relative, raw in resources.items():
        path = store.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    calls = []

    def quarto(args, cwd, *, stdout):
        calls.append(args)
        Path(args[2]).with_suffix(".pdf").write_bytes(b"%PDF-1.7\nRendered resume")
        return 0

    monkeypatch.setattr(cms.subprocess, "call", quarto)
    generate(store)
    cms.render_resume_pdf(store, "/bin/quarto")
    if change in ("template", "layout", "font"):
        relative = list(resources)[["template", "layout", "font"].index(change)]
        path = store.path(relative)
        path.write_bytes(path.read_bytes() + b"\nChanged")
    elif change == "removed_font":
        store.path("frontend/assets/fonts/name.ttf").unlink()
    elif change == "pdf":
        store.path("frontend/assets/resume.pdf").write_bytes(b"Changed PDF")
    elif change == "missing_pdf":
        store.path("frontend/assets/resume.pdf").unlink()
    else:
        store.path(".atlas/cms/resume-pdf.cache.yaml").write_bytes(b"Stale cache")
    generate(store)
    cms.render_resume_pdf(store, "/bin/quarto")
    assert len(calls) == 2
    cms.render_resume_pdf(store, "/bin/quarto")
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["exit", "missing", "invalid"])
def test_failed_resume_pdf_render_preserves_download_and_stops_site(
    store, monkeypatch, failure
):
    from atlas import cms

    download = store.path("frontend/assets/resume.pdf")
    download.parent.mkdir(parents=True, exist_ok=True)
    download.write_bytes(b"Previous download")
    cache = store.path(".atlas/cms/resume-pdf.cache.yaml")
    cache.write_bytes(b"Previous cache")
    monkeypatch.setattr(cms.shutil, "which", lambda _: "/bin/quarto")
    calls = []

    def quarto(args, cwd, *, stdout):
        calls.append(args)
        if failure == "invalid":
            Path(args[2]).with_suffix(".pdf").write_bytes(b"An HTML error page")
        return 7 if failure == "exit" else 0

    monkeypatch.setattr(cms.subprocess, "call", quarto)
    invoke(store, "build", code=7 if failure == "exit" else 2)
    assert len(calls) == 1
    assert download.read_bytes() == b"Previous download"
    assert cache.read_bytes() == b"Previous cache"
    assert not list(store.path(".atlas/cms").glob("resume-pdf-*"))


def test_resume_positions_stay_zero_based_after_removal_and_section_changes(store):
    store.new("resume", "Second role", section="employment", body="Second")
    store.new("resume", "Third role", section="employment", body="Third")
    run(store, "resume", "rm", "resume/employment-engineer-example", "--yes")
    entries = [
        item["record"]
        for item in store.ls("resume")
        if item["record"]["section"] == "employment"
    ]
    assert [entry["position"] for entry in entries] == [0, 1]
    run(store, "resume", "edit", "resume/second-role", "--section", "projects")
    assert store.get("resume/third-role")["record"]["position"] == 0
    assert store.get("resume/second-role")["record"]["position"] == 0


def test_clean_checkout_recreates_all_ignored_pages(store):
    for name in ("posts.qmd", "collections.qmd", "resume.qmd"):
        store.path(f"frontend/{name}").unlink(missing_ok=True)
    generate(store, preview=True)
    assert store.path("frontend/posts/example.ipynb").exists()
    assert store.path("frontend/collections/guide.qmd").exists()
    for name in ("posts.qmd", "collections.qmd", "resume.qmd"):
        assert store.path(f"frontend/{name}").exists()


def test_interrupted_notebook_record_save_recovers_as_one_operation(store, monkeypatch):
    created = new_post(store)
    source = store.path("content/posts/attention.ipynb")
    original = source.read_bytes()
    install = store._install

    def fail_record(path, raw):
        if path == store.record_path("post/attention"):
            raise OSError("simulated interrupted save")
        install(path, raw)

    monkeypatch.setattr(store, "_install", fail_record)
    changed = nb.dump(nb.notebook("Saved content"))
    with pytest.raises(OSError):
        store.write_notebook(
            "post/attention", changed, created["revision"], digest(original)
        )
    assert store.path(".atlas/cms/pending.json").exists()
    monkeypatch.setattr(store, "_install", install)
    with store.lock():
        loaded = store.get("post/attention")
    assert source.read_bytes() == changed
    assert loaded["record"]["source_digest"] == digest(changed)
    assert not store.path(".atlas/cms/pending.json").exists()


def test_malformed_yaml_and_symlinks_are_preserved(store):
    created = new_post(store)
    path = store.record_path(created["record"]["id"])
    malformed = path.read_bytes() + b"title: duplicate\n"
    path.write_bytes(malformed)
    invoke(store, "post", "edit", "post/attention", "--title", "Do not erase", code=2)
    assert path.read_bytes() == malformed
    with pytest.raises(ValueError):
        store.path("../outside")
    destination = store.root / "outside"
    destination.mkdir()
    (store.root / "content/link").symlink_to(destination)
    with pytest.raises(ValueError):
        store.path("content/link/file")


def test_internal_edits_ignore_broken_unrelated_records(store):
    new_post(store)
    store.record_path("post/broken").write_text("broken: [yaml")
    run(store, "notes", "post/attention", "--file", "-", input="Still editable")
    assert store.get("post/attention")["record"]["internal_notes"] == "Still editable"


def test_public_sync_removes_draft_images_and_stale_public_sidecars(store):
    created = new_post(store)
    publish(store, created["record"]["id"])
    sidecars = store.path("content/posts/figures")
    sidecars.mkdir()
    (sidecars / "plot.svg").write_text("<svg/>")
    (sidecars / "private.yaml").write_text("notes: private")
    (sidecars / ".hidden").write_text("private")
    run(store, "sync", "--preview")
    assert store.path("frontend/posts/figures/plot.svg").exists()
    assert not store.path("frontend/posts/figures/private.yaml").exists()
    assert not store.path("frontend/posts/figures/.hidden").exists()
    (sidecars / "plot.svg").unlink()
    run(store, "sync", "--preview")
    assert not store.path("frontend/posts/figures/plot.svg").exists()
    assert list(store.path("frontend/assets/cms").glob("*"))
    run(store, "post", "draft", "post/attention")
    run(store, "sync")
    assert not list(store.path("frontend/assets/cms").glob("*"))


def test_source_observation_and_normalized_noop_dates(store):
    created = new_post(store)
    equivalent = run(
        store, "post", "edit", "post/attention", "--tags", " python ,Python,python "
    )
    assert equivalent == created
    source = store.path(created["record"]["source_path"])
    source.write_bytes(nb.dump(nb.notebook("Edited in Jupyter")))
    run(store, "sync", "--preview")
    observed = store.get("post/attention")
    assert observed["record"]["updated_at"] != created["record"]["updated_at"]
    assert observed["record"]["source_digest"] == digest(source.read_bytes())
    run(store, "sync", "--preview")
    assert store.get("post/attention") == observed


def test_reimporting_the_same_image_restores_missing_bytes(store):
    new_post(store)
    published = publish(store, "post/attention")
    image = store.path(published["record"]["thumbnail_path"])
    original = image.read_bytes()
    image.unlink()
    restored = store.update("post/attention", {}, image=store.root / "thumbnail.png")
    assert image.read_bytes() == original
    assert restored == published


@pytest.mark.parametrize(
    "kind, field", [("post", "thumbnail_path"), ("collection", "cover_path")]
)
def test_thumbnail_and_cover_inputs_are_independent_copies_from_outside_the_workspace(
    store, kind, field
):
    image = store.root.parent / f"{store.root.name} Desktop thumbnail.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    original = image.read_bytes()
    identity = store.new(kind, "Image copy")["record"]["id"]
    updated = store.update(identity, {}, image=image)
    copied = store.path(updated["record"][field])
    assert copied.read_bytes() == original == image.read_bytes()
    assert not copied.is_symlink() and not copied.samefile(image)
    image.write_bytes(b"Changed original")
    assert copied.read_bytes() == original
    image.unlink()
    assert copied.read_bytes() == original
    replacement = store.root.parent / f"{store.root.name} replacement.jpg"
    Image.new("RGB", (8, 8), "red").save(replacement)
    flag = "--thumbnail" if kind == "post" else "--cover"
    changed = run(store, kind, "edit", identity, flag, str(replacement))
    assert changed["record"][field] != updated["record"][field]
    assert store.path(changed["record"][field]).read_bytes() == replacement.read_bytes()
    assert copied.read_bytes() == original


def test_build_copies_only_referenced_figures_from_selected_posts(store):
    new_post(store, "Public")
    new_post(store, "Private")
    publish(store, "post/public")
    image = store.root.parent / f"{store.root.name} Desktop figure.svg"
    image.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>')
    public = figure(store, "public", image, caption="A public figure")
    private = figure(store, "private", image)
    original = store.path("content/posts/public.ipynb").read_bytes()
    image.unlink()
    public_copy = store.path(public["image"])
    private_copy = store.path(private["image"])
    generate(store, preview=True)
    assert store.path(f"frontend/assets/cms/post/{private_copy.name}").exists()
    generate(store)
    projected = store.path(f"frontend/assets/cms/post/{public_copy.name}")
    assert projected.read_bytes() == public_copy.read_bytes()
    assert not store.path(f"frontend/assets/cms/post/{private_copy.name}").exists()
    generated = nb.load(store.path("frontend/posts/public.ipynb").read_bytes())
    assert f"../assets/cms/post/{public_copy.name}" in nb.source(generated["cells"][-1])
    assert store.path("content/posts/public.ipynb").read_bytes() == original


def test_terminal_editor_supports_arguments_and_preserves_failed_edit(
    tmp_path, monkeypatch
):
    import shlex
    import sys

    from atlas.cms import edit_text

    editor = tmp_path / "editor with spaces.py"
    editor.write_text(
        "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('Edited prose')\n"
    )
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", shlex.join([sys.executable, str(editor)]))
    assert edit_text("Old prose", ".md") == "Edited prose"
    editor.write_text(
        "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('Unfinished prose')\nsys.exit(1)\n"
    )
    with pytest.raises(ValueError, match="preserved at") as error:
        edit_text("Old prose", ".md")
    saved = Path(str(error.value).split("preserved at ", 1)[1].rstrip("."))
    assert saved.read_text() == "Unfinished prose"
    saved.unlink()


def test_show_reports_the_site_url_path(store):
    created = new_post(store)
    assert (
        run(store, "post", "show", created["record"]["id"])["url_path"]
        == "/posts/attention.html"
    )
    run(store, "collection", "new", "Course", "--description", "A tour")
    shown = run(store, "collection", "show", "collection/course")
    assert shown["url_path"] == "/collections/course.html"
    run(store, "resume", "add", "Role", "--section", "employment", "--file", "-")
    shown = run(store, "resume", "show", "resume/role")
    assert "url_path" not in shown


def test_cms_id_resolves_a_unique_prefix_and_reports_ambiguity(store):
    assert invoke(store, "id", "example").output.strip() == "post/example"
    new_post(store)
    run(store, "post", "new", "Attitudes", "--description", "More attention")
    run(store, "collection", "new", "Course", "--description", "Lessons")
    ambiguous = invoke(store, "id", "att", code=2)
    assert json.loads(ambiguous.output) == {
        "error": "Multiple matches for 'att'.",
        "matches": ["post/attention", "post/attitudes"],
    }
    assert invoke(store, "id", "attenti").output.strip() == "post/attention"
    assert invoke(store, "id", "attitudes").output.strip() == "post/attitudes"
    assert invoke(store, "id", "post/attitude").output.strip() == "post/attitudes"
    assert invoke(store, "id", "course").output.strip() == "collection/course"
    invoke(store, "id", "zzz", code=4)
    identity = run(store, "post", "show", "post/attention")["record"]["id"]
    assert identity == "post/attention"


@pytest.mark.parametrize(
    "query",
    ["invalid-kind/example", "invalid-kind/exam", "/example", "posts/example"],
)
def test_cms_id_rejects_unknown_kind_prefixes(store, query):
    result = invoke(store, "id", query, code=4)
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": f"Unknown record: {query}"}


def test_cms_id_recovers_interrupted_creation_before_matching(store, monkeypatch):
    new_post(store, "Alpha")
    install = store._install

    def fail_record(path, raw):
        if path == store.record_path("post/alpine"):
            raise OSError("simulated interrupted creation")
        install(path, raw)

    with monkeypatch.context() as patch:
        patch.setattr(store, "_install", fail_record)
        with pytest.raises(OSError, match="simulated interrupted creation"):
            store.new("post", "Alpine")
    pending = store.path(".atlas/cms/pending.json")
    assert pending.exists()

    result = invoke(store, "id", "al", code=2)
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": "Multiple matches for 'al'.",
        "matches": ["post/alpha", "post/alpine"],
    }
    assert not pending.exists()
