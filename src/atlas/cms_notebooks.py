"""Notebook source operations. Rendering and editing never execute cells."""

import json
import re
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
        if not isinstance(item, dict) or item.get("cell_type") not in (
            "markdown",
            "code",
            "raw",
        ):
            raise ValueError("Invalid notebook cell.")
        text = item.get("source")
        if not isinstance(text, str) and not (
            isinstance(text, list) and all(isinstance(line, str) for line in text)
        ):
            raise ValueError("Invalid notebook cell source.")
    return value


def dump(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode()
