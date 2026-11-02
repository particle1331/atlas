#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import shutil
import subprocess
from pathlib import Path

shutil.rmtree("backup", ignore_errors=True)
result = subprocess.run(["bash", "backup.sh"], capture_output=True, text=True)
assert result.returncode == 0, result.stderr
assert Path("backup/a.txt").read_text() == "alpha\n"
assert Path("backup/b.txt").read_text() == "beta\n"
print("ok")
PY
