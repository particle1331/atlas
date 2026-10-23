# Atlas

Atlas provides the `at` CLI. Its vault stores local secrets in the system keyring
using the service name `atlas.vault`. Secret names and values are shared across
projects for the current operating system user.

```sh
uv sync
uv run at --help
```

## Git hooks

Install the pre-commit tool and enable the repository hook once per clone:

```sh
uv tool install pre-commit
pre-commit install
```

Before each commit, the hook scans staged files for likely secrets with
`detect-secrets`. To scan all tracked files manually, use
`pre-commit run --all-files`. Run `uv run at vault check` to check vault entries.

## Vault

```sh
# Create or replace a secret; prompts for a hidden value and confirmation.
uv run at vault set API_TOKEN

# Read a value from stdin; removes one trailing line ending.
uv run at vault set API_TOKEN --stdin < /path/to/token

# Copy the value when running interactively; write it to stdout when piped.
uv run at vault get API_TOKEN

# Delete the local value; prompts for confirmation.
uv run at vault rm API_TOKEN

# Delete without prompting, including in scripts.
uv run at vault rm API_TOKEN --yes  # or -y

# Check the names declared in the Atlas repository root's .env.example.
uv run at vault check
```

Declare expected names in the Atlas repository root's `.env.example`, for example:

```dotenv
# Required secrets
API_TOKEN=
DATABASE_URL=
```

Use one `NAME=` entry per line with an empty value. Blank lines and full-line `#`
comments (including indented comments) are skipped. `export` declarations, inline
comments, quoted values, and multiline values are not supported. Duplicate names
are checked separately. The path is fixed by Atlas's project root; it does not
depend on the current directory and has no override option.

`check` reports `[ok]` for each stored name and `[no]` for each missing name,
followed by a missing-count summary if needed. It does not print stored values.
The manifest must exist; a missing file raises `FileNotFoundError` and exits with
code `1`. A manifest containing only blank lines or comments, or an empty manifest,
succeeds and reports `No secrets declared.`

`set` requires a terminal for hidden input unless `--stdin` is used. Empty secret
values are rejected. `rm` requires a terminal for confirmation unless `--yes`
or `-y` is used.

`get` copies a secret to the clipboard when stdout is a terminal. When stdout is
redirected or piped, it writes the stored value to stdout without adding a newline.

Vault commands leave `.env.example` unchanged. Deleting a value makes its name
appear as missing on the next check. Remove a name from `.env.example` when the
project stops requiring it.

Exit codes are `0` for success (including cancelled deletion), `1` for missing
secrets or a missing manifest, and `2` for invalid manifest entries, input errors,
or keyring/clipboard errors.
Python keyring chooses the credential backend; unavailable or disabled backends
produce an error. Run `uv run keyring diagnose` to inspect backend configuration.
