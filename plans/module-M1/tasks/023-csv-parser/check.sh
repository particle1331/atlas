#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from csv_parser import parse_csv

assert parse_csv("a,b\n1,2\n") == [["a", "b"], ["1", "2"]]
assert parse_csv('"a,b",c\n"line1\nline2","quote ""x"""\n') == [
    ["a,b", "c"],
    ["line1\nline2", 'quote "x"'],
]
assert parse_csv("a,,b\n,,\n") == [["a", "", "b"], ["", "", ""]]
assert parse_csv("a,b\r\n1,2\r\n") == [["a", "b"], ["1", "2"]]
assert parse_csv("") == []
assert parse_csv('""') == [[""]]
for bad in ['"a', 'a,"b"c', '"a"b', 'a"b"']:
    try:
        parse_csv(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid CSV: {bad!r}")
print("ok")
PY
