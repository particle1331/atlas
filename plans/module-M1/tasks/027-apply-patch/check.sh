#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from patch import apply_patch

original = "a\nb\nc\nd"
patch = "--- a\n+++ b\n@@ -2,3 +2,4 @@\n b\n-c\n+C\n+CC\n d"
assert apply_patch(original, patch) == "a\nb\nC\nCC\nd"
patch2 = "--- a\n+++ b\n@@ -1,2 +1,3 @@\n a\n+b1\n b"
assert apply_patch("a\nb", patch2) == "a\nb1\nb"
for bad in [
    "--- a\n+++ b\n@@ -2,2 +2,2 @@\n x\n-c",
    "--- a\n+++ b\n@@ -1,1 +1,1 @@\n-a\n+b\n@@ -2,1 +2,1 @@\n-c\n+d",
    "not a patch",
]:
    try:
        apply_patch(original, bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid patch: {bad!r}")
print("ok")
PY
