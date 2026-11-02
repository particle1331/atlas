Implement `render(template, context)` in `template.py`.

Support `{{ name }}` variable substitution and dotted paths such as
`{{ user.name }}`. Also support the filters `upper` and `lower` with
`{{ name|upper }}` and `{{ name|lower }}`; whitespace around names and
filters is ignored.

Raise `KeyError` for a missing variable and `ValueError` for a malformed
tag. Do not use `eval`.
