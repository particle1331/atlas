#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from datetime import datetime
from cron import next_runs

start = datetime(2024, 1, 1, 0, 0)
assert next_runs("*/15 * * * *", start, 4) == [
    datetime(2024, 1, 1, 0, 15),
    datetime(2024, 1, 1, 0, 30),
    datetime(2024, 1, 1, 0, 45),
    datetime(2024, 1, 1, 1, 0),
]
assert next_runs("0 9 * * MON-FRI", start, 3) == [
    datetime(2024, 1, 1, 9, 0),
    datetime(2024, 1, 2, 9, 0),
    datetime(2024, 1, 3, 9, 0),
]
assert next_runs("30 8 1 * *", start, 2) == [
    datetime(2024, 1, 1, 8, 30),
    datetime(2024, 2, 1, 8, 30),
]
assert next_runs("0 0 1 JAN,JUL *", start, 2) == [
    datetime(2024, 7, 1, 0, 0),
    datetime(2025, 1, 1, 0, 0),
]
assert next_runs("0 12 * * SUN", start, 2) == [
    datetime(2024, 1, 7, 12, 0),
    datetime(2024, 1, 14, 12, 0),
]
assert next_runs("0 0 13 * FRI", datetime(2024, 9, 1), 3) == [
    datetime(2024, 9, 6),
    datetime(2024, 9, 13),
    datetime(2024, 9, 20),
]
assert next_runs("0 0 13 * SAT", datetime(2024, 9, 1), 8) == [
    datetime(2024, 9, 7),
    datetime(2024, 9, 13),
    datetime(2024, 9, 14),
    datetime(2024, 9, 21),
    datetime(2024, 9, 28),
    datetime(2024, 10, 5),
    datetime(2024, 10, 12),
    datetime(2024, 10, 13),
]
assert next_runs("0 0 * * 7", start, 1) == [datetime(2024, 1, 7)]
assert next_runs("0 0 * * 0", start, 1) == [datetime(2024, 1, 7)]

for expression, count in [
    ("* * * *", 1),
    ("60 * * * *", 1),
    ("*/0 * * * *", 1),
    ("0 0 32 * *", 1),
    ("0 0 * FOO *", 1),
    ("0 0 * * MON-XXX", 1),
    ("* * * * *", 0),
]:
    try:
        next_runs(expression, start, count)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid cron: {expression!r}, {count}")
print("ok")
PY
