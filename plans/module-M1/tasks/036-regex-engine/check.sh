#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from regex_engine import fullmatch

cases = [
    ("abc", "abc", True),
    ("abc", "ab", False),
    ("a.c", "abc", True),
    ("a.c", "a\nc", False),
    ("a*", "aaa", True),
    ("a*", "", True),
    ("a+", "", False),
    ("ab?c", "ac", True),
    ("ab?c", "abbc", False),
    ("[a-c]+", "abc", True),
    ("[^a-c]+", "xyz", True),
    ("[^a-c]+", "xay", False),
    ("^(foo|bar)+$", "foobar", True),
    ("^(foo|bar)+$", "foobaz", False),
    ("(ab)*", "ababab", True),
    ("(ab)*", "aba", False),
    ("a|b|c", "b", True),
    ("^$", "", True),
    ("a$", "a", True),
    ("a$", "ab", False),
    ("\\d+", "123", True),
    ("\\d+", "12a", False),
    ("\\w+", "a_1", True),
    ("\\s+", " \t\n", True),
    ("\\.", ".", True),
    ("\\.", "a", False),
    ("[a-]+", "a-a", True),
    ("[-a]+", "-a", True),
]
for pattern, text, expected in cases:
    got = fullmatch(pattern, text)
    assert got == expected, (pattern, text, got, expected)
for pattern in ["(", ")", "[", "a**", "*a", "a|", "|a", "\\", "[z-a]", "[]"]:
    try:
        fullmatch(pattern, "a")
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid pattern: {pattern!r}")
print("ok")
PY
