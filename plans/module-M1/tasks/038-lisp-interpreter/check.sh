#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from lisp import evaluate

assert evaluate("(+ 1 2 3)") == 6
assert evaluate("(if #t 1 2)") == 1
assert evaluate("(if #f 1 2)") == 2
assert evaluate("(begin (define x 10) (define (add y) (+ x y)) (add 5))") == 15
assert (
    evaluate(
        "(begin (define (fact n) (if (= n 0) 1 (* n (fact (- n 1))))) (fact 5))"
    )
    == 120
)
assert (
    evaluate(
        "(begin (define (make-adder n) (lambda (x) (+ x n))) "
        "(define add5 (make-adder 5)) (add5 7))"
    )
    == 12
)
assert evaluate("(let ((x 2) (y 3)) (* x y))") == 6
assert evaluate("(quote (1 2 3))") == [1, 2, 3]
assert evaluate("'(1 2 3)") == [1, 2, 3]
assert evaluate("(car (list 1 2))") == 1
assert evaluate("(cdr (list 1 2 3))") == [2, 3]
assert evaluate("(cons 0 (list 1 2))") == [0, 1, 2]
assert evaluate("(null? (list))") is True
assert evaluate("(not #f)") is True
assert evaluate("(not #t)") is False
assert (
    evaluate(
        "(begin (define (sum-to n acc) "
        "(if (= n 0) acc (sum-to (- n 1) (+ acc n)))) (sum-to 100 0))"
    )
    == 5050
)

for source in ["(car (list))", "(unknown 1)", "(/ 1 0)", "(if)", "(", ")"]:
    try:
        evaluate(source)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid program: {source!r}")
print("ok")
PY
