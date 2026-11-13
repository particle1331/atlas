# OpenCode project commands

Project commands live in `commands/` and reload automatically in OpenCode.

## Commit planning

Run `/commit-plan` to inspect current uncommitted changes and recent history,
group related changes, and propose Conventional Commit messages. Add optional
guidance, for example:

```text
/commit-plan keep the content updates separate from tooling changes
```

The command runs in a separate session using `openai/gpt-6-luna`, leaving the
main session's model unchanged. It only proposes a plan: it does not edit files,
stage changes, create commits, or rewrite history.

To review existing commits instead, specify a range in your guidance:

```text
/commit-plan review existing commits in main..HEAD instead of the working tree
```

The model override is configured in `commands/commit-plan.md` frontmatter.
