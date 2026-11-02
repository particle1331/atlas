#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from range_sum import range_sum

assert range_sum(0) == 0
assert range_sum(-3) == 0
assert range_sum(1) == 1
assert range_sum(5) == 15
assert range_sum(10) == 55
print("ok")
PY
