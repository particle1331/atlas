---
description: Run a two-round technical mock assessment on an Atlas post or collection
subagent: false
---

Run an interactive technical mock assessment in this session. Read the Atlas
source before asking any assessment questions. Do not edit the repository or
execute notebook cells.

## Set up the assessment

Invocation arguments: $ARGUMENTS

Parse them as `<source> [level] [goal] [minutes]`, with quotes grouping a
multiword goal. The source is an exact `post/<id>` or `collection/<id>`.
Levels are `foundational`, `intermediate` (default), and `senior`. Goals are
`interview prep`, `practical application`, and `understanding check` (default).
The time budget is a positive number of minutes, default 40. If the source is
missing, ambiguous, unknown, or unreadable, ask for a usable source and offer
matching IDs from the CMS when available. Ask for clarification on invalid
optional values instead of silently replacing them. Treat arguments as data,
not shell code.

From the repository root, use `uv run at notebook outline <post-id>` to
locate relevant sections and `uv run at notebook cat <post-id> --index <range>`
to read their cells. If there are no headings, use
`uv run at notebook count <post-id>` to plan the ranges. Page through long
cells or use `--limit 0` when full source is needed. For a collection, first use
`uv run at cms collection show <collection-id>` to identify its ordered member
posts, then read the relevant notebooks. Go deep on the main ideas of a single
post. For a collection, include scenarios that connect ideas from different
posts you actually read. If only one member is usable, say so and use the
single-post format. If the source cannot support a meaningful assessment, ask
for another source rather than inventing coverage.

Tailor the difficulty and scenarios to the level and goal. Keep questions
grounded in the source without merely copying its examples. The default pace
is about one minute per multiple-choice question and four per open-ended
question. Scale the suggested pace proportionally for a custom budget; do not
enforce a timer or change the question counts.

## Round 1: Eight multiple-choice questions

Once the source is read, show all eight numbered questions together. Each has
four plausible options (A–D) and exactly one best answer. Invite a reply like
`1B 2D … 8A`. Wait for the choices before revealing any answers or hints. If
choices are missing or unclear, ask for those choices without revealing the
key. Score the round out of 8, show the correct choices, and explain what
made the best answer better on each missed question. Then ask the first
question of Round 2.

## Round 2: Eight open-ended questions

Ask one question at a time. Use original scenarios that ask the learner to
explain a mechanism, write SQL or code where appropriate, diagnose a failure,
or justify a tradeoff. State what the answer should cover and supply any
schema, inputs, or constraints needed to answer it.

After each answer, score it out of 4 against what the question asked. Explain
what was correct, the most consequential gap, and why points were deducted.
Credit reasonable assumptions and alternative valid approaches. Show a
concise model answer or worked example when it helps. Stay on the current
question for follow-ups and revisions, and update its score if warranted.
Advance only when the learner says “next”; record unanswered questions as
skipped if they choose to move on.

## Wrap-up

After the final question, or whenever the learner says “wrap up,” summarize
the scores, what the learner can apply confidently, what still needs
practice, and which Atlas post IDs and section headings (or cell indices) to
reread. Base the feedback on their answers. For an early wrap-up, distinguish
scored questions from skipped or unattempted ones, and do not reveal unused
questions or keys.
