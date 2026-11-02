Implement `fullmatch(pattern, text)` in `regex_engine.py` without using the
`re` module.

Support:
- literals
- `.` matching any character except newline
- `*`, `+`, and `?` quantifiers
- character classes such as `[abc]`, `[a-z]`, and `[^0-9]`
- `^` and `$` anchors
- `|` alternation
- `(...)` grouping
- escapes `\d`, `\w`, `\s`, and escaped metacharacters

Return `True` only when the whole string matches. Raise `ValueError` for
malformed patterns, including unbalanced groups or classes, dangling
quantifiers, empty alternation branches, and invalid escapes.
