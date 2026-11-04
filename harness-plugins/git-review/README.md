# Git Review for DeepSeek Harness

A persistent, dependency-free Host/Client bundle. Open **Git Review** from the left sidebar, or choose it in a repository conversation's view selector alongside Chat and Trajectory. The sidebar page targets the Session the main view currently holds (falling back to the first catalogued Session), so switching conversations changes which repository it reviews; it has no Session binding of its own. It uses the session's current repository and selected model; there is no replacement web server or external application.

## Review a commit series

The page follows a two-pane Changes/History layout: filterable changed files with include checkboxes on the left, the selected diff on the right, and Summary/Description plus the commit control under the file list.

0. Grouping has explicit **Model** and **Reasoning** selectors above the Group commits button. Defaults are the newest available `deepseek-flash`, then the newest Luna version (for example `gpt-6.1-luna`, compared numerically), then the session model, with **low** reasoning where the model offers it. The choice persists in this browser. Models matching “astra” are hidden and rejected by the Host, so a bulk file-reading grouping can never silently select an expensive scanning model.
1. Click **Group commits**. AI picks the groups, writes each message, and the same action creates the local commits immediately — there is no proposal screen or review checklist. The changes decide how many commits there are, capped at ten. Unassigned changes stay in **Changes**.
2. **History** shows the new commits and their changed files. Commits that are not yet on the upstream carry an **↑** badge; the header **Push origin** button shows the pending count. The push confirmation binds the displayed HEAD and exact upstream destination. Nothing force-pushes, fetches, resets, cleans, stashes, deletes branches or discards files.

Right-click the “N changed files” header for **Stash changes…** (includes untracked files) and **Discard all changes…**. Right-click a changed file in **Changes** for **Copy relative path**, **Copy absolute path**, and **Discard changes…** (confirmed; tracked files restore from HEAD, untracked files are deleted, staged files are refused). Right-click the latest History commit for **Amend message…**, **Undo commit**, and **Copy hash**. Undo is a mixed reset of exactly one local commit: its changes return to Changes unstaged, and the index/worktree are not discarded. Amend changes only the message (tree and parents untouched). Both refuse a commit already contained in the configured upstream, so published history is never rewritten.

The Changes tab can also commit a plain selection directly: choose files, write a summary, and use **Commit N files to branch**. This is the GitHub-Desktop-style quick path and creates one commit from exactly the checked files; nothing is pushed. Group commits remains the review-first path for turning many changes into several coherent commits. **History** shows recent local commits, the selected commit's changed files, and its patch; choosing a file narrows the diff to that file. **Branches** lists existing local branches; switching requires a completely clean index and working tree. This first version is not a complete GitHub Desktop replacement: branch creation, remote setup, conflict resolution, manual staging and hunk splitting remain external Git/editor operations.

### Whole-file granularity

Groups contain whole changed files, not individual hunks. A file with several unrelated changes must be split manually before organizing, or reviewed as a mixed-purpose file. Implementation, tests, documentation, authored content, supporting assets and related backend records should stay together by subject. The model is instructed to flag uncertainty and mixed files. It does not prove that every intermediate commit builds: review the order and run relevant tests.

### Sessions and privacy

The optional **Use recent repository sessions** switch is on by default. Grouping follows the meaning of the changes; the only count limit is the hard cap of ten commits, and the model is told not to split cohesive work or pad groups to reach a count. Organizing sends bounded diffs and bounded user/final-assistant excerpts to the selected model provider. No tools, reasoning, system prompts or attachments are included in session excerpts. Only sessions originating in the same canonical Git repository are considered. Activity timestamps rank resumed sessions, and changed-directory segments from other repositories and inherited fork content are excluded. At most twelve full session logs are read.

If the model's JSON hits its output-token limit, one compact retry is made with reduced reasoning effort; output truncated a second time is rejected, never partially accepted.

All eligible changed paths must appear exactly once in the model's strict JSON response. Duplicate, invented, missing or excluded paths, invalid source citations, partial generation and malformed JSON reject the proposal rather than silently repairing or committing it. A large file inventory that cannot fit the bounded prompt fails explicitly; filenames are never silently dropped.

Notebook planning summarizes recognizable changed source fragments rather than saved outputs or attachments. Missing source context, binary content, diff truncation and omitted session excerpts are disclosed. Heuristic secret-name detection excludes environment/credential/key files from automatic planning and commits; high-confidence credential patterns are redacted from model inputs. This is not universal secret detection: review source before publication. Explicit local UI diff viewing is separate from automated model input; model-facing `git_review` diffs require an explicit non-sensitive path.

### Git safety and compatibility

- A proposal stores HEAD plus a content hash of every grouped file. Commits re-check only those files and the exact HEAD: edits to unrelated files in this or other sessions do not invalidate the grouping. A grouped file that changed (or disappeared) blocks the series and names the affected files. A banner offers **Group again** for either case.
- A content fingerprint of the whole worktree still guards planning itself and the quick Commit-selection path. No mtime-only checks.
- Existing staging is never silently changed. Group creation refuses **any** pre-existing staged changes. Unstage them yourself, then organize again.
- A locked alternate index builds the reviewed whole-file series. Prepared contents are checked against the worktree, then one compare-and-swap advances the branch from the reviewed HEAD. Working files are not rewritten. Unrelated unstaged files remain untouched.
- Detached HEAD, conflicts, dirty submodules, merge/rebase/cherry-pick/revert/bisect states, sparse/split indexes and commit signing are not supported for creating groups. Signing is refused rather than silently skipped. Executable Git hooks (including a configured `core.hooksPath`) are bypassed exactly like GitHub Desktop, and the result reports that they were not run; they are never executed. External Git clean/smudge/process filters are refused even for status/diff, because Git can execute them while reading.
- Credential helpers and interactive prompts are disabled during pushing. Standard HTTPS, local/file and standard SSH remotes are supported; custom Git transports/commands are refused. SSH uses noninteractive OpenSSH with strict host checking, no user SSH configuration, no host/keychain modifications and no proxy commands. Use an explicit `ssh://` URL for custom ports; SSH aliases are not expanded. If authentication is unavailable, push with your usual Git client instead.
- Push is only to the current branch's single configured upstream, with an explicit non-force refspec. Counts reflect local tracking refs; **no fetch** occurs automatically. Pushing runs against a frozen destination snapshot, so later edits to remote URLs/`insteadOf` rules reject the action rather than redirecting it. A successful push does not refresh your local remote-tracking refs; run your normal fetch to update ahead/behind counts. Changes to the reviewed push destination reject the action.
- Process time/output and review diff sizes are bounded. A truncated diff must be reviewed completely in an external editor/Git before approval.
- After an exceptional post-ref-update/index-install failure, recovery information and the owned index lock are retained. Follow the reported recovery details; never delete locks blindly or retry as though no commits were created.

Proposals and commit receipts persist locally in the worktree Git directory under `dsh-git-review/proposal.json`; they are not tracked or pushed. Review checkmarks are view-local and intentionally reset when refreshing/reopening. One Harness profile serializes mutating review actions per repository.

## Agent access

The `git_review` tool shares the same application service as the UI. Read actions: `status`, explicit-path `diff`, `history`, `branches`. Proposal actions: `organize`, `save`. `commit`, `checkout` and `push` require separate runtime approval for the exact operation and obey the session's workspace policy. UI review acknowledgements cannot be supplied through the tool schema. The tool adds approximately 700 prompt tokens (schema estimate); it adds no standing system-prompt section.

The `/git-review` command is the authenticated, session-addressed UI transport. Direct UI commits/pushes require their own confirmation; tool calls do not inherit UI confirmation.

## Installation and development

Install this directory through Harness `plugin_manager` → `install_bundle` with its absolute path. Keep the directory in place: local directory installation links it. The bundle is profile-wide and survives restart. No dependencies, package scripts or extra services are installed.

After changing an already loaded Host module, follow the plugin manager's reported application/restart status; don't infer a fresh module from an unchanged slot id. This authored bundle doesn't modify shipped Harness artifacts or require a development server.

```sh
node --check client.js
node --test *.test.js
```

Tests use mock models and uniquely owned temporary Git repositories. They do not commit, push or switch branches in the user's workspace. The original SVG icon is authored for this bundle and has no third-party artwork dependency. All containers/control colors use Harness theme tokens; the icon has its own artwork colors. English and Chinese display metadata are exported.
