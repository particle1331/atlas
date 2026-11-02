#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from diff import unified_diff

assert unified_diff(["a", "b", "c"], ["a", "b", "c"]) == ""

assert unified_diff(["a", "b", "c"], ["a", "B", "c"]) == "\n".join(
    [
        "--- a",
        "+++ b",
        "@@ -1,3 +1,3 @@",
        " a",
        "-b",
        "+B",
        " c",
    ]
)

assert unified_diff(["b", "c"], ["a", "b", "c"]) == "\n".join(
    [
        "--- a",
        "+++ b",
        "@@ -1,2 +1,3 @@",
        "+a",
        " b",
        " c",
    ]
)

assert unified_diff(["a", "b", "c", "d"], ["a", "b", "d"], context=1) == "\n".join(
    [
        "--- a",
        "+++ b",
        "@@ -2,3 +2,2 @@",
        " b",
        "-c",
        " d",
    ]
)

a = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
b = ["a", "B", "c", "d", "e", "f", "g", "H", "i", "j"]
assert unified_diff(a, b, context=1) == "\n".join(
    [
        "--- a",
        "+++ b",
        "@@ -1,3 +1,3 @@",
        " a",
        "-b",
        "+B",
        " c",
        "@@ -7,3 +7,3 @@",
        " g",
        "-h",
        "+H",
        " i",
    ]
)

assert unified_diff([], ["a", "b"]) == "\n".join(
    ["--- a", "+++ b", "@@ -0,0 +1,2 @@", "+a", "+b"]
)
assert unified_diff(["a"], []) == "\n".join(
    ["--- a", "+++ b", "@@ -1,1 +0,0 @@", "-a"]
)
assert unified_diff(["a", "b", "c"], ["a", "B", "c"], context=0) == "\n".join(
    ["--- a", "+++ b", "@@ -2,1 +2,1 @@", "-b", "+B"]
)
try:
    unified_diff(["a"], ["b"], context=-1)
except ValueError:
    pass
else:
    raise AssertionError("accepted negative context")
print("ok")
PY
