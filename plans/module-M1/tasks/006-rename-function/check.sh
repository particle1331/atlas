#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import subprocess
import sys

out = subprocess.check_output([sys.executable, "main.py"], text=True).strip()
assert out == "5", out

import calc

assert hasattr(calc, "add_numbers")
assert not hasattr(calc, "add"), "old function name still exists"
print("ok")
PY
