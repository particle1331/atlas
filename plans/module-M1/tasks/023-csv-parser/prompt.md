Implement `parse_csv(text)` in `csv_parser.py` without using the `csv`
module.

Return a list of rows, where each row is a list of strings.

Support:
- comma-separated fields and empty fields
- quoted fields containing commas, newlines, and doubled quotes (`""`)
- LF and CRLF line endings
- an optional trailing newline

Raise `ValueError` for unterminated quotes or extra characters after a
closing quote.
