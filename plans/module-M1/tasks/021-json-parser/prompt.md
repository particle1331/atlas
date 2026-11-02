Implement `parse_json(text)` in `json_parser.py` without using the `json`
module.

Support JSON objects, arrays, strings, numbers, `true`, `false`, and `null`,
with arbitrary whitespace between tokens.

Strings must support the escapes `\"`, `\\`, `\/`, `\b`, `\f`, `\n`,
`\r`, `\t`, and `\uXXXX` (four hex digits). Numbers may be negative and
may use decimals or exponents.

Raise `ValueError` for invalid input, including trailing non-whitespace,
trailing commas, unterminated strings, invalid escapes, and leading zeros.
