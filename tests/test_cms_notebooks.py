import json

import pytest

from atlas import cms_notebooks as nb


@pytest.mark.parametrize(
    "value, message",
    [
        pytest.param([], "Expected a version 4", id="non-object-root"),
        pytest.param({"cells": []}, "Expected a version 4", id="missing-version"),
        pytest.param({"nbformat": 3, "cells": []}, "Expected a version 4", id="v3"),
        pytest.param({"nbformat": 4}, "Notebook cells must be a list", id="no-cells"),
        pytest.param(
            {"nbformat": 4, "cells": {}},
            "Notebook cells must be a list",
            id="non-list-cells",
        ),
    ],
)
def test_load_rejects_malformed_notebook(value, message):
    with pytest.raises(ValueError, match=message):
        nb.load(json.dumps(value).encode())


@pytest.mark.parametrize(
    "cell, message",
    [
        pytest.param(None, r"Invalid notebook cell\.", id="non-object-cell"),
        pytest.param(
            {"source": ""}, r"Invalid notebook cell\.", id="missing-cell-type"
        ),
        pytest.param(
            {"cell_type": "unknown", "source": ""},
            r"Invalid notebook cell\.",
            id="unknown-cell-type",
        ),
        pytest.param(
            {"cell_type": [], "source": ""},
            r"Invalid notebook cell\.",
            id="array-cell-type",
        ),
        pytest.param(
            {"cell_type": {}, "source": ""},
            r"Invalid notebook cell\.",
            id="object-cell-type",
        ),
        pytest.param(
            {"cell_type": "markdown"},
            "Invalid notebook cell source",
            id="missing-source",
        ),
        pytest.param(
            {"cell_type": "markdown", "source": 1},
            "Invalid notebook cell source",
            id="non-text-source",
        ),
        pytest.param(
            {"cell_type": "markdown", "source": ["first\n", 2]},
            "Invalid notebook cell source",
            id="non-text-source-line",
        ),
    ],
)
def test_load_rejects_malformed_cell(cell, message):
    with pytest.raises(ValueError, match=message):
        nb.load(json.dumps({"nbformat": 4, "cells": [cell]}).encode())


@pytest.mark.parametrize("kind", ["markdown", "code", "raw"])
@pytest.mark.parametrize(
    "source", ["first\nsecond", ["first\n", "second"]], ids=["string", "list"]
)
def test_load_accepts_notebook_cell_sources(kind, source):
    cell = {"cell_type": kind, "id": "example", "metadata": {}, "source": source}
    if kind == "code":
        cell.update(execution_count=None, outputs=[])
    value = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [cell]}

    loaded = nb.load(json.dumps(value).encode())

    assert loaded == value
    assert nb.source(loaded["cells"][0]) == "first\nsecond"


def test_dump_load_preserves_notebook_content():
    value = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"title": "Résumé"},
        "cells": [
            {
                "cell_type": "markdown",
                "id": "prose",
                "metadata": {"tags": ["résumé"]},
                "source": ["![Café](attachment:café.png)\n"],
                "attachments": {"café.png": {"image/png": "cG5n"}},
            },
            {
                "cell_type": "code",
                "id": "example",
                "metadata": {},
                "source": "print('你好')",
                "execution_count": 7,
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": "你好\n"}
                ],
            },
        ],
    }

    serialized = nb.dump(value)

    assert "Résumé".encode("utf-8") in serialized
    assert nb.load(serialized) == value
