Implement `sort_versions(versions)` in `semver.py`.

Parse Semantic Versioning 2.0.0 strings: `MAJOR.MINOR.PATCH`, an optional
`-prerelease`, and an optional `+build`.

Sort ascending by SemVer precedence:
- numeric prerelease identifiers compare numerically
- alphanumeric identifiers compare lexically
- numeric identifiers have lower precedence than alphanumeric ones
- a version without a prerelease has higher precedence than one with one
- build metadata is ignored for precedence

When two versions have equal precedence, preserve their input order.
Raise `ValueError` for invalid versions.
