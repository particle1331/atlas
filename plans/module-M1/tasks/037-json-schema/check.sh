#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from schema import validate

schema = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string", "minLength": 3},
        "age": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}
assert validate({"name": "Al", "age": -1, "extra": 1}, schema) == [
    "$.age: minimum",
    "$.name: minLength",
    "$: additionalProperties",
]
assert validate({"name": "Ada"}, schema) == ["$: required"]

array_schema = {"type": "array", "items": {"type": "integer", "minimum": 1}}
assert validate([1, 0, "x"], array_schema) == [
    "$[1]: minimum",
    "$[2]: type",
]

string_schema = {"type": "string", "enum": ["a", "b"], "pattern": "^[a-z]+$"}
assert validate("C", string_schema) == ["$: enum", "$: pattern"]

assert validate(True, {"anyOf": [{"type": "string"}, {"type": "integer"}]}) == [
    "$: anyOf"
]
assert validate(
    1, {"oneOf": [{"type": "number"}, {"type": "integer"}]}
) == ["$: oneOf"]
assert validate(1.5, {"oneOf": [{"type": "number"}, {"type": "integer"}]}) == []

assert validate(-1, {"allOf": [{"type": "integer"}, {"minimum": 0}]}) == [
    "$: minimum"
]

nested = {
    "type": "object",
    "properties": {"a": {"type": "integer"}},
    "additionalProperties": {"type": "string"},
}
assert validate({"a": 1, "b": 2}, nested) == ["$.b: type"]

try:
    validate(1, {"type": "wat"})
except ValueError:
    pass
else:
    raise AssertionError("accepted unknown type")
print("ok")
PY
