#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from json_parser import parse_json

assert parse_json('{"a": 1, "b": [true, null, false]}') == {
    "a": 1,
    "b": [True, None, False],
}
assert parse_json('"line\\nquote\\"slash\\\\unicode\\u00e9"') == 'line\nquote"slash\\unicodeé'
assert parse_json(" -12.5e2 ") == -1250.0
assert parse_json("[]") == []
assert parse_json("{}") == {}
assert parse_json('{"nested": {"x": [1, 2, {"y": null}]}}') == {
    "nested": {"x": [1, 2, {"y": None}]}
}
for bad in ["", "{", '{"a":1,}', "[1,]", '"unterminated', "tru", "01", "1 2", '{"a" 1}', '{"a": 01}']:
    try:
        parse_json(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid JSON: {bad!r}")
print("ok")
PY
