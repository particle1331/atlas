Implement `evaluate(source)` in `lisp.py` for a small Lisp interpreter.
Return the value of the last top-level expression.

Support:
- integers, `#t`, `#f`, and symbols
- `quote`, `if`, `define`, `lambda`, `let`, and `begin`
- variadic `+`, `-`, `*`, `/`
- two-argument `<`, `<=`, `=`, `>`, `>=`
- `list`, `car`, `cdr`, `cons`, `null?`, and `not`
- lexical scoping, closures, recursion, and `'` as quote shorthand
- `;` line comments

`define` may bind a value or use the function shorthand
`(define (name args...) body...)`. Raise `ValueError` for malformed input,
unbound symbols, wrong arity, or division by zero.
