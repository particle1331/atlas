---
description: Group current changes and create local Conventional Commits
agent: general
model: openai/gpt-6-luna
subagent: true
---

Review the current Git working tree, group related changes, and create local
Conventional Commits. Invoking this command authorizes staging and creating
new commits for clear, in-scope changes without another approval step.

Additional user guidance: $ARGUMENTS

1. Read the applicable AGENTS.md instructions. Inspect `git status --short`,
   recent commit history, staged and unstaged diffs, and untracked file names.
   Read relevant untracked text files selectively; do not read secrets or dump
   large generated files, binaries, or notebook JSON. For notebook inspection,
   follow this repository's notebook tooling instructions.
2. Group changes by purpose, not merely by directory or file extension. Keep
   related implementation, tests, documentation, authored content, managed
   records, and deliberate generated assets together when appropriate.
   Identify unrelated changes and files that contain multiple concerns.
3. Choose a sensible commit order. For each group, identify exact paths and
   its purpose, and use a message in the form `type(scope): description`
   (scope optional). Use appropriate Conventional Commit types such as feat,
   fix, refactor, docs, test, chore, build, ci, perf, or style. Reserve style
   for formatting-only changes. Mark breaking changes only when supported by
   evidence and explain the required BREAKING CHANGE footer.
4. Leave secrets, suspicious generated output, and changes whose purpose is
   unclear uncommitted. Report these exclusions, including the résumé PDF when
   it has no corresponding intentional source change. Do not discard them.
5. Inspect the existing index before staging. Preserve unrelated staged work;
   do not silently include, unstage, or overwrite it. If an ambiguous or
   out-of-scope staged change prevents safe commits, stop and explain the
   blocker rather than changing the user's staging choices.
6. Before creating any commits, attempt the unmodified `make doctor` command
   from the repository root, including for prose-only changes. Run it once for
   the reviewed working tree, not once per commit group. Also run applicable
   content or rendering checks required by AGENTS.md and inspect diffs. If
   `make doctor` fails or cannot run, stop before creating commits and report
   the failing checks or missing tools.
   Do not skip the attempt or weaken checks. Only proceed after a reported
   failure or inability to run it if the user explicitly authorizes that
   exception; applicable content checks and commit hooks still apply.
   A clean working tree or a read-only review of existing commits does not
   require running it.
   Do not execute notebook cells or start project services just to commit.
   Report draft publication blockers and other known limitations accurately;
   do not repair unrelated drafts or modify authored files to make checks pass.
7. Stage only the selected paths or hunks for each group, inspect the staged
   diff, and create the commit. Keep managed records with their authored
   changes. If splitting a file cannot be done safely, keep related concerns
   together or leave it uncommitted. Never use blanket staging.
8. Respect commit hooks. If a hook fails or modifies files, inspect the result
   and report the blocker; do not bypass hooks or blindly retry. Verify each
   successful commit and finish by checking Git status and recent history.

Do not edit authored files, amend existing commits, rewrite history, reset,
discard work, or push. Do not change Git configuration or bypass signing.
Validation may produce generated output; review and leave incidental changes
uncommitted. Do not undo commits unless the user separately requests it.
If the working tree is clean, say so; do not invent groups or rewrite existing
commits. If the user asks about existing commits instead, inspect the requested
range read-only and propose grouping without rebasing or changing history.

Return a self-contained result for the parent agent to display in the main
conversation: begin with the number of commits actually created, then list
their hashes, messages and brief purposes. Include checks actually run,
failures, excluded paths and remaining working-tree changes. Say explicitly
that nothing was pushed. If blocked or only partly complete, say so; do not
describe proposed commits as completed. Keep the result concise.
