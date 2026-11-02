Implement `evaluate(expr)` in `expr.py` for arithmetic expressions.

Support non-negative number literals, `+`, `-`, `*`, `/`, `%`, parentheses,
unary `+`/`-`, and exponentiation `^`.

Precedence: `^` binds tighter than unary minus and is right-associative.
For example, `-2^2` is `-4` and `2^3^2` is `512`. Multiplication, division,
and modulo bind tighter than addition and subtraction.

Return a float. Raise `ValueError` for malformed input or division by zero.
