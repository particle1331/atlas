#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from vm import run

assert run([("PUSH", 2), ("PUSH", 3), ("ADD",), ("PRINT",)]) == [5]
assert run([("PUSH", 10), ("PUSH", 3), ("SUB",), ("PRINT",)]) == [7]
assert run([("PUSH", 2), ("DUP",), ("MUL",), ("PRINT",)]) == [4]
assert run([("PUSH", 1), ("PUSH", 2), ("SWAP",), ("PRINT",), ("PRINT",)]) == [1, 2]
countdown = [
    ("PUSH", 3),
    ("DUP",),
    ("PRINT",),
    ("PUSH", 1),
    ("SUB",),
    ("DUP",),
    ("JZ", 8),
    ("JMP", 1),
    ("PRINT",),
]
assert run(countdown) == [3, 2, 1, 0]
for bad in [
    [("ADD",)],
    [("NOPE",)],
    [("PUSH", 1), ("JMP", 99)],
]:
    try:
        run(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid program: {bad}")
print("ok")
PY
