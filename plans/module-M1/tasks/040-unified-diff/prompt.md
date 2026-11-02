Implement `unified_diff(a, b, context=3)` in `diff.py` without using
`difflib`.

`a` and `b` are lists of lines without trailing newlines. Return a unified
diff string with `--- a`, `+++ b`, and one or more hunk headers of the form
`@@ -old_start,old_count +new_start,new_count @@`. Always include the
counts, even when they are `1`.

Use `context` unchanged lines around each change. Merge hunks when their
context would touch. Return an empty string when the inputs are equal.
