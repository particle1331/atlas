Implement `apply_patch(original, patch)` in `patch.py`.

`original` is a string of lines joined by `\n` (no trailing newline).
`patch` is a unified diff with exactly one hunk:

```text
--- a
+++ b
@@ -start,count +start,count @@
 context
-removed
+added
```

Return the patched text, joined by `\n` with no trailing newline. Raise
`ValueError` if the hunk context does not match, the hunk is malformed, or
the patch contains more than one hunk.
