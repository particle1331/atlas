#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from expr import evaluate

cases = {
    "2+3*4": 14,
    "(2+3)*4": 20,
    "2^3^2": 512,
    "-2^2": -4,
    "(-2)^2": 4,
    "10/4": 2.5,
    "10%3": 1,
    "2*-3": -6,
    " 1 + 2 ": 3,
    "2^3*2": 16,
}
for expr, expected in cases.items():
    got = evaluate(expr)
    assert abs(got - expected) < 1e-9, (expr, got, expected)
for bad in ["", "2+", "(1+2", "1/0", "2^^3", "abc", "1 2", "2**3"]:
    try:
        evaluate(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid expression: {bad!r}")
print("ok")
PY
