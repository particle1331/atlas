#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from semver import sort_versions

versions = [
    "1.0.0-beta.11",
    "1.0.0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-rc.1",
    "2.0.0",
    "1.0.0-alpha.beta.1",
]
expected = [
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-alpha.beta.1",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
    "2.0.0",
]
assert sort_versions(versions) == expected, sort_versions(versions)
assert sort_versions(["1.0.0+build.1", "1.0.0"]) == ["1.0.0+build.1", "1.0.0"]
for bad in ["1.0", "1.0.0.0", "01.0.0", "1.0.0-", "1.0.0+meta+meta"]:
    try:
        sort_versions([bad])
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid version: {bad!r}")
print("ok")
PY
