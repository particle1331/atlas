import copy
import json
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from nbformat.v4 import new_output
from PIL import Image
from typer.testing import CliRunner

from atlas import cms_notebooks as nb
from atlas.cli import app
from atlas.cms_store import Conflict, Store, digest, encode
from atlas.notebook_cli import source_input
from atlas.notebook_ops import figure, outline


@pytest.fixture
def store(tmp_path):
    (tmp_path / "content").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/cms.yaml").write_bytes(encode({"schema": 5}))
    (tmp_path / "content/resume.yaml").write_bytes(
        encode({"title": "Résumé", "summary": ""})
    )
    store = Store(tmp_path)
    created = store.new("post", "Example")
    value = nb.notebook("Original prose")
    value["cells"][0]["attachments"] = {"inline.png": {"image/png": "cG5n"}}
    code = nb.cell("#| label: fig-example\nprint('old')", "code")
    code.update(
        execution_count=7,
        outputs=[{"output_type": "stream", "name": "stdout", "text": "old\n"}],
    )
    code["metadata"]["tags"] = ["example"]
    value["cells"].append(code)
    source = store.path(created["record"]["source_path"])
    store.write_notebook(
        "post/example", nb.dump(value), created["revision"], digest(source.read_bytes())
    )
    return store


def invoke(store, *args, code=0, input=None):
    result = CliRunner().invoke(
        app, ["notebook", "--root", str(store.root), *args], input=input
    )
    assert result.exit_code == code, (result.output, result.exception)
    return result


def notebook(store):
    return nb.load(store.path("content/posts/example.ipynb").read_bytes())


def test_map_and_count_report_sources_without_writing(store, monkeypatch):
    monkeypatch.setenv("COLUMNS", "160")
    missing = store.new("post", "Missing")["record"]
    store.path(missing["source_path"]).unlink()
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")

    result = invoke(store, "map")
    rows = result.stdout.replace("│", " ")
    assert re.search(
        r"post/example\s+draft\s+2\s+content/posts/example[.]ipynb\s+Example", rows
    )
    assert re.search(
        r"post/missing\s+draft\s+missing\s+content/posts/missing[.]ipynb\s+Missing",
        rows,
    )
    assert invoke(store, "count", "Example").stdout == (
        f"post/example: 2 cells (notebook:{digest(before)})\n"
    )
    assert path.read_bytes() == before
    assert store.get("post/example") == record
    assert not store.path(missing["source_path"]).exists()


def test_kernels_reports_available_specs_without_starting_them(store, monkeypatch):
    monkeypatch.setattr(
        "jupyter_client.kernelspec.KernelSpecManager.get_all_specs",
        lambda _: {
            "python3": {"spec": {"display_name": "Python 3"}},
            "custom": {"spec": {}},
        },
    )
    result = invoke(store, "kernels")
    assert "Display name" in result.stdout
    rows = result.stdout.replace("│", " ")
    assert re.search(r"custom\s+custom", rows)
    assert re.search(r"python3\s+Python 3", rows)
    assert result.stdout.index("custom") < result.stdout.index("python3")


@pytest.mark.parametrize(
    "locator, expected", [(("--index", "0"), []), (("--tag", "example"), ["example"])]
)
def test_reading_tags_does_not_write(store, locator, expected):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    assert json.loads(invoke(store, "tag", "example", *locator).stdout) == expected
    assert path.read_bytes() == before
    assert store.get("post/example") == record


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "# Introduction\n\n### Results ###",
            [(1, 1, "Introduction"), (3, 3, "Results")],
        ),
        ("<!--\n# Hidden\n-->\n\n## Visible", [(5, 2, "Visible")]),
        ("<pre>\n# Hidden\n</pre>\n\n## Visible", [(5, 2, "Visible")]),
        (
            "```md\n# Hidden\n```\n\n~~~text\n## Also hidden\n~~~\n\n# Visible",
            [(9, 1, "Visible")],
        ),
        ("    # Python comment\n\n## Visible", [(3, 2, "Visible")]),
        ("***\n---", []),
        (
            "> ## Quoted\n\n- ### Listed",
            [(1, 2, "Quoted"), (3, 3, "Listed")],
        ),
        (
            "First line\nSecond line\n---\n\nChapter\n====",
            [(1, 2, "First line Second line"), (5, 1, "Chapter")],
        ),
        ("Ordinary prose with # inline markers", []),
    ],
    ids=[
        "atx",
        "comment",
        "html",
        "fences",
        "indented-code",
        "rules",
        "containers",
        "setext",
        "no-headings",
    ],
)
def test_outline_follows_markdown_blocks(source, expected):
    assert outline(nb.notebook(source)) == [
        {"cell_index": 0, "line": line, "level": level, "text": text}
        for line, level, text in expected
    ]


def test_outline_cli_reports_cell_indices_and_revision_without_writing(store):
    invoke(store, "edit-cell", "example", "--index", "0", "--content", "> ## Quoted")
    invoke(
        store,
        "edit-cell",
        "example",
        "--index",
        "1",
        "--content",
        "# Not a Markdown heading",
    )
    invoke(store, "append-cell", "example", "--content", "## Results")
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")

    result = json.loads(invoke(store, "outline", "Example").stdout)

    assert result == {
        "id": "post/example",
        "revision": "notebook:" + digest(before),
        "headings": [
            {"cell_index": 0, "line": 1, "level": 2, "text": "Quoted"},
            {"cell_index": 2, "line": 1, "level": 2, "text": "Results"},
        ],
    }
    assert path.read_bytes() == before
    assert store.get("post/example") == record


def test_cell_mutations_finish_and_preserve_other_content(store):
    before = notebook(store)
    # A real CLI subprocess with a timeout catches accidental nested flock calls
    # without hanging the test runner indefinitely.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "atlas",
            "notebook",
            "--root",
            str(store.root),
            "edit-cell",
            "post/example",
            "--index",
            "1",
            "--content",
            "print('new')",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    edited = notebook(store)
    assert edited["cells"][0] == before["cells"][0]
    assert edited["cells"][1] == before["cells"][1] | {"source": ["print('new')"]}
    record = store.get("post/example")["record"]
    assert record["source_digest"] == digest(
        store.path(record["source_path"]).read_bytes()
    )

    invoke(store, "append-cell", "example", "--content", "Last")
    invoke(store, "insert-cell", "example", "--before", "0", "--content", "First")
    invoke(store, "tag", "example", "--index", "0", "--add", "temporary")
    invoke(store, "remove-cell", "example", "--tag", "temporary")
    invoke(store, "clear-outputs", "example", "--index", "1")
    after = notebook(store)
    assert [nb.source(cell) for cell in after["cells"]] == [
        "Original prose",
        "print('new')",
        "Last",
    ]
    assert after["cells"][1]["outputs"] == []


@pytest.mark.parametrize(
    "locator, position",
    [
        (("--before", "0"), 0),
        (("--after", "0"), 1),
        (("--after", "1"), 2),
        (("--tag", "example"), 2),
        (("--label", "fig-example"), 2),
    ],
)
def test_insert_locators_preserve_existing_cells(store, locator, position):
    before = notebook(store)
    before["cells"].append(nb.cell("Trailing prose"))
    store.path("content/posts/example.ipynb").write_bytes(nb.dump(before))
    invoke(
        store,
        "insert-cell",
        "example",
        *locator,
        "--type",
        "code",
        "--content",
        "print('inserted')",
    )
    after = notebook(store)
    inserted = after["cells"][position]
    assert inserted == {
        "id": inserted["id"],
        "cell_type": "code",
        "metadata": {},
        "source": ["print('inserted')"],
        "execution_count": None,
        "outputs": [],
    }
    assert inserted["id"] not in {cell["id"] for cell in before["cells"]}
    del after["cells"][position]
    assert after == before


@pytest.mark.parametrize(
    "locator, message, preserved",
    [
        ((), "Use exactly one of", False),
        (("--before", "0", "--after", "0"), "Use exactly one of", False),
        (("--tag", "example", "--label", "fig-example"), "Use exactly one of", False),
        (("--after", "2"), "Insert position is out of range.", True),
        (("--before", "3"), "Insert position is out of range.", True),
        (("--tag", "absent"), "No notebook cell matched that locator.", True),
        (("--tag", "ambiguous"), "Ambiguous locator matched cells", True),
    ],
)
def test_invalid_insert_does_not_write(store, locator, message, preserved):
    path = store.path("content/posts/example.ipynb")
    value = notebook(store)
    for cell in value["cells"]:
        cell["metadata"].setdefault("tags", []).append("ambiguous")
    path.write_bytes(nb.dump(value))
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(
        store, "insert-cell", "example", *locator, "--content", "Unsaved text", code=2
    )
    assert message in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record
    if preserved:
        error = json.loads(result.stderr)["error"]
        recovered = Path(error.split("preserved at ", 1)[1].removesuffix("."))
        assert recovered.parent == store.path(".atlas/cms/edits")
        assert recovered.read_text() == "Unsaved text"


@pytest.mark.parametrize(
    "locator, targets",
    [
        ((), [1, 3]),
        (("--from", "0"), [1, 3]),
        (("--from", "2"), [3]),
        (("--index", "1"), [1]),
        (("--index", "3"), [3]),
        (("--tag", "later"), [3]),
        (("--label", "fig-later"), [3]),
    ],
)
def test_clear_outputs_changes_only_selected_code_outputs(store, locator, targets):
    before = notebook(store)
    later = nb.cell("#| label: fig-later\nprint('later')", "code")
    later["metadata"]["tags"] = ["later"]
    later.update(
        execution_count=8,
        outputs=[{"output_type": "stream", "name": "stdout", "text": "later\n"}],
    )
    before["cells"].extend([nb.cell("Between code cells"), later])
    store.path("content/posts/example.ipynb").write_bytes(nb.dump(before))
    expected = copy.deepcopy(before)
    for index in targets:
        expected["cells"][index]["outputs"] = []

    invoke(store, "clear-outputs", "example", *locator)

    assert notebook(store) == expected


@pytest.mark.parametrize(
    "locator, message",
    [
        (("--from", "1", "--index", "1"), "Use --from alone."),
        (("--from", "1", "--tag", "example"), "Use --from alone."),
        (("--from", "1", "--label", "fig-example"), "Use --from alone."),
        (("--from", "2"), "Start index is out of range."),
        (("--index", "0"), "No code cells matched that locator."),
        (("--tag", "absent"), "No code cells matched that locator."),
    ],
)
def test_invalid_clear_outputs_does_not_write(store, locator, message):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(store, "clear-outputs", "example", *locator, code=2)
    assert message in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record


@pytest.mark.parametrize(
    "command",
    [
        ("insert-cell", "--after", "0", "--content", "Stale edit"),
        ("clear-outputs", "--from", "0"),
    ],
)
def test_insert_and_clear_outputs_reject_stale_revision(store, command):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(
        store,
        command[0],
        "example",
        *command[1:],
        "--expected-revision",
        "notebook:" + "0" * 64,
        code=3,
    )
    assert f"current revision is notebook:{digest(before)}" in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record


def test_remove_requires_an_explicit_unambiguous_locator(store):
    original = notebook(store)
    invoke(store, "remove-cell", "example", code=2)
    invoke(store, "remove-cell", "example", "--index", "0", "--tag", "example", code=2)
    assert notebook(store) == original
    value = copy.deepcopy(original)
    value["cells"].append(nb.cell("#| label: fig-example\nprint('another')", "code"))
    store.path("content/posts/example.ipynb").write_bytes(nb.dump(value))
    invoke(store, "remove-cell", "example", "--label", "fig-example", code=2)
    assert notebook(store) == value


def test_remove_missing_tag_does_not_write(store):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(store, "remove-cell", "example", "--tag", "absent", code=2)
    assert "No notebook cells matched that locator." in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record


@pytest.mark.parametrize("mode", ["file", "stdin-file", "stdin-file-tty", "pipe"])
@pytest.mark.parametrize(
    "text",
    ["", "Single line without a final newline", "Updated café prose\n第二行\n"],
    ids=["empty", "single-line", "multiline-unicode"],
)
def test_edit_accepts_noninteractive_source_without_changing_other_cells(
    store, mode, text, monkeypatch
):
    before = notebook(store)
    args = []
    stdin = text

    def unexpected_editor(*_):
        pytest.fail("Noninteractive source must not open an editor")

    monkeypatch.setattr("atlas.notebook_cli.edit_text", unexpected_editor)
    if mode == "file":
        path = store.root / "source.md"
        path.write_text(text)
        args = ["--file", str(path)]
        stdin = "Unrelated stdin text"
    elif mode in {"stdin-file", "stdin-file-tty"}:
        args = ["--file", "-"]
        if mode == "stdin-file-tty":
            # The actual runner stdin is a TTY, including for Click's accessors.
            class TerminalInput(BytesIO):
                def isatty(self):
                    return True

            monkeypatch.setattr(
                "typer.testing.make_input_stream",
                lambda value, charset: TerminalInput(value.encode(charset)),
            )
    result = invoke(store, "edit-cell", "example", "--index", "0", *args, input=stdin)
    assert json.loads(result.stdout)["changed"] is True
    expected = copy.deepcopy(before)
    expected["cells"][0]["source"] = text.splitlines(keepends=True)
    assert notebook(store) == expected


def test_named_file_source_does_not_read_stdin(tmp_path, monkeypatch):
    path = tmp_path / "source.md"
    text = "File content, not stdin.\n"
    path.write_text(text)

    def unexpected_read(*_):
        pytest.fail("A named source file must not consume stdin")

    monkeypatch.setattr(
        sys, "stdin", SimpleNamespace(isatty=lambda: False, read=unexpected_read)
    )

    assert source_input(None, path, "Original prose", ".md") == text


def test_edit_missing_file_does_not_fall_back_to_stdin(store):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    missing = store.root / "missing-source.md"

    result = invoke(
        store,
        "edit-cell",
        "example",
        "--index",
        "0",
        "--file",
        str(missing),
        input="Piped text must not replace the missing file.",
        code=2,
    )

    assert missing.name in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record


def test_edit_rejects_conflicting_source_inputs_without_writing(store):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(
        store,
        "edit-cell",
        "example",
        "--index",
        "0",
        "--content",
        "Content argument",
        "--file",
        "-",
        input="Piped input",
        code=2,
    )
    assert "Use only one of --content or --file." in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record


def test_editor_can_clear_a_cell(monkeypatch):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("atlas.notebook_cli.edit_text", lambda *_: "")
    assert source_input(None, None, "Old prose", ".md") == ""
    monkeypatch.setattr("atlas.notebook_cli.edit_text", lambda *_: None)
    assert source_input(None, None, "Old prose", ".md") == "Old prose"


def test_stale_source_preserves_the_editor_input(store, monkeypatch):
    def edit(*_):
        value = notebook(store)
        value["cells"][0]["source"] = ["Concurrent edit"]
        store.path("content/posts/example.ipynb").write_bytes(nb.dump(value))
        return "My unsaved prose"

    monkeypatch.setattr("atlas.notebook_cli.source_input", edit)
    result = invoke(store, "edit-cell", "example", "--index", "0", code=3)
    assert "preserved at" in result.stderr
    assert nb.source(notebook(store)["cells"][0]) == "Concurrent edit"
    assert (
        next(store.path(".atlas/cms/edits").glob("*.txt")).read_text()
        == "My unsaved prose"
    )


def test_cat_locators_search_and_stale_revision(store):
    result = invoke(store, "cat", "Example", "--index", "0:1", "--with-revision")
    assert "> cell 0 [markdown]" in result.stdout
    assert "> cell 1" not in result.stdout
    token = result.stdout.splitlines()[0].removeprefix("> source-revision: ")
    assert (
        "print('old')"
        in invoke(store, "cat", "example", "--label", "fig-example").stdout
    )
    assert "cell 0" in invoke(store, "find", "original PROSE").stdout
    invoke(store, "find", " ", code=2)
    invoke(store, "edit-cell", "example", "--index", "0", "--content", "Changed")
    before = notebook(store)
    invoke(
        store,
        "remove-cell",
        "example",
        "--index",
        "0",
        "--expected-revision",
        token,
        code=3,
    )
    assert notebook(store) == before


def test_unchanged_string_source_keeps_bytes_and_public_date(store):
    value = notebook(store)
    value["cells"][0]["source"] = "Original prose"
    source = store.path("content/posts/example.ipynb")
    source.write_bytes(nb.dump(value))
    original = source.read_bytes()
    record = store.get("post/example")
    result = invoke(
        store, "edit-cell", "example", "--index", "0", "--content", "Original prose"
    )
    assert json.loads(result.stdout)["changed"] is False
    assert source.read_bytes() == original
    assert store.get("post/example") == record


def external_image(store, extension=".png"):
    image = store.root.parent / f"{store.root.name} Desktop image{extension}"
    if extension == ".svg":
        image.write_bytes(
            b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="blue"/></svg>\n'
        )
    else:
        Image.new("RGB", (8, 8), "blue").save(image)
    return image


def test_figure_label_requires_replace_without_writing(store):
    path = store.path("content/posts/example.ipynb")
    before = path.read_bytes()
    record = store.get("post/example")
    result = invoke(
        store,
        "figure",
        "example",
        str(store.root / "unused.png"),
        "--label",
        "fig-example",
        code=2,
    )
    assert "Use --label with --replace to select an existing figure." in result.stderr
    assert path.read_bytes() == before
    assert store.get("post/example") == record
    assert not store.path("content/images/post").exists()


@pytest.mark.parametrize("extension", [".png", ".jpg", ".jpeg", ".svg"])
def test_figure_copies_external_bytes_and_appends_a_quarto_cell(store, extension):
    image = external_image(store, extension)
    raw = image.read_bytes()
    before = notebook(store)
    result = json.loads(
        invoke(
            store,
            "figure",
            "example",
            str(image),
            "--caption",
            "A [useful] figure",
            "--alt",
            'A "blue" square.',
        ).stdout
    )
    copied = store.path(result["image"])
    assert re.fullmatch(
        r"content/images/post/example-[0-9a-f]{32}" + re.escape(extension),
        result["image"],
    )
    assert copied.read_bytes() == raw == image.read_bytes()
    assert not copied.is_symlink() and not copied.samefile(image)
    after = notebook(store)
    assert after["cells"][:-1] == before["cells"]
    assert result["index"] == 2
    cell = after["cells"][-1]
    assert cell["cell_type"] == "markdown"
    assert (
        nb.source(cell)
        == f'![A \\[useful\\] figure](../images/post/{copied.name}){{#{result["label"]} fig-alt="A \\"blue\\" square."}}\n'
    )
    assert (
        copied.name
        in invoke(store, "cat", "example", "--label", result["label"]).stdout
    )
    assert store.get("post/example")["record"]["source_digest"] == digest(
        store.path("content/posts/example.ipynb").read_bytes()
    )
    image.write_bytes(b"Changed on the Desktop")
    assert copied.read_bytes() == raw
    image.unlink()
    assert copied.read_bytes() == raw


@pytest.mark.parametrize("position", [0, 1, 2])
def test_figure_inserts_at_a_zero_based_position_without_replacing_cells(
    store, position
):
    image = external_image(store)
    before = notebook(store)
    result = json.loads(
        invoke(store, "figure", "example", str(image), "--index", str(position)).stdout
    )
    after = notebook(store)
    assert result["index"] == position
    assert after["cells"][:position] + after["cells"][position + 1 :] == before["cells"]


def test_repeated_figure_imports_get_distinct_names(store):
    image = external_image(store)
    first = json.loads(invoke(store, "figure", "example", str(image)).stdout)
    second = json.loads(invoke(store, "figure", "example", str(image)).stdout)
    assert first["image"] != second["image"]
    assert first["label"] != second["label"]
    assert (
        store.path(first["image"]).read_bytes()
        == store.path(second["image"]).read_bytes()
        == image.read_bytes()
    )


@pytest.mark.parametrize("locator", ["index", "label"])
@pytest.mark.parametrize("extension", [".jpeg", ".svg"])
def test_replacing_a_figure_changes_only_its_image_url(store, locator, extension):
    original = json.loads(
        invoke(store, "figure", "example", str(external_image(store))).stdout
    )
    value = notebook(store)
    cell = value["cells"][2]
    old_url = "<../images/post/" + store.path(original["image"]).name + ">"
    text = f'Introductory text.\n\n![My edited caption *with emphasis*\nand a second line]({old_url} "Image title"){{#{original["label"]} width=80% fig-align="left" fig-alt="Original alt text"}}\n\nTrailing text.\n'
    cell["source"] = text.splitlines(keepends=True)
    cell["metadata"]["tags"] = ["keep-me"]
    cell["attachments"] = {"inline.png": {"image/png": "cG5n"}}
    store.path("content/posts/example.ipynb").write_bytes(nb.dump(value))
    image = external_image(store, extension)
    flags = ["--index", "2"] if locator == "index" else ["--label", original["label"]]
    result = json.loads(
        invoke(store, "figure", "example", str(image), "--replace", *flags).stdout
    )
    new_url = "<../images/post/" + store.path(result["image"]).name + ">"
    after = notebook(store)
    assert len(after["cells"]) == len(value["cells"])
    assert after["cells"][:2] == value["cells"][:2]
    assert after["cells"][2] == cell | {
        "source": text.replace(old_url, new_url).splitlines(keepends=True)
    }
    assert result["label"] == original["label"] and result["index"] == 2
    assert store.path(result["image"]).suffix == extension
    assert store.path(result["image"]).read_bytes() == image.read_bytes()
    assert store.path(original["image"]).exists()
    assert (
        store.path(result["image"]).name
        in invoke(store, "cat", "example", "--label", original["label"]).stdout
    )


@pytest.mark.parametrize(
    "case, code",
    [
        ("no-locator", 2),
        ("both", 2),
        ("code", 2),
        ("no-image", 2),
        ("multiple", 2),
        ("caption", 2),
        ("stale", 3),
    ],
)
def test_failed_figure_replacement_preserves_cells_and_assets(store, case, code):
    original = json.loads(
        invoke(store, "figure", "example", str(external_image(store))).stdout
    )
    value = notebook(store)
    flags = ["--index", "2"]
    if case == "no-locator":
        flags = []
    elif case == "both":
        flags += ["--label", original["label"]]
    elif case == "code":
        flags = ["--index", "1"]
    elif case == "no-image":
        flags = ["--index", "0"]
    elif case == "multiple":
        value["cells"][2]["source"] *= 2
        store.path("content/posts/example.ipynb").write_bytes(nb.dump(value))
    elif case == "caption":
        flags += ["--caption", "Do not overwrite"]
    elif case == "stale":
        flags += ["--expected-revision", "notebook:" + "0" * 64]
    before = store.get("post/example")
    assets = {
        path: path.read_bytes()
        for path in store.path("content/images").rglob("*")
        if path.is_file()
    }
    invoke(
        store,
        "figure",
        "example",
        str(external_image(store, ".svg")),
        "--replace",
        *flags,
        code=code,
    )
    assert notebook(store) == value
    assert store.get("post/example") == before
    assert {
        path: path.read_bytes()
        for path in store.path("content/images").rglob("*")
        if path.is_file()
    } == assets


def test_figure_replacement_can_repair_a_missing_image(store):
    original = json.loads(
        invoke(store, "figure", "example", str(external_image(store))).stdout
    )
    store.path(original["image"]).unlink()
    result = json.loads(
        invoke(
            store,
            "figure",
            "example",
            str(external_image(store, ".svg")),
            "--replace",
            "--index",
            "2",
        ).stdout
    )
    assert store.path(result["image"]).is_file()
    assert result["label"] == original["label"]


@pytest.mark.parametrize(
    "case, code",
    [
        ("index", 2),
        ("stale", 3),
        ("missing", 2),
        ("invalid", 2),
        ("invalid-svg", 2),
        ("not-svg", 2),
    ],
)
def test_failed_figure_import_does_not_change_the_notebook_or_copy_an_image(
    store, case, code
):
    image = external_image(
        store, ".svg" if case in ("invalid-svg", "not-svg") else ".png"
    )
    options = []
    if case == "index":
        options = ["--index", "3"]
    elif case == "stale":
        options = ["--expected-revision", "notebook:" + "0" * 64]
    elif case == "missing":
        image.unlink()
    elif case in ("invalid", "invalid-svg"):
        image.write_bytes(b"Not an image")
    elif case == "not-svg":
        image.write_bytes(b"<html/>")
    before = notebook(store)
    record = store.get("post/example")
    invoke(store, "figure", "example", str(image), *options, code=code)
    assert notebook(store) == before
    assert store.get("post/example") == record
    assert not list(store.path("content/images").rglob("*"))


def test_concurrent_metadata_edit_rejects_the_figure_without_an_orphan_copy(
    store, monkeypatch
):
    image = external_image(store)
    read = store.image

    def read_then_edit(*args, **kwargs):
        result = read(*args, **kwargs)
        store.update("post/example", {"title": "Concurrent title"})
        return result

    monkeypatch.setattr(store, "image", read_then_edit)
    before = notebook(store)
    with pytest.raises(Conflict):
        figure(store, "example", image)
    assert notebook(store) == before
    assert not list(store.path("content/images").rglob("*"))


def test_interrupted_figure_save_recovers_the_copy_notebook_and_metadata(
    store, monkeypatch
):
    image = external_image(store)
    install = store._install

    def fail_metadata(target, raw):
        if target == store.record_path("post/example"):
            raise OSError("Interrupted save")
        install(target, raw)

    monkeypatch.setattr(store, "_install", fail_metadata)
    with pytest.raises(OSError):
        figure(store, "example", image)
    assert store.path(".atlas/cms/pending.json").exists()
    monkeypatch.setattr(store, "_install", install)
    with store.lock():
        record = store.get("post/example")["record"]
    copied = next(store.path("content/images/post").glob("*.png"))
    assert copied.read_bytes() == image.read_bytes()
    assert copied.name in nb.source(notebook(store)["cells"][-1])
    assert record["source_digest"] == digest(
        store.path(record["source_path"]).read_bytes()
    )


def test_output_extracts_multiline_svg_without_changing_notebook(store):
    value = notebook(store)
    svg = ["<svg>\n", "<text>Hi</text>\n", "</svg>"]
    value["cells"][1]["outputs"] = [
        {
            "output_type": "display_data",
            "metadata": {},
            "data": {"image/svg+xml": svg, "text/plain": ["A plot"]},
        }
    ]
    source = store.path("content/posts/example.ipynb")
    source.write_bytes(nb.dump(value))
    original = source.read_bytes()
    invoke(store, "output", "example", "--index", "1", "--output", "0")
    assert next(
        store.path(".atlas/cms/notebook-output").glob("*.svg")
    ).read_text() == "".join(svg)
    assert source.read_bytes() == original


def test_diff_has_separate_removed_and_added_lines(store):
    subprocess.run(["git", "init", "-q", str(store.root)], check=True)
    subprocess.run(["git", "add", "content"], cwd=store.root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "Initial",
        ],
        cwd=store.root,
        check=True,
    )
    invoke(store, "clear-outputs", "example", "--index", "1")
    assert notebook(store)["cells"][1]["outputs"] == []
    source = store.path("content/posts/example.ipynb")
    before = source.read_bytes()
    record = store.get("post/example")
    assert invoke(store, "diff", "example").stdout == ""
    assert source.read_bytes() == before
    assert store.get("post/example") == record
    invoke(store, "edit-cell", "example", "--index", "1", "--content", "print('new')")
    result = invoke(store, "diff", "example")
    assert "-print('old')\n+print('new')\n" in result.stdout


def test_indexed_run_keeps_prefix_outputs_and_reports_errors(store, monkeypatch):
    before = notebook(store)
    setup = nb.cell("setup = 42", "code")
    setup.update(
        execution_count=7,
        outputs=[
            {"output_type": "stream", "name": "stdout", "text": "Original setup output"}
        ],
    )
    before["cells"].insert(1, setup)
    store.path("content/posts/example.ipynb").write_bytes(nb.dump(before))

    class Client:
        def __init__(self, target, **kwargs):
            self.target = target
            assert kwargs["allow_errors"] is True
            assert kwargs["resources"]["metadata"]["path"] == str(
                store.root / "content/posts"
            )

        def execute(self):
            assert len(self.target.cells) == 3
            self.target.cells[1].outputs = [
                new_output("stream", name="stdout", text="setup")
            ]
            self.target.cells[2].outputs = [
                new_output("error", ename="ExampleError", evalue="failed", traceback=[])
            ]
            self.target.cells[2].execution_count = 2

    monkeypatch.setattr("nbclient.NotebookClient", Client)
    result = invoke(store, "run", "example", "--index", "2", code=1)
    assert json.loads(result.stdout)["errors"][0]["index"] == 2
    after = notebook(store)
    assert after["cells"][1] == before["cells"][1]
    assert after["cells"][2]["outputs"][0]["ename"] == "ExampleError"


def test_run_retains_results_when_source_changes(store, monkeypatch):
    class Client:
        def __init__(self, target, **kwargs):
            self.target = target

        def execute(self):
            self.target.cells[1].outputs = [
                new_output("stream", name="stdout", text="Result")
            ]
            value = notebook(store)
            value["cells"][0]["source"] = ["Concurrent edit"]
            store.path("content/posts/example.ipynb").write_bytes(nb.dump(value))

    monkeypatch.setattr("nbclient.NotebookClient", Client)
    invoke(store, "run", "example", code=3)
    assert nb.source(notebook(store)["cells"][0]) == "Concurrent edit"
    saved = next(store.path(".atlas/cms/execution-conflicts").glob("*.ipynb"))
    assert nb.load(saved.read_bytes())["cells"][1]["outputs"][0]["text"] == "Result"


def test_unchanged_execution_returns_the_actual_source_revision(store, monkeypatch):
    source = store.path("content/posts/example.ipynb")
    original = json.dumps(notebook(store), indent=4).encode()
    source.write_bytes(original)
    record = store.get("post/example")

    class Client:
        def __init__(self, target, **kwargs):
            pass

        def execute(self):
            pass

    monkeypatch.setattr("nbclient.NotebookClient", Client)
    result = invoke(store, "run", "example", "--index", "1")
    assert json.loads(result.stdout)["revision"] == "notebook:" + digest(original)
    assert source.read_bytes() == original
    assert store.get("post/example") == record


def test_recovery_conflict_cannot_block_preserving_execution_results(
    store, monkeypatch
):
    def conflict(_):
        raise Conflict("Interrupted save conflicts with external edits")

    class Client:
        def __init__(self, target, **kwargs):
            self.target = target

        def execute(self):
            self.target.cells[1].outputs = [
                new_output("stream", name="stdout", text="Result")
            ]
            monkeypatch.setattr(Store, "recover", conflict)

    monkeypatch.setattr("nbclient.NotebookClient", Client)
    before = notebook(store)
    result = invoke(store, "run", "example", code=3)
    assert "results retained at" in result.stderr
    saved = next(store.path(".atlas/cms/execution-conflicts").glob("*.ipynb"))
    assert nb.load(saved.read_bytes())["cells"][1]["outputs"][0]["text"] == "Result"
    assert notebook(store) == before
