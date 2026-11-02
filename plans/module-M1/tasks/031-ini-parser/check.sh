#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from ini_parser import parse_ini

text = '''
# global
name = atlas
[server]
host = localhost
port = 8080  ; trailing comment
[paths]
root = "/tmp/a\\nb"
quote = "say \\"hi\\""
'''
parsed = parse_ini(text)
assert parsed["DEFAULT"] == {"name": "atlas"}
assert parsed["server"] == {"host": "localhost", "port": "8080"}
assert parsed["paths"] == {"root": "/tmp/a\nb", "quote": 'say "hi"'}
assert parse_ini("[a]\nx=1\nx=2\n")["a"]["x"] == "2"
for bad in ["[a\nx=1", "[a]\nbad line", '[a]\nx="unterminated']:
    try:
        parse_ini(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid INI: {bad!r}")
print("ok")
PY
