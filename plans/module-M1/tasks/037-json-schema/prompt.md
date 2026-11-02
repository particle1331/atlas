Implement `validate(instance, schema)` in `schema.py`.

Return a sorted list of error strings. Each error has the form
`"<path>: <keyword>"`. Use `$` for the root, `$.key` for object properties,
and `$[0]` for array indices.

Support these keywords:
- `type`: one type name or a list of names (`object`, `array`, `string`,
  `number`, `integer`, `boolean`, `null`)
- `properties`, `required`, and `additionalProperties` (boolean or schema)
- `items` (one schema for every array element)
- `enum`
- `minimum` and `maximum`
- `minLength`, `maxLength`, and `pattern` (use `re.search`)
- `allOf`, `anyOf`, and `oneOf`

`allOf` contributes the errors from each failing subschema. `anyOf` adds
`<path>: anyOf` when no subschema matches. `oneOf` adds `<path>: oneOf`
unless exactly one subschema matches. Stop descending after a type error.
Raise `ValueError` for an unknown type name.
