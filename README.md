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

Before each commit, the hook runs `uv run at vault check` and scans staged files
for likely secrets. To run both checks manually across tracked files, use
`pre-commit run --all-files`.

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
uv run at vault rm API_TOKEN --yes

# Check the names declared in the current directory's .env.example.
uv run at vault check
uv run at vault check --manifest /path/to/.env.example
```

Declare expected names in `.env.example`, for example:

```dotenv
API_TOKEN=
DATABASE_URL=
```

`check` reports `ok` or `missing` for each name and prints no secret values. Comments,
`export` declarations, quoted values, and multiline values follow dotenv syntax;
duplicate names are checked once. Values in the example file are ignored.

`get` copies a secret to the clipboard when stdout is a terminal. When stdout is
redirected or piped, it writes the stored value to stdout without adding a newline.

Vault commands leave `.env.example` unchanged. Deleting a value makes its name
appear as missing on the next check. Remove a name from `.env.example` when the
project stops requiring it.

Exit codes are `0` for success, `1` for a missing secret, and `2` for a configuration,
input, or keyring error. An empty manifest succeeds and reports no declared secrets.
Python keyring chooses the credential backend; unavailable or disabled backends
produce an error. Run `uv run keyring diagnose` to inspect backend configuration.
