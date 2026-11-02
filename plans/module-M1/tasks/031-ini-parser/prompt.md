Implement `parse_ini(text)` in `ini_parser.py`.

Return a dict mapping section names to dicts of key/value strings.

Support:
- section headers `[name]`
- `key = value` pairs
- comments starting with `#` or `;` (whole-line or trailing)
- quoted values with `\n`, `\t`, `\"`, and `\\` escapes
- keys before any section go into a `"DEFAULT"` section
- duplicate keys: last value wins

Raise `ValueError` for malformed lines or duplicate section names.
