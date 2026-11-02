#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import hashlib
import subprocess
import sys
from pathlib import Path

expected = "422cac8f37d4c655dd8db18df10211b2fde4b36fb359caf89e42083cc80d1ee3"
actual = hashlib.sha256(Path("test_ledger.py").read_bytes()).hexdigest()
assert actual == expected, "test_ledger.py was modified"

from ledger import compute_balances

transactions = [
    {"id": "z1", "date": "2024-01-01", "account": "A", "type": "charge", "amount": "5.00"},
    {"id": "a2", "date": "2024-01-02", "account": "A", "type": "refund", "amount": "10.00"},
    {"id": "m3", "date": "2024-01-03", "account": "A", "type": "charge", "amount": "10.00"},
    {"id": "b1", "date": "2024-01-04", "account": "B", "type": "charge", "amount": "0.10"},
    {"id": "b2", "date": "2024-01-05", "account": "B", "type": "charge", "amount": "0.20"},
]
assert compute_balances(transactions) == {"A": "10.00", "B": "0.30"}, compute_balances(transactions)

result = subprocess.run([sys.executable, "-m", "unittest", "-q"], capture_output=True, text=True)
if result.returncode != 0:
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)
print("ok")
PY
