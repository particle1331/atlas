#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import subprocess
import sys
from pathlib import Path

subprocess.run([sys.executable, "total.py"], check=True)
text = Path("total.txt").read_text().strip()
assert text == "49.75", text
print("ok")
PY
