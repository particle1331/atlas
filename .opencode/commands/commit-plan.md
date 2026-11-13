---
description: Group current changes and propose Conventional Commits
agent: general
model: openai/gpt-6-luna
subagent: true
---

Review the current Git working tree and propose logical groups of changes
with Conventional Commit messages. This is a read-only planning task.

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
3. Propose a sensible commit order. For each group, list exact paths, summarize
   its purpose, and give a message in the form `type(scope): description`
   (scope optional). Use appropriate Conventional Commit types such as feat,
   fix, refactor, docs, test, chore, build, ci, perf, or style. Reserve style
   for formatting-only changes. Mark breaking changes only when supported by
   evidence and explain the required BREAKING CHANGE footer.
4. Flag secrets, suspicious generated output, missing validation, and changes
   whose purpose is unclear. State which checks were actually run; do not
   claim that suggested checks passed.

Do not edit files, stage changes, create commits, run builds or tests that may
write files, amend commits, rewrite history, or push. Do not discard any work.
If the working tree is clean, say so; do not invent groups or rewrite existing
commits. If the user asks about existing commits instead, inspect the requested
range read-only and propose grouping without rebasing or changing history.

Keep the result concise and actionable. End with any questions needed before
the user can approve the proposed groups.
