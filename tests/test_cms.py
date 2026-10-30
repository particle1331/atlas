import json
import re
from collections import Counter
from pathlib import Path

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


@pytest.fixture
def workspace(tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "posts").mkdir(parents=True)
    (frontend / "collections").mkdir()
    (frontend / "_quarto.yml").write_text(
        "project:\n  type: website\nexecute:\n  enabled: false\n"
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
    assert post["status"] == "draft"  # The scaffold has no required thumbnail.
    assert post["tags"] == ["Python"]
    raw = workspace.path("content/posts/example.ipynb").read_bytes()
    assert nb.source(nb.load(raw)["cells"][0]) == "## Original body\n\nWrite freely."
    assert workspace.path("backend/posts/example.yaml").exists()
    assert workspace.path("backend/collections/guide.yaml").exists()
    assert workspace.path("backend/cms.yaml").exists()
    assert workspace.path("content/collections/guide.yaml").exists()
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
        "content/collections/guide.yaml": b"# Editable collection text\ntitle: Hand-edited guide\nshort_description: A new summary\nlong_description: |\n  Hand-edited introduction.\n",
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
    assert new_post(store)["record"]["id"] != "post/attention"
    invoke(store, "post", "edit", "post/attention", "--tags", "a,,b", code=2)


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
    assert changed["record"]["source_digest"] == digest(source.read_bytes())
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
    invoke(store, "post", "publish", "post/public", code=2)
    publish(store, "post/public")
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
    run(
        store,
        "collection",
        "edit",
        "collection/reading",
        "--cover",
        str(store.root / "thumbnail.png"),
        "--cover-caption",
        "*Public cover* by the artist",
    )
    run(store, "collection", "add", "collection/reading", "post/private")
    run(store, "collection", "add", "collection/reading", "post/public")
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
    assert "Related:" not in store.path("frontend/posts/public.ipynb").read_text()
    previous = store.path("frontend/posts/public.ipynb").read_bytes()
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


@pytest.mark.parametrize("command", ["build", "preview"])
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

    def quarto(args, cwd):
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
            assert "typst" in calls[-2]
            assert download.read_bytes().startswith(b"%PDF-")
            assert ("--profile" in args) == (command == "preview")
            if command == "preview":
                assert args[args.index("--port") + 1] == "4300"
        return 0

    monkeypatch.setattr(cms.subprocess, "call", quarto)
    args = [command] + (["--port", "4300"] if command == "preview" else [])
    invoke(store, *args)
    first = download.read_bytes()
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
    assert len(calls) == 4
    assert download.read_bytes() != first
    assert b"A freshly edited summary." in download.read_bytes()
    assert b"A freshly edited accomplishment." in download.read_bytes()
    assert not list(store.path(".atlas/cms").glob("resume-pdf-*"))


@pytest.mark.parametrize("failure", ["exit", "missing", "invalid"])
def test_failed_resume_pdf_render_preserves_download_and_stops_site(
    store, monkeypatch, failure
):
    from atlas import cms

    download = store.path("frontend/assets/resume.pdf")
    download.parent.mkdir(parents=True, exist_ok=True)
    download.write_bytes(b"Previous download")
    monkeypatch.setattr(cms.shutil, "which", lambda _: "/bin/quarto")
    calls = []

    def quarto(args, cwd):
        calls.append(args)
        if failure == "invalid":
            Path(args[2]).with_suffix(".pdf").write_bytes(b"An HTML error page")
        return 7 if failure == "exit" else 0

    monkeypatch.setattr(cms.subprocess, "call", quarto)
    invoke(store, "build", code=7 if failure == "exit" else 2)
    assert len(calls) == 1
    assert download.read_bytes() == b"Previous download"
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
