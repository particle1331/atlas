"""Notebook source operations. Rendering and editing never execute cells."""

import json
import re
from copy import deepcopy
from uuid import uuid4

IMAGE_LINK = re.compile(r"(!\[[\s\S]*?\]\()(<[^>\n]+>|[^)\s]+)(?=\s|\))")


def cell(source: str = "", kind: str = "markdown") -> dict:
    result = {
        "cell_type": kind,
        "id": uuid4().hex[:12],
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def notebook(source: str = "") -> dict:
    return {
        "cells": [cell(source)],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def source(item: dict) -> str:
    value = item["source"]
    return value if isinstance(value, str) else "".join(value)


def load(raw: bytes) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("nbformat") != 4:
        raise ValueError("Expected a version 4 Jupyter notebook.")
    if not isinstance(value.get("cells"), list):
        raise ValueError("Notebook cells must be a list.")
    for item in value["cells"]:
        if not isinstance(item, dict) or item.get("cell_type") not in {
            "markdown",
            "code",
            "raw",
        }:
            raise ValueError("Invalid notebook cell.")
        text = item.get("source")
        if not isinstance(text, str) and not (
            isinstance(text, list) and all(isinstance(line, str) for line in text)
        ):
            raise ValueError("Invalid notebook cell source.")
    return value


def dump(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode()


def replace(
    value: dict, text: str, index: int | None, append: bool, code: bool
) -> dict:
    value = deepcopy(value)
    if append:
        value["cells"].append(cell(text, "code" if code else "markdown"))
        return value
    if index is None:
        if len(value["cells"]) != 1:
            raise ValueError("Use --cell INDEX or --append for a multi-cell notebook.")
        index = 0
    if index < 0 or index >= len(value["cells"]):
        raise ValueError("Cell index is out of range (indices start at zero).")
    item = value["cells"][index]
    if source(item) == text:
        return value
    item["source"] = text.splitlines(keepends=True)
    if item["cell_type"] == "code":
        item.update(execution_count=None, outputs=[])
    return value
