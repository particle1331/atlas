# OpenCode project configuration

Project commands live in `commands/` and reload automatically in OpenCode.

## Agents

The seven custom agents live in `agents/*.md` in this repository, not in
`~/.config/opencode/agents/`. Keep these definitions in Git and edit them here.
Each file contains the agent's model, explicit reasoning variant, permissions
and instructions. Every custom agent must specify its reasoning level as
`openai/<model>#<variant>`; do not rely on provider defaults.

| Agents | Model and reasoning |
| --- | --- |
| Orchestrator, fixer, designer, observer | `openai/gpt-6.1-sol#high` |
| Oracle | `openai/gpt-6.1-sol#max` |
| Librarian | `openai/gpt-6-luna#medium` |
| Explore | `openai/gpt-6-luna-fast#low` |

From the repository root, inspect the configuration OpenCode actually loads:

```sh
opencode debug config
opencode debug agents
```

`debug config` lists the configuration source paths; it should include this
checkout's `.opencode` directory. `debug agents` shows the resolved models,
reasoning variants, instructions and permissions. It does not show each agent's
source filename. With no matching global agent files, the definitions here are
the source for these custom agents.

OpenCode still reads unrelated global settings, such as MCP connections and
provider configuration. This is not a global-config isolation mechanism.
Agent definitions merge across configuration sources, so avoid duplicate custom
agents in global configuration when using this repository-owned setup. These
agents are project-local and will not be available in other projects unless
those projects define them too.

Edits reload automatically; run `/reload` in OpenCode to force a refresh.
An existing session keeps its separately selected model, so changing an agent's
model preference does not change the current session's model.

## Local commits

Run `/commit` to inspect current uncommitted changes and recent history,
group related changes, and create local Conventional Commits without another
approval step. Add optional guidance, for example:

```text
/commit keep the content updates separate from tooling changes
```

The command runs in a fresh child session using `openai/gpt-6-luna`,
leaving the main session's agent and model unchanged. OpenCode returns the
child's result to the main agent. The [commit command handoff rule](../AGENTS.md#commit-command-handoff)
instructs the main agent to display the hashes and summary without repeating the review,
so you do not need to open the child session. Displaying the result uses a
main-model response; the repository review and commits run on Luna.

The child stages selected changes and creates new commits, but never pushes,
amends existing commits, rewrites history or discards work. Ambiguous files
(such as an unexplained résumé PDF update) remain uncommitted. Existing staged
work is preserved; if it prevents safe grouping, the command reports a blocker.
Checks and commit hooks may produce generated changes, which are reviewed
rather than automatically included. Undoing commits requires a separate request.

To review existing commits instead, specify a range in your guidance:

```text
/commit review existing commits in main..HEAD instead of the working tree; do not create commits
```

The model and `subagent: true` setting are configured in
`commands/commit.md` frontmatter. This replaces `/commit-plan`; command changes
reload automatically.
