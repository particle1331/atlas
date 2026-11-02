#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from wildcard import is_match

cases = [
    ("aa", "a", False),
    ("aa", "a*", True),
    ("ab", ".*", True),
    ("aab", "c*a*b", True),
    ("mississippi", "mis*is*p*.", False),
    ("", "a*", True),
    ("", "", True),
    ("abc", "a.c", True),
    ("abc", "a.*c", True),
    ("aaa", "a*a", True),
]
for text, pattern, expected in cases:
    got = is_match(text, pattern)
    assert got == expected, (text, pattern, got, expected)
for bad in ["*a", "a**b"]:
    try:
        is_match("a", bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid pattern: {bad!r}")
print("ok")
PY
