#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import hashlib
import subprocess
import sys
from pathlib import Path

expected = "7d93a57febf406d9a69bc08e8dd8fd5c3196e176659484c81959874d3b55d85c"
actual = hashlib.sha256(Path("test_math.py").read_bytes()).hexdigest()
assert actual == expected, "test_math.py was modified"
result = subprocess.run(
    [sys.executable, "-m", "unittest", "-q"], capture_output=True, text=True
)
if result.returncode != 0:
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)
print("ok")
PY
