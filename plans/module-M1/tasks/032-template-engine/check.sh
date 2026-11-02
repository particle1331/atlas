#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from template import render

assert render("Hello, {{ name }}!", {"name": "Ada"}) == "Hello, Ada!"
assert render("{{ user.name }}", {"user": {"name": "Ada"}}) == "Ada"
assert render("{{ name|upper }}", {"name": "Ada"}) == "ADA"
assert render("{{ name | lower }}", {"name": "Ada"}) == "ada"
assert render("{{ user.name|upper }}", {"user": {"name": "ada"}}) == "ADA"
for context, template, error in [
    ({}, "{{ name }}", KeyError),
    ({"name": "Ada"}, "{{ name|title }}", ValueError),
    ({"name": "Ada"}, "{{ }}", ValueError),
    ({"name": "Ada"}, "{{ name", ValueError),
]:
    try:
        render(template, context)
    except error:
        pass
    else:
        raise AssertionError(f"accepted invalid template: {template!r}")
print("ok")
PY
