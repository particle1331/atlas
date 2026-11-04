window.__ModuleLoader__.load({
  id: '@local/dsh-git-review',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useState, useEffect, useRef, useCallback, useMemo } = React;

    const EN = {
      title: 'Git Review',
      currentRepository: 'Current Repository',
      currentBranch: 'Current Branch',
      refresh: 'Refresh',
      pushOrigin: 'Push origin',
      changes: 'Changes',
      history: 'History',
      filter: 'Filter',
      changedFiles: 'changed files',
      noChanges: 'No local changes',
      summary: 'Summary (required)',
      description: 'Description',
      commitTo: 'Commit {n} files to {branch}',
      groupCommits: 'Group commits',
      grouping: 'Grouping…',
      organizingHint: 'Reading diffs and recent sessions; this can take a minute.',
      committing: 'Creating commits…',
      createdCommits: 'Created {n} commits.',
      hooksSkipped: 'Git hooks were skipped, as GitHub Desktop does.',
      unpushed: 'Not pushed yet',
      backToChanges: 'Back to changes',
      proposal: 'Commits to create',
      proposalReady: 'Review the proposed commits',
      review: 'I reviewed this commit',
      commits: 'commits',
      amendMessage: 'Amend message…',
      undoCommit: 'Undo commit',
      copyHash: 'Copy hash',
      copyRelative: 'Copy relative path',
      copyAbsolute: 'Copy absolute path',
      discardChanges: 'Discard changes…',
      discardTitle: 'Discard changes',
      stashChanges: 'Stash changes…',
      stashTitle: 'Stash all changes',
      stashWarning: 'Moves every change, including untracked files, into a stash you can restore with Git.',
      stashedNotice: 'All changes were stashed.',
      discardAll: 'Discard all changes…',
      discardAllTitle: 'Discard all changes',
      discardAllWarning: 'This restores every tracked file from HEAD and deletes untracked files. It cannot be undone.',
      discardWarning: 'This permanently restores the file from HEAD (or deletes an untracked file). It cannot be undone.',
      discardedNotice: 'Discarded changes.',
      amendTitle: 'Amend latest commit',
      undoTitle: 'Undo latest commit',
      amendedNotice: 'Commit message amended.',
      undoneNotice: 'Commit undone; its changes are back in the working tree.',
      headOnly: 'Only the latest commit can be changed.',
      undoWarning: 'This moves the branch back one commit. Its changes return to Changes as unstaged; nothing is pushed or deleted.',
      amendWarning: 'Only the message changes; the commit content stays untouched.',
      createCommits: 'Create commits',
      reviewAll: 'Review every proposed commit first',
      loading: 'Loading…',
      retry: 'Retry',
      cancel: 'Cancel',
      confirm: 'Confirm',
      commitConfirm: 'Commit the selected files?',
      commitNotice: 'The selected files were committed. Nothing was pushed.',
      pushNotice: 'Push this branch to its configured upstream? No force.',
      pushed: 'Pushed. Remote-tracking counts may stay stale until your next fetch.',
      noDiff: 'Select a changed file to see its diff.',
      noHistory: 'No commits yet.',
      binary: 'Binary file — content not displayed.',
      truncated: 'Diff truncated; inspect the complete file in your editor before committing.',
      wrap: 'Wrap lines',
      sideBySide: 'Split view',
      unified: 'Unified view',
      files: 'files',
      allFiles: 'All files',
      why: 'Why these changes belong together',
      warnings: 'Review notes',
      unassigned: 'Unassigned / excluded',
      stale: 'The repository changed after this proposal. Organize again.',
      notReviewed: 'Review every commit before creating the series.',
      noSession: 'Open a repository conversation to review its changes.',
      detached: 'Detached HEAD',
      ahead: 'ahead',
      behind: 'behind',
      upstream: 'Upstream',
      reviewEdits: 'Edits save when you create the commits.',
      switchBranch: 'Switch branch',
      noBranches: 'No local branches',
      switching: 'Switching…',
      switched: 'Switched to',
      cleanRequired: 'Switching branches requires a clean working tree. Commit or discard changes first.',
      groupAgain: 'Group again',
      groupedWith: 'Grouped with',
      reasoningLevel: 'reasoning',
      model:'Model',
      reasoning:'Reasoning',
      providerDefault:'Provider default',
      modelCatalogUnavailable:'Model catalog unavailable; using this session’s model. Expensive scanning models are hidden.',
      stillValid: 'Other files changed; your grouped files are unchanged.',
      affectedFiles: '{n} grouped files changed since this proposal.',
      affectedFile: '1 grouped file changed since this proposal.',
      errorPrefix: 'Git Review'
    };
    const ZH = {
      ...EN,
      title: 'Git 变更审阅',
      currentRepository: '当前仓库',
      currentBranch: '当前分支',
      refresh: '刷新',
      pushOrigin: '推送 origin',
      changes: '变更',
      history: '历史',
      filter: '筛选',
      changedFiles: '个变更文件',
      noChanges: '没有本地变更',
      summary: '摘要（必填）',
      description: '描述',
      commitTo: '提交 {n} 个文件到 {branch}',
      groupCommits: '整理提交',
      grouping: '整理中…',
      organizingHint: '正在读取差异和近期会话，可能需要一分钟。',
      committing: '正在创建提交…',
      createdCommits: '已创建 {n} 个提交。',
      hooksSkipped: '已跳过 Git hooks（与 GitHub Desktop 行为一致）。',
      unpushed: '尚未推送',
      backToChanges: '返回变更',
      proposal: '待创建提交',
      proposalReady: '查看建议提交',
      review: '我已审阅此提交',
      commits: '个提交',
      amendMessage: '修改提交信息…',
      undoCommit: '撤销提交',
      copyHash: '复制哈希',
      copyRelative: '复制相对路径',
      copyAbsolute: '复制绝对路径',
      discardChanges: '放弃变更…',
      discardTitle: '放弃变更',
      discardWarning: '这会从 HEAD 恢复文件（或删除未跟踪文件），无法撤销。',
      stashChanges: '暂存变更…',
      stashTitle: '暂存所有变更',
      stashWarning: '把所有变更（包括未跟踪文件）移入 stash，可用 Git 恢复。',
      stashedNotice: '所有变更已暂存。',
      discardAll: '放弃所有变更…',
      discardAllTitle: '放弃所有变更',
      discardAllWarning: '这会从 HEAD 恢复所有跟踪文件并删除未跟踪文件，无法撤销。',
      discardedNotice: '已放弃变更。',
      amendTitle: '修改最新提交',
      undoTitle: '撤销最新提交',
      amendedNotice: '提交信息已修改。',
      undoneNotice: '已撤销提交，变更回到工作区。',
      headOnly: '只能修改最新提交。',
      undoWarning: '分支回退一个提交，变更以未暂存状态回到“变更”；不会推送或删除内容。',
      amendWarning: '只修改信息，提交内容保持不变。',
      createCommits: '创建提交',
      reviewAll: '请先审阅所有建议提交',
      noDiff: '选择一个变更文件查看差异。',
      noHistory: '还没有提交。',
      binary: '二进制文件 — 不显示内容。',
      truncated: '差异已截断；提交前请在编辑器中检查完整文件。',
      wrap: '自动换行',
      sideBySide: '并排',
      unified: '统一',
      files: '个文件',
      why: '分组依据',
      warnings: '审阅提示',
      unassigned: '未分组 / 已排除',
      stale: '生成方案后仓库已改变，请重新整理。',
      notReviewed: '创建提交系列前请审阅每个提交。',
      noSession: '打开一个仓库会话以审阅其变更。',
      detached: '游离 HEAD',
      ahead: '领先',
      behind: '落后',
      upstream: '上游',
      reviewEdits: '编辑内容会在创建提交时保存。',
      switchBranch: '切换分支',
      noBranches: '没有本地分支',
      switching: '切换中…',
      switched: '已切换到',
      cleanRequired: '切换分支需要干净的工作区。请先提交或还原变更。',
      groupAgain: '重新整理',
      groupedWith: '分组模型',
      reasoningLevel: '推理级别',
      stillValid: '其他文件有变更；已分组的文件未改变。',
      affectedFiles: '有 {n} 个已分组文件在方案生成后改变。',
      commitConfirm: '提交所选文件？',
      commitNotice: '所选文件已提交，未推送。',
      pushed: '推送完成；下次 fetch 前跟踪计数可能仍显示旧值。',
      pushNotice: '将当前分支推送到已配置的上游，不使用强制推送。'
    };

    const CSS = `
.gd{height:100%;min-height:0;display:flex;flex-direction:column;color:var(--dsw-alias-label-primary);background:var(--dsw-alias-bg-base);font-size:12.5px;line-height:1.5;overflow:hidden}
.gd *{box-sizing:border-box}
.gd button,.gd input,.gd textarea,.gd-dialog button{font:inherit;color:inherit}
.gd button{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);border-radius:7px;padding:6px 11px;cursor:pointer;white-space:nowrap}
.gd button:hover{background:var(--dsw-alias-bg-layer-2)}
.gd button:disabled{opacity:.45;cursor:not-allowed}
.gd :focus-visible,.gd-dialog :focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px}
.gd .gd-primary{background:var(--dsw-alias-brand-primary);border-color:var(--dsw-alias-brand-primary);color:var(--dsw-alias-bg-base);font-weight:600}
.gd .gd-primary:hover{filter:brightness(1.08)}
.gd-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr);align-items:stretch;gap:0;padding:0;border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex-shrink:0}
.gd-head>div{display:flex;flex-direction:column;justify-content:center;min-width:0;padding:10px 16px}
.gd-head>div+div{border-left:1px solid var(--dsw-alias-border-l1)}
.gd-kicker{font-size:10.5px;color:var(--dsw-alias-label-secondary);margin-bottom:2px}
.gd-repo{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13.5px;overflow:hidden;text-overflow:ellipsis}
.gd-repo svg{flex-shrink:0;color:var(--dsw-alias-label-secondary)}
.gd-branch{font-weight:600;display:flex;align-items:center;gap:6px}
.gd-branch svg{color:var(--dsw-alias-label-secondary)}
.gd-branchwrap{position:relative}
.gd .gd-branchbtn{display:flex;align-items:center;gap:6px;max-width:100%;padding:4px 7px;background:transparent;border-color:transparent;font-weight:600}
.gd .gd-branchbtn:hover{background:var(--dsw-alias-bg-layer-2);border-color:var(--dsw-alias-border-l1)}
.gd-caret{color:var(--dsw-alias-label-secondary);font-size:10px;margin-left:2px}
.gd-menu{position:absolute;z-index:30;top:calc(100% + 6px);left:0;min-width:250px;max-width:340px;max-height:320px;overflow:auto;background:var(--dsw-alias-bg-overlay);border:1px solid var(--dsw-alias-border-l2);border-radius:9px;padding:5px;box-shadow:0 10px 30px color-mix(in srgb,var(--dsw-alias-label-primary) 18%,transparent)}
.gd .gd-menu-row{display:flex;width:100%;justify-content:space-between;align-items:center;gap:10px;border:0;background:transparent;border-radius:6px;padding:7px 9px;text-align:left;font-weight:500}
.gd .gd-menu-row:hover{background:var(--dsw-alias-bg-layer-2)}
.gd-menu-note{padding:8px 9px;color:var(--dsw-alias-label-secondary);font-size:11px}
.gd-menu-error{padding:8px 9px;color:var(--dsw-alias-state-error-primary);font-size:11px;overflow-wrap:anywhere}
.gd-head-actions{flex-direction:row !important;align-items:center !important;justify-content:flex-start !important;gap:8px;padding:8px 14px !important;flex-wrap:wrap}
.gd-meta{font-size:11px;color:var(--dsw-alias-label-secondary)}
.gd-main{flex:1;min-height:0;display:flex}
.gd-side{width:404px;flex-shrink:0;min-width:280px;display:flex;flex-direction:column;border-right:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);min-height:0}
.gd-tabs{display:flex;border-bottom:1px solid var(--dsw-alias-border-l1);flex-shrink:0}
.gd .gd-tab{flex:1;border:0;border-radius:0;background:transparent;padding:11px 8px;border-bottom:2px solid transparent;color:var(--dsw-alias-label-secondary);font-weight:550}
.gd .gd-tab[aria-selected=true]{color:var(--dsw-alias-label-primary);border-bottom-color:var(--dsw-alias-brand-primary);background:var(--dsw-alias-bg-layer-2)}
.gd .gd-tab:hover{background:var(--dsw-alias-bg-layer-2)}
.gd-filter{padding:9px 12px;border-bottom:1px solid var(--dsw-alias-border-l1);flex-shrink:0}
.gd-filter input{width:100%;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:var(--dsw-alias-bg-base);padding:6px 9px;font-size:12px}
.gd-list{flex:1;min-height:0;overflow:auto;padding:6px 0}
.gd-list-head{display:flex;align-items:center;gap:8px;padding:6px 12px;color:var(--dsw-alias-label-secondary);font-size:11.5px;font-weight:600;position:sticky;top:0;background:var(--dsw-alias-bg-layer-1);z-index:1;flex-shrink:0}
.gd-file{display:flex;align-items:center;gap:9px;width:100%;padding:6px 12px;border:0;border-radius:0;background:transparent;text-align:left;cursor:pointer;white-space:normal}
.gd-file:hover{background:var(--dsw-alias-bg-layer-2)}
.gd-file[aria-selected=true]{background:var(--dsw-alias-bg-layer-2);box-shadow:inset 2px 0 0 var(--dsw-alias-brand-primary)}
.gd-file input[type=checkbox],.gd-check{width:13px;height:13px;accent-color:var(--dsw-alias-brand-primary);flex-shrink:0;cursor:pointer}
.gd-status{width:14px;height:14px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;color:var(--dsw-alias-label-secondary)}
.gd-status.add{color:var(--dsw-alias-state-success-primary)}
.gd-status.del{color:var(--dsw-alias-state-error-primary)}
.gd-status.mod{color:var(--dsw-alias-state-warn-primary)}
.gd-path{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}
.gd-path .gd-dir{color:var(--dsw-alias-label-secondary)}
.gd-path .gd-name{font-weight:500}
.gd-commit-box{border-top:1px solid var(--dsw-alias-border-l1);padding:10px 12px 12px;display:flex;flex-direction:column;gap:7px;flex-shrink:0;background:var(--dsw-alias-bg-layer-1)}
.gd-commit-box input,.gd-commit-box textarea{width:100%;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:var(--dsw-alias-bg-base);padding:6px 8px;font-size:12px;resize:vertical}
.gd-commit-box textarea{min-height:52px;max-height:130px}
.gd .gd-group-btn{display:flex;align-items:center;justify-content:center;gap:7px;border-color:var(--dsw-alias-brand-primary);color:var(--dsw-alias-brand-primary);background:transparent;font-weight:600}
.gd .gd-group-btn:hover{background:color-mix(in srgb,var(--dsw-alias-brand-primary) 10%,transparent)}
.gd-selects{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:6px}
.gd-selects label{display:flex;flex-direction:column;gap:2px;font-size:10.5px;color:var(--dsw-alias-label-secondary)}
.gd-selects select{width:100%;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:var(--dsw-alias-bg-base);padding:4px 6px;font-size:11px;min-width:0}
.gd-commit-count{font-size:11px;color:var(--dsw-alias-label-secondary);display:flex;justify-content:space-between;gap:6px;overflow-wrap:anywhere}
.gd-files{width:262px;flex-shrink:0;display:flex;flex-direction:column;min-height:0;border-right:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1)}
.gd-diff{flex:1;min-width:0;display:flex;flex-direction:column;min-height:0;background:var(--dsw-alias-bg-base)}
.gd-diff-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 16px;border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex-shrink:0}
.gd-diff-title{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gd-diff-tools{display:flex;align-items:center;gap:8px;flex-shrink:0}
.gd-diff-tools label{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--dsw-alias-label-secondary);white-space:nowrap}
.gd-diff-body{flex:1;min-height:0;overflow:auto}
.gd-code{font:11.5px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:auto;min-height:100%;white-space:pre;background:var(--dsw-alias-bg-base)}
.gd-code.gd-wrap{white-space:pre-wrap;overflow-wrap:anywhere}
.gd-line{display:block;padding:0 14px;min-width:max-content}
.gd-wrap .gd-line{min-width:0}
.gd-add{background:color-mix(in srgb,var(--dsw-alias-state-success-primary) 13%,transparent)}
.gd-del{background:color-mix(in srgb,var(--dsw-alias-state-error-primary) 13%,transparent)}
.gd-hunk{background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary)}
.gd-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);min-height:100%}
.gd-split>div{overflow:auto}
.gd-split>div+div{border-left:1px solid var(--dsw-alias-border-l1)}
.gd-pad{padding:14px 16px}
.gd-muted{color:var(--dsw-alias-label-secondary)}
.gd-small{font-size:11px}
.gd-error{color:var(--dsw-alias-state-error-primary)}
.gd-warn{color:var(--dsw-alias-state-warn-primary)}
.gd-banner{padding:8px 16px;border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);display:flex;gap:10px;align-items:center;flex-wrap:wrap;overflow-wrap:anywhere;flex-shrink:0}
.gd-banner.gd-warn{color:var(--dsw-alias-state-warn-primary)}
.gd-banner.gd-ok{color:var(--dsw-alias-state-success-primary)}
.gd-banner.gd-bad{color:var(--dsw-alias-state-error-primary)}
.gd-group-list{padding:8px}
.gd .gd-group-card{display:block;width:100%;text-align:left;border:1px solid transparent;background:transparent;padding:9px 10px;border-radius:8px;margin-bottom:2px;white-space:normal}
.gd .gd-group-card:hover{background:var(--dsw-alias-bg-layer-2)}
.gd .gd-group-card[aria-selected=true]{background:var(--dsw-alias-bg-layer-2);border-color:var(--dsw-alias-border-l1)}
.gd-group-title{display:flex;gap:9px;align-items:flex-start;font-weight:550}
.gd-num{width:20px;height:20px;border-radius:50%;border:1px solid var(--dsw-alias-border-l2);flex-shrink:0;text-align:center;line-height:18px;font-size:10.5px;font-weight:600}
.gd-group-meta{color:var(--dsw-alias-label-secondary);font-size:11px;margin:3px 0 0 29px}
.gd-field{width:100%;margin:4px 0 10px;border:1px solid var(--dsw-alias-border-l1);border-radius:6px;background:var(--dsw-alias-bg-base);padding:7px 9px}
.gd-msg{font-size:14px;font-weight:600}
.gd-reason{border:1px solid var(--dsw-alias-border-l1);border-radius:8px;background:var(--dsw-alias-bg-layer-1);padding:10px 12px;margin:10px 0}
.gd-reason p{margin:3px 0 0}
.gd-fileblock{border:1px solid var(--dsw-alias-border-l1);border-radius:8px;margin:10px 0;overflow:hidden}
.gd-fileblock summary{cursor:pointer;padding:8px 11px;background:var(--dsw-alias-bg-layer-1);font-family:ui-monospace,monospace;font-size:11.5px;overflow-wrap:anywhere}
.gd-fileblock summary::-webkit-details-marker{display:none}
.gd-review{display:flex;align-items:center;gap:8px;padding:10px 0;font-weight:550}
.gd-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.gd-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;text-align:center;padding:28px;color:var(--dsw-alias-label-secondary)}
.gd-empty h3{margin:0;font-size:15px;color:var(--dsw-alias-label-primary)}
.gd-empty svg{color:var(--dsw-alias-label-secondary)}
.gd-dialog{max-width:600px;width:calc(100% - 48px);max-height:80vh;overflow:auto;padding:22px;border:1px solid var(--dsw-alias-border-l2);border-radius:14px;background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);font:13px/1.6 system-ui,sans-serif;box-shadow:0 24px 60px rgba(0,0,0,.45)}
.gd-dialog::backdrop{background:rgba(0,0,0,.45)}
.gd-dialog h3{font-size:17px;margin:0 0 10px}
.gd-dialog p{color:var(--dsw-alias-label-secondary);margin:6px 0}
.gd-dialog .gd-actions{justify-content:flex-end;margin-top:16px}
.gd-spark{color:var(--dsw-alias-brand-primary)}
.gd-ahead-badge{flex-shrink:0;font-size:10px;line-height:1.2;color:var(--dsw-alias-brand-primary);border:1px solid var(--dsw-alias-brand-primary);border-radius:4px;padding:0 4px}
.gd-ctx{position:fixed;z-index:60;min-width:200px;background:var(--dsw-alias-bg-overlay);border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:4px;box-shadow:0 10px 30px color-mix(in srgb,var(--dsw-alias-label-primary) 18%,transparent)}
.gd .gd-ctx button{display:block;width:100%;border:0;background:transparent;text-align:left;border-radius:6px;padding:7px 9px}
.gd .gd-ctx button:hover{background:var(--dsw-alias-bg-layer-2)}
.gd .gd-ctx button:disabled{opacity:.42}
.gd-spin{animation:gd-spin .9s linear infinite;flex-shrink:0;vertical-align:-2px}
.gd-btn-busy{display:inline-flex;align-items:center;gap:6px}
@keyframes gd-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.gd-spin{animation-duration:2.4s}}
@media(max-width:900px){.gd-side{width:330px}.gd-head>div{padding:8px 12px}.gd-head-actions{padding:8px 10px !important}}
@media(max-width:1100px){.gd-files{width:220px}}
@media(max-width:900px){.gd-files{width:190px}.gd-path{font-size:11px}}
@media(max-width:680px){.gd-main{flex-direction:column}.gd-side{width:100%;max-height:42%;border-right:0;border-bottom:1px solid var(--dsw-alias-border-l1)}.gd-files{display:none}.gd-diff{min-height:200px}.gd-head{grid-template-columns:1fr auto}.gd-head .gd-branch-cell{display:none}}
`;

    function RepoIcon({size = 18}) {
      return h('svg', {width:size, height:size, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:1.7, 'aria-hidden':true},
        h('path', {d:'M5 4.5A2.5 2.5 0 0 1 7.5 2H18a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7.5A2.5 2.5 0 0 1 5 17.5v-13Z'}),
        h('path', {d:'M8 2v17m0-8h7'}));
    }
    function StatusIcon({status}) {
      const raw = String(status || '').replace(/[.\s]/g, '');
      const letter = raw.startsWith('?') ? 'A' : (raw[0] || 'M');
      const label = letter === 'A' ? 'Added' : letter === 'D' ? 'Deleted' : letter === 'R' ? 'Renamed' : 'Modified';
      const frame = h('rect', {x:1.4, y:1.4, width:11.2, height:11.2, rx:2.4, fill:'none', stroke:'currentColor', strokeWidth:1.3});
      let mark;
      if (letter === 'A') {
        mark = h('path', {d:'M7 4.3v5.4M4.3 7h5.4', stroke:'currentColor', strokeWidth:1.5, strokeLinecap:'round'});
      } else if (letter === 'D') {
        mark = h('path', {d:'M4.3 7h5.4', stroke:'currentColor', strokeWidth:1.5, strokeLinecap:'round'});
      } else if (letter === 'R') {
        mark = h('path', {d:'M4.2 7h5.6M7.6 4.8 9.8 7l-2.2 2.2', stroke:'currentColor', strokeWidth:1.3, strokeLinecap:'round', strokeLinejoin:'round'});
      } else {
        mark = h('circle', {cx:7, cy:7, r:2.1, fill:'currentColor'});
      }
      const tone = letter === 'A' ? 'add' : letter === 'D' ? 'del' : 'mod';
      return h('svg', {className:'gd-status ' + tone, width:14, height:14, viewBox:'0 0 14 14', role:'img', 'aria-label':label},
        h('title', null, label), frame, mark);
    }

    function BranchIcon({size = 15}) {
      return h('svg', {width:size, height:size, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:1.7, 'aria-hidden':true},
        h('circle', {cx:6, cy:5, r:2.2}), h('circle', {cx:6, cy:19, r:2.2}), h('circle', {cx:18, cy:7, r:2.2}),
        h('path', {d:'M6 7.2v9.6M6 12c0-5 12 0 12-2.8'}));
    }
    function SparkIcon() {
      return h('svg', {width:14, height:14, viewBox:'0 0 24 24', fill:'currentColor', 'aria-hidden':true, className:'gd-spark'},
        h('path', {d:'M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Zm6 12l.9 2.6 2.6.9-2.6.9L18 21l-.9-2.6-2.6-.9 2.6-.9L18 14ZM5 15l.7 2 2 .7-2 .7L5 20.4l-.7-2-2-.7 2-.7L5 15Z'}));
    }

    function Spinner({size = 14}) {
      return h('svg', {className:'gd-spin', width:size, height:size, viewBox:'0 0 24 24', fill:'none', 'aria-hidden':true},
        h('circle', {cx:12, cy:12, r:9, stroke:'currentColor', strokeWidth:2.5, opacity:.25}),
        h('path', {d:'M21 12a9 9 0 0 0-9-9', stroke:'currentColor', strokeWidth:2.5, strokeLinecap:'round'}));
    }

    function Dialog({title, children, onCancel, onConfirm, confirmLabel, t, busy}) {
      const ref = useRef(null);
      useEffect(() => { ref.current?.showModal(); return () => ref.current?.close(); }, []);
      return h('dialog', {ref, className:'gd-dialog', onCancel: e => { e.preventDefault(); if (!busy) onCancel(); }, 'aria-label': title},
        h('h3', null, title), children,
        h('div', {className:'gd-actions'},
          h('button', {onClick: onCancel, disabled: busy, autoFocus:true}, t('cancel')),
          h('button', {className:'gd-primary', onClick: onConfirm, disabled: busy}, busy ? t('loading') : confirmLabel)));
    }

    function DiffText({data, wrap, split, t}) {
      if (data === undefined && data !== null) return h('p', {className:'gd-pad gd-muted'}, t('loading'));
      if (data === undefined || data === null) return h('p', {className:'gd-pad gd-muted'}, t('loading'));
      if (data.error) return h('p', {className:'gd-pad gd-error'}, data.error);
      const text = data.text || data.diff || '';
      const lines = text.split('\n');
      const kind = line => line.startsWith('+++') || line.startsWith('---') ? 'gd-hunk'
        : line.startsWith('+') ? 'gd-add' : line.startsWith('-') ? 'gd-del'
        : line.startsWith('@@') || line.startsWith('diff --git') ? 'gd-hunk' : '';
      function column(xs) {
        return h('div', {className:'gd-code' + (wrap ? ' gd-wrap' : '')},
          xs.map((line, i) => h('span', {key:i, className:'gd-line ' + kind(line)}, line || ' ')));
      }
      const paired = [];
      if (split) {
        let oldNo = 0, nextNo = 0, inHunk = false;
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          const m = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
          if (m) { oldNo = Number(m[1]); nextNo = Number(m[2]); inHunk = true; paired.push({left:line, right:line}); continue; }
          if (line.startsWith('diff --git')) inHunk = false;
          if (inHunk && (line.startsWith('-') || line.startsWith('+'))) {
            const removed = [], added = [];
            while (i < lines.length && (lines[i].startsWith('-') || lines[i].startsWith('+'))) {
              const value = lines[i++]; (value[0] === '-' ? removed : added).push(value);
            }
            i--;
            for (let j = 0; j < Math.max(removed.length, added.length); j++) {
              paired.push({left: removed[j] || '', right: added[j] || '', old: removed[j] ? oldNo++ : '', next: added[j] ? nextNo++ : ''});
            }
          } else {
            const context = inHunk && line.startsWith(' ');
            paired.push({left: line, right: line, old: context ? oldNo++ : '', next: context ? nextNo++ : ''});
          }
        }
      }
      return h(React.Fragment, null,
        data.binary && h('p', {className:'gd-pad gd-muted'}, t('binary')),
        data.truncated && h('p', {className:'gd-pad gd-warn'}, t('truncated')),
        !text ? h('p', {className:'gd-pad gd-muted'}, t('noDiff'))
          : split ? h('div', {className:'gd-split'}, ['left', 'right'].map((side, index) => {
              const no = index === 0 ? 'old' : 'next';
              return h('div', {key:side, className:'gd-code' + (wrap ? ' gd-wrap' : '')},
                paired.map((row, i) => h('span', {key:i, className:'gd-line ' + kind(row[side])},
                  h('span', {className:'gd-muted', 'aria-hidden':true, style:{display:'inline-block', minWidth:'4ch', paddingRight:'1ch', userSelect:'none'}}, row[no] || ''),
                  row[side] || ' ')));
            }))
          : column(lines));
    }

    return {
      inject: ['slots', 'locale', 'remote', 'remote.commands'],
      apply(ctx) {
        ctx.effect(() => ctx.locale.register('localGitReview', 'en', EN));
        ctx.effect(() => ctx.locale.register('localGitReview', 'zh', ZH));
        const t = ctx.locale.bind('localGitReview');

        async function rpc(sessionId, request) {
          const result = await ctx.remote.commands.execute(sessionId, `/git-review ${JSON.stringify(request)}`, []);
          if (!result.ok) throw new Error(result.error?.message || result.error?.code || 'Remote request failed');
          const response = result.value?.result;
          if (!response) throw new Error('Git Review command is unavailable.');
          let data;
          try { data = JSON.parse(response.text || '{}'); }
          catch { throw new Error(response.text || 'Invalid Git Review response'); }
          if (response.kind === 'error' || data.error) throw Object.assign(new Error(data.error || response.text), {code: data.code});
          return data;
        }

        function hooksSkipped(result) {
          return Boolean(result?.warnings?.some(warning => warning?.code === 'HOOKS_SKIPPED'));
        }

        function statusLetter(status) {
          const raw = String(status || '').replace(/[.\s]/g, '');
          if (raw.startsWith('?')) return 'A';
          return raw[0] || 'M';
        }
        function statusClass(letter) {
          return letter === 'A' ? 'add' : letter === 'D' || letter === 'R' ? 'del' : 'mod';
        }
        function splitPath(p) {
          const index = p.lastIndexOf('/');
          return index < 0 ? ['', p] : [p.slice(0, index + 1), p.slice(index + 1)];
        }
        function repoName(root) { return root ? root.split('/').filter(Boolean).pop() : ''; }
        function versionFrom(text, pattern) {
          const match = pattern.exec(text);
          if (!match) return [];
          return match[1].split('.').map(Number).filter(value => Number.isFinite(value));
        }
        function compareVersion(left, right) {
          const length = Math.max(left.length, right.length);
          for (let i = 0; i < length; i++) {
            const a = left[i] || 0, b = right[i] || 0;
            if (a !== b) return a - b;
          }
          return 0;
        }

        function Review({sessionId}) {
          React.useSyncExternalStore(fn => ctx.locale.subscribe(fn), () => ctx.locale.getSnapshot());
          const [data, setData] = useState(null);
          const [error, setError] = useState('');
          const [notice, setNotice] = useState('');
          const [busy, setBusy] = useState('');
          const [organizePhase, setOrganizePhase] = useState('');
          const [tab, setTab] = useState('changes');
          const [filter, setFilter] = useState('');
          const [selectedPath, setSelectedPath] = useState(null);
          const [checked, setChecked] = useState([]);
          const [summary, setSummary] = useState('');
          const [description, setDescription] = useState('');
          const [catalog, setCatalog] = useState(null);
          const [selection, setSelection] = useState(null);
          const [reasoningOptions, setReasoningOptions] = useState({efforts:[], defaultEffort:null});
          const reasoningTouched = useRef(false);
          const [diffs, setDiffs] = useState({});
          const [wrap, setWrap] = useState(false);
          const [split, setSplit] = useState(false);
          const [commits, setCommits] = useState([]);
          const [selectedCommit, setSelectedCommit] = useState(null);
          const [selectedCommitPath, setSelectedCommitPath] = useState(null);
          const [commitFiles, setCommitFiles] = useState({});
          const commitFilesLoaded = useRef(new Set());
          const [proposal, setProposal] = useState(null);
          const [proposalDirty, setProposalDirty] = useState(false);
          const [proposalPath, setProposalPath] = useState(null);
          const [groupIndex, setGroupIndex] = useState(0);
          const [modal, setModal] = useState(null);
          const [branchMenu, setBranchMenu] = useState(null);
          const [ctxMenu, setCtxMenu] = useState(null);
          const [amendDraft, setAmendDraft] = useState({summary:'', description:''});
          const branchRef = useRef(null);
          const diffCache = useRef(new Map());
          const mounted = useRef(true);
          const selectionPrint = useRef(null);

          useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

          const snapshot = data?.snapshot;
          const draft = data?.draft;
          const files = snapshot?.files || [];
          const affected = draft?.affectedPaths || [];
          const visibleFiles = useMemo(() => {
            const query = filter.trim().toLowerCase();
            return query ? files.filter(f => f.path.toLowerCase().includes(query)) : files;
          }, [files, filter]);
          const checkedSet = useMemo(() => new Set(checked), [checked]);
          const unpushed = useMemo(() => {
            if (!snapshot?.upstream || !snapshot.ahead) return new Set();
            return new Set(commits.slice(0, snapshot.ahead).map(commit => commit.hash));
          }, [commits, snapshot?.upstream, snapshot?.ahead]);
          const activeGroup = proposal?.groups?.[groupIndex] || null;
          const activeGroups = proposal?.groups || [];

          const accept = useCallback((next, {keepProposal = false} = {}) => {
            if (!mounted.current) return;
            setData(next);
            if (!keepProposal) { setProposal(null); setProposalDirty(false); setProposalPath(null); }
            setSelectedPath(prev => next.snapshot?.files?.some(f => f.path === prev) ? prev : null);
            const fingerprint = next.snapshot?.fingerprint;
            if (fingerprint !== selectionPrint.current) {
              selectionPrint.current = fingerprint;
              setChecked((next.snapshot?.files || []).filter(f => !f.sensitive && !f.conflict && !f.submodule).map(f => f.path));
            }
          }, []);

          const refresh = useCallback(async () => {
            setBusy('refresh'); setError('');
            try {
              const next = await rpc(sessionId, {action:'status'});
              if (!mounted.current) return;
              accept(next);
              diffCache.current.clear(); setDiffs({});
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }, [sessionId, accept]);

          useEffect(() => { refresh(); }, [refresh]);

          useEffect(() => {
            let stopped = false;
            (async () => {
              try {
                const result = await rpc(sessionId, {action:'models'});
                if (!stopped) setCatalog(result.providers || []);
              } catch { if (!stopped) setCatalog([]); }
            })();
            return () => { stopped = true; };
          }, [sessionId]);

          // Choose the saved model, else the session's model, else the first offered.
          useEffect(() => {
            if (!catalog || selection) return;
            const offered = (provider, model) => catalog.some(row => row.provider === provider && row.models.some(m => m.id === model));
            let saved = null;
            try { saved = JSON.parse(window.localStorage.getItem('dsh.git-review.model') || 'null'); } catch {}
            const session = data?.selection;
            if (saved && offered(saved.provider, saved.model)) {
              reasoningTouched.current = Boolean(saved.reasoningEffort);
              setSelection({provider:saved.provider, model:saved.model, reasoningEffort:saved.reasoningEffort || 'low'});
              return;
            }
            // Preferred cheap grouping models: newest deepseek-flash, then the
            // newest Luna version (e.g. gpt-6.1-luna), then the session model.
            const newest = (matches, versionOf) => {
              let best = null;
              for (const row of catalog) {
                for (const item of row.models) {
                  if (!matches(item)) continue;
                  const version = versionOf(`${item.id} ${item.name || ''}`);
                  if (!best || compareVersion(version, best.version) > 0) best = {provider:row.provider, model:item.id, version};
                }
              }
              return best;
            };
            const flash = newest(item => /deepseek/i.test(item.id + ' ' + (item.name || '')) && /flash/i.test(item.id + ' ' + (item.name || '')),
              text => versionFrom(text, /deepseek(?:[-_ ]?(?:v)?)?(\d+(?:\.\d+)*)[-_ ]?flash/i));
            const luna = newest(item => /\bluna\b/i.test(item.id + ' ' + (item.name || '')),
              text => versionFrom(text, /(?:gpt[-_ ]?)?[a-z]*[-_ ]?(\d+(?:\.\d+)*)[-_ ]?luna/i));
            let choice = null;
            if (flash) choice = {provider:flash.provider, model:flash.model, reasoningEffort:'low'};
            else if (luna) choice = {provider:luna.provider, model:luna.model, reasoningEffort:'low'};
            if (!choice && session && offered(session.provider, session.model)) choice = {provider:session.provider, model:session.model, reasoningEffort:'low'};
            if (!choice) {
              const row = catalog.find(item => item.models.length > 0);
              if (row) choice = {provider:row.provider, model:row.models[0].id, reasoningEffort:'low'};
            }
            if (choice) setSelection(choice);
          }, [catalog, data?.selection, selection]);

          // Reasoning levels come from the selected model's capability metadata.
          useEffect(() => {
            if (!selection) return;
            let stopped = false;
            setReasoningOptions({efforts:[], defaultEffort:null});
            (async () => {
              try {
                const info = await rpc(sessionId, {action:'modelInfo', provider:selection.provider, model:selection.model});
                if (stopped) return;
                setReasoningOptions({efforts:info.efforts || [], defaultEffort:info.defaultEffort ?? null});
                if (!reasoningTouched.current) {
                  const low = (info.efforts || []).find(effort => effort.id === 'low');
                  setSelection(current => current && current.provider === selection.provider && current.model === selection.model
                    ? {...current, reasoningEffort: low ? 'low' : ''} : current);
                }
              } catch { if (!stopped) setReasoningOptions({efforts:[], defaultEffort:null}); }
            })();
            return () => { stopped = true; };
          }, [sessionId, selection?.provider, selection?.model]);

          function chooseModel(value) {
            const [provider, model] = value.split('\u0000');
            reasoningTouched.current = false;
            const next = {provider, model, reasoningEffort:'low'};
            setSelection(next);
            try { window.localStorage.setItem('dsh.git-review.model', JSON.stringify(next)); } catch {}
          }
          function chooseReasoning(value) {
            reasoningTouched.current = true;
            const next = {...selection, reasoningEffort:value};
            setSelection(next);
            try { window.localStorage.setItem('dsh.git-review.model', JSON.stringify(next)); } catch {}
          }

          const diffSpecs = useMemo(() => {
            if (tab === 'history') {
              if (!selectedCommit) return [];
              const key = `commit:${selectedCommit}${selectedCommitPath ? ':' + selectedCommitPath : ''}`;
              return [{key, commit: selectedCommit, ...(selectedCommitPath ? {path: selectedCommitPath} : {})}];
            }
            const paths = tab === 'proposal' ? (activeGroup?.paths || []) : (selectedPath ? [selectedPath] : []);
            return paths.map(p => ({key: p, path: p}));
          }, [tab, selectedCommit, selectedCommitPath, activeGroup, selectedPath]);

          useEffect(() => {
            let stopped = false;
            const queue = diffSpecs.filter(spec => !diffCache.current.has(spec.key));
            async function worker(items) {
              while (items.length && !stopped) {
                const spec = items.shift();
                try {
                  const result = await rpc(sessionId, {action:'diff', ...(spec.commit ? {commit: spec.commit, ...(spec.path ? {path: spec.path} : {})} : {path: spec.path})});
                  if (stopped) return;
                  diffCache.current.set(spec.key, result);
                  setDiffs(old => ({...old, [spec.key]: result}));
                } catch (e) {
                  if (!stopped) setDiffs(old => ({...old, [spec.key]: {error: e.message}}));
                }
              }
            }
            const items = queue.slice();
            for (let i = 0; i < Math.min(4, items.length); i++) worker(items);
            return () => { stopped = true; };
          }, [sessionId, diffSpecs]);

          const loadHistory = useCallback(async () => {
            setBusy('history');
            try {
              const result = await rpc(sessionId, {action:'history'});
              if (!mounted.current) return;
              setCommits(result.commits || []);
              setSelectedCommit((result.commits || [])[0]?.hash || null);
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }, [sessionId]);

          useEffect(() => { if (tab === 'history') loadHistory(); }, [tab, loadHistory]);

          useEffect(() => {
            if (!ctxMenu) return;
            const close = () => setCtxMenu(null);
            // Capture-phase dismissal must not swallow the menu item's own click.
            const onPointer = event => {
              if (event.target instanceof Element && event.target.closest('.gd-ctx')) return;
              close();
            };
            const key = event => { if (event.key === 'Escape') close(); };
            window.addEventListener('pointerdown', onPointer, true);
            window.addEventListener('scroll', close, true);
            window.addEventListener('keydown', key);
            return () => {
              window.removeEventListener('pointerdown', onPointer, true);
              window.removeEventListener('scroll', close, true);
              window.removeEventListener('keydown', key);
            };
          }, [ctxMenu]);

          useEffect(() => {
            if (tab !== 'history' || !selectedCommit || commitFilesLoaded.current.has(selectedCommit)) return;
            let stopped = false;
            (async () => {
              try {
                const result = await rpc(sessionId, {action:'commitFiles', commit:selectedCommit});
                if (stopped) return;
                commitFilesLoaded.current.add(selectedCommit);
                setCommitFiles(old => ({...old, [selectedCommit]: result.files || []}));
                setSelectedCommitPath(prev => prev && (result.files || []).some(f => f.path === prev) ? prev : ((result.files || [])[0]?.path ?? null));
              } catch (e) { if (!stopped) setError(e.message); }
            })();
            return () => { stopped = true; };
          }, [tab, selectedCommit, sessionId]);

          useEffect(() => {
            if (!branchMenu) return;
            const onPointer = event => {
              if (branchRef.current && event.target instanceof Node && branchRef.current.contains(event.target)) return;
              setBranchMenu(null);
            };
            document.addEventListener('pointerdown', onPointer, true);
            return () => document.removeEventListener('pointerdown', onPointer, true);
          }, [branchMenu]);

          function toggleChecked(path) {
            setChecked(old => old.includes(path) ? old.filter(p => p !== path) : [...old, path]);
          }
          function toggleAll() {
            const selectable = visibleFiles.filter(f => !f.sensitive && !f.conflict && !f.submodule).map(f => f.path);
            const allSelected = selectable.length > 0 && selectable.every(p => checkedSet.has(p));
            setChecked(old => allSelected ? old.filter(p => !selectable.includes(p)) : [...new Set([...old, ...selectable])]);
          }

          async function runCommit() {
            const proceed = await new Promise(resolve => setModal({action:'commitSelected', resolve}));
            setModal(null);
            if (!proceed) return;
            setBusy('commit'); setError('');
            try {
              const result = await rpc(sessionId, {action:'commitSelected', summary: summary.trim(), description, paths: checked, confirmed: true});
              if (!mounted.current) return;
              setSummary(''); setDescription('');
              diffCache.current.clear(); setDiffs({});
              const next = await rpc(sessionId, {action:'status'});
              if (!mounted.current) return;
              accept(next);
              setNotice(t('commitNotice') + (hooksSkipped(result) ? ' ' + t('hooksSkipped') : ''));
              await loadHistory();
              setTab('history');
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function organize() {
            setBusy('organize'); setOrganizePhase('grouping'); setError(''); setNotice('');
            try {
              const next = await rpc(sessionId, {action:'organize', ...(selection ? {provider:selection.provider, model:selection.model, ...(selection.reasoningEffort ? {reasoningEffort:selection.reasoningEffort} : {})} : {})});
              if (!mounted.current) return;
              const draftNow = next.draft;
              if (!draftNow?.groups?.length) throw new Error('Grouping produced no commits.');
              setData(next);
              setOrganizePhase('committing');
              const result = await rpc(sessionId, {action:'commit', planId:draftNow.id, revision:draftNow.revision, confirmed:true});
              if (!mounted.current) return;
              const count = result.commits?.length ?? draftNow.groups.length;
              setNotice(t('createdCommits').replace('{n}', count) + (hooksSkipped(result) ? ' ' + t('hooksSkipped') : ''));
              setProposal(null); setProposalPath(null);
              diffCache.current.clear(); setDiffs({});
              const fresh = await rpc(sessionId, {action:'status'});
              if (!mounted.current) return;
              accept(fresh);
              await loadHistory();
              setTab('history');
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) { setBusy(''); setOrganizePhase(''); } }
          }

          async function createCommits() {
            setBusy('commit'); setError('');
            try {
              let current = proposal;
              if (proposalDirty) {
                const saved = await rpc(sessionId, {action:'save', planId: draft.id, revision: draft.revision, groups: current.groups.map(({id, title, body, rationale, paths}) => ({id, title, body, rationale, paths}))});
                if (!mounted.current) return;
                current = saved.draft;
                setProposal({...saved.draft, groups: saved.draft.groups.map(g => ({...g}))});
                setProposalPath(saved.draft.groups[groupIndex]?.paths?.[0] ?? null);
                setProposalDirty(false);
                setData(prev => ({...prev, draft: saved.draft}));
              }
              await rpc(sessionId, {action:'commit', planId: current.id, revision: current.revision, confirmed: true});
              if (!mounted.current) return;
              setNotice(t('commitNotice'));
              setProposal(null); setProposalPath(null);
              const next = await rpc(sessionId, {action:'status'});
              if (!mounted.current) return;
              accept(next);
              await loadHistory();
              setTab('history');
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function openBranchMenu() {
            if (branchMenu) { setBranchMenu(null); return; }
            setBranchMenu({loading:true, branches:[], error:''});
            try {
              const result = await rpc(sessionId, {action:'branches'});
              if (mounted.current) setBranchMenu({loading:false, branches:result.branches || [], error:''});
            } catch (e) {
              if (mounted.current) setBranchMenu({loading:false, branches:[], error:e.message});
            }
          }
          function chooseBranch(name) {
            setBranchMenu(null);
            if (name === snapshot?.branch) return;
            if (files.length) { setError(t('cleanRequired')); return; }
            setModal({action:'checkout', branch:name});
          }
          async function confirmCheckout() {
            const branch = modal?.branch;
            setModal(null);
            setBusy('checkout'); setError('');
            try {
              await rpc(sessionId, {action:'checkout', branch, expectedHead:snapshot.head, confirmed:true});
              if (!mounted.current) return;
              setNotice(t('switched') + ' ' + branch);
              await refresh();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmStash() {
            setModal(null);
            setBusy('stash'); setError('');
            try {
              await rpc(sessionId, {action:'stashChanges', confirmed:true});
              if (!mounted.current) return;
              setNotice(t('stashedNotice'));
              await refresh();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmDiscardAll() {
            setModal(null);
            setBusy('discard'); setError('');
            try {
              await rpc(sessionId, {action:'discardChanges', paths:files.map(file => file.path), confirmed:true});
              if (!mounted.current) return;
              setNotice(t('discardedNotice'));
              await refresh();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmDiscard() {
            const target = modal?.path;
            setModal(null);
            setBusy('discard'); setError('');
            try {
              await rpc(sessionId, {action:'discardChanges', paths:[target], confirmed:true});
              if (!mounted.current) return;
              setNotice(t('discardedNotice'));
              await refresh();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmUndo() {
            setModal(null);
            setBusy('undo'); setError('');
            try {
              await rpc(sessionId, {action:'undoCommit', expectedHead:snapshot.head, confirmed:true});
              if (!mounted.current) return;
              setNotice(t('undoneNotice'));
              await refresh();
              await loadHistory();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmAmend() {
            setModal(null);
            setBusy('amend'); setError('');
            try {
              const result = await rpc(sessionId, {action:'amendCommit', summary:amendDraft.summary, description:amendDraft.description, expectedHead:snapshot.head, confirmed:true});
              if (!mounted.current) return;
              setNotice(t('amendedNotice') + (hooksSkipped(result) ? ' ' + t('hooksSkipped') : ''));
              await refresh();
              await loadHistory();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          async function confirmPush() {
            setModal(null);
            setBusy('push'); setError('');
            try {
              const result = await rpc(sessionId, {action:'push', expectedHead: snapshot.head, expectedTarget: snapshot.pushTarget?.fingerprint, confirmed: true});
              if (!mounted.current) return;
              setNotice(t('pushed') + (hooksSkipped(result) ? ' ' + t('hooksSkipped') : ''));
              await refresh();
            } catch (e) { if (mounted.current) setError(e.message); }
            finally { if (mounted.current) setBusy(''); }
          }

          const canCommit = !!snapshot && checked.length > 0 && summary.trim().length > 0 &&
            !files.some(f => f.staged || f.conflict || f.submodule) && !busy;

          function diffTools() {
            return h('div', {className:'gd-diff-tools'},
              h('label', null, h('input', {type:'checkbox', checked: wrap, onChange: e => setWrap(e.target.checked)}), t('wrap')),
              h('button', {onClick: () => setSplit(s => !s), 'aria-pressed': split}, split ? t('unified') : t('sideBySide')));
          }

          function fileRow(file) {
            const letter = statusLetter(file.status);
            const [dir, name] = splitPath(file.path);
            const disabled = file.sensitive || file.conflict || file.submodule;
            return h('div', {key:file.path, className:'gd-file', role:'button', tabIndex:0, 'aria-selected': selectedPath === file.path,
              onClick: () => { setSelectedPath(file.path); setTab('changes'); },
              onContextMenu:e => { e.preventDefault(); e.stopPropagation(); setSelectedPath(file.path); setCtxMenu({kind:'file', path:file.path, x:Math.min(e.clientX, window.innerWidth - 250), y:Math.min(e.clientY, window.innerHeight - 170)}); },
              onKeyDown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedPath(file.path); setTab('changes'); } }},
              h('input', {type:'checkbox', checked: checkedSet.has(file.path) && !disabled, disabled,
                onClick: e => e.stopPropagation(), onChange: () => toggleChecked(file.path), 'aria-label': `Include ${file.path}`}),
              h(StatusIcon, {status:file.status}),
              h('span', {className:'gd-path'}, h('span', {className:'gd-dir'}, dir), h('span', {className:'gd-name'}, name)),
              file.sensitive && h('span', {className:'gd-small gd-error'}, 'secret?'));
          }

          function changesPane() {
            const allVisibleSelected = visibleFiles.length > 0 &&
              visibleFiles.every(f => checkedSet.has(f.path) || f.sensitive || f.conflict || f.submodule);
            return h(React.Fragment, null,
              h('div', {className:'gd-filter'}, h('input', {placeholder:t('filter'), value:filter, onChange:e => setFilter(e.target.value), 'aria-label':t('filter')})),
              h('div', {className:'gd-list-head', onContextMenu:e => { e.preventDefault(); setCtxMenu({kind:'all', x:Math.min(e.clientX, window.innerWidth - 260), y:Math.min(e.clientY, window.innerHeight - 170)}); }},
                h('input', {type:'checkbox', className:'gd-check', checked:allVisibleSelected, onChange:toggleAll, 'aria-label':'Select all changed files'}),
                h('span', null, files.length, ' ', t('changedFiles'))),
              h('div', {className:'gd-list'}, files.length === 0
                ? h('div', {className:'gd-empty'}, h(RepoIcon, {size:36}), h('h3', null, t('noChanges')))
                : visibleFiles.map(fileRow)),
              h('div', {className:'gd-commit-box'},
                h('input', {placeholder:t('summary'), value:summary, maxLength:120, onChange:e => setSummary(e.target.value), 'aria-label':t('summary')}),
                h('textarea', {placeholder:t('description'), value:description, maxLength:4000, onChange:e => setDescription(e.target.value), 'aria-label':t('description')}),
                catalog && catalog.length === 0 && h('p', {className:'gd-small gd-muted', style:{margin:0}}, t('modelCatalogUnavailable')),
                catalog && catalog.length > 0 && selection && h('div', {className:'gd-selects'},
                  h('label', null, t('model'),
                    h('select', {value:selection.provider + '\u0000' + selection.model, onChange:e => chooseModel(e.target.value), disabled:!!busy, 'aria-label':t('model')},
                      catalog.filter(row => row.models.length).map(row =>
                        h('optgroup', {key:row.provider, label:row.name},
                          row.models.map(model => h('option', {key:model.id, value:row.provider + '\u0000' + model.id}, model.name)))))),
                  h('label', null, t('reasoning'),
                    h('select', {value:selection.reasoningEffort || '', onChange:e => chooseReasoning(e.target.value), disabled:!!busy, 'aria-label':t('reasoning')},
                      h('option', {value:''}, t('providerDefault')),
                      reasoningOptions.efforts.map(effort => h('option', {key:effort.id, value:effort.id}, effort.name))))),
                h('button', {className:'gd-group-btn', onClick:organize, disabled:!!busy || files.length === 0},
                  h(SparkIcon), busy === 'organize' ? h('span', {className:'gd-btn-busy'}, h(Spinner), organizePhase === 'committing' ? t('committing') : t('grouping')) : t('groupCommits')),
                h('div', {className:'gd-commit-count'},
                  h('span', null, checked.length, ' / ', files.length),
                  h('span', null, snapshot?.branch ? t('commitTo').replace('{n}', checked.length).replace('{branch}', snapshot.branch) : t('detached'))),
                h('button', {className:'gd-primary', disabled:!canCommit, onClick:runCommit,
                  title:canCommit ? '' : (files.some(f => f.staged) ? 'Unstage existing changes first' : '')},
                  t('commitTo').replace('{n}', checked.length).replace('{branch}', snapshot?.branch || ''))));
          }

          function historyPane() {
            return h(React.Fragment, null,
              h('div', {className:'gd-list-head'}, h('span', null, commits.length, ' commits')),
              h('div', {className:'gd-list'}, commits.length === 0
                ? h('div', {className:'gd-pad gd-muted'}, t('noHistory'))
                : commits.map(commit => h('button', {key:commit.hash, className:'gd-file', 'aria-selected':selectedCommit === commit.hash,
                    onClick:() => { setSelectedCommit(commit.hash); const known = commitFiles[commit.hash]; setSelectedCommitPath(known?.[0]?.path ?? null); }, style:{display:'block'},
                    onContextMenu:e => { e.preventDefault(); e.stopPropagation(); setCtxMenu({kind:'commit', x:Math.min(e.clientX, window.innerWidth - 230), y:Math.min(e.clientY, window.innerHeight - 170), commit}); }},
                    h('div', {style:{display:'flex', gap:'8px', alignItems:'flex-start', justifyContent:'space-between'}},
                      h('span', {style:{fontWeight:550, minWidth:0, whiteSpace:'normal', overflowWrap:'anywhere'}}, commit.title),
                      unpushed.has(commit.hash) && h('span', {className:'gd-ahead-badge', title:t('unpushed'), style:{marginLeft:'auto'}}, '↑')),
                    h('div', {className:'gd-small gd-muted'}, commit.hash.slice(0, 8), ' · ', commit.author || '', commit.date ? ' · ' + String(commit.date).slice(0, 16) : '')))));
          }

          function filesPane() {
            const isProposal = tab === 'proposal';
            const entries = isProposal
              ? (activeGroup?.paths || []).map(path => ({path, status:(files.find(f => f.path === path)?.status) || '.M'}))
              : (commitFiles[selectedCommit] || []);
            const activePath = isProposal ? proposalPath : selectedCommitPath;
            const setActive = isProposal ? setProposalPath : setSelectedCommitPath;
            return h('aside', {className:'gd-files', 'aria-label':t('files')},
              h('div', {className:'gd-list-head'}, h('span', null, entries.length, ' ', t('files'))),
              h('div', {className:'gd-list'},
                h('div', {className:'gd-file', role:'button', tabIndex:0, 'aria-selected':!activePath,
                  onClick:() => setActive(null),
                  onKeyDown:e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActive(null); } }},
                  h('span', {style:{width:'14px'}}), h('span', {className:'gd-path'}, h('span', {className:'gd-name'}, t('allFiles')))),
                entries.map(file => {
                  const [dir, name] = splitPath(file.path);
                  return h('div', {key:file.path, className:'gd-file', role:'button', tabIndex:0, 'aria-selected':activePath === file.path,
                    onClick:() => setActive(file.path),
                    onKeyDown:e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActive(file.path); } }},
                    h(StatusIcon, {status:file.status}),
                    h('span', {className:'gd-path'}, h('span', {className:'gd-dir'}, dir), h('span', {className:'gd-name'}, name)));
                })));
          }

          function proposalPane() {
            return h(React.Fragment, null,
              h('div', {className:'gd-list-head'},
                h('button', {onClick:() => { setTab('changes'); setProposal(null); setProposalPath(null); }, disabled:!!busy}, '← ' + t('backToChanges')),
                h('span', {className:'gd-small gd-muted'}, activeGroups.length, ' ', t('commits'))),
              h('div', {className:'gd-small gd-muted', style:{padding:'0 12px 6px', overflowWrap:'anywhere'}},
                t('groupedWith'), ' ', (draft?.model?.provider || '?') + '/' + (draft?.model?.model || '?'),
                ' · ', t('reasoningLevel'), ': ', draft?.reasoningEffort || 'default'),
              h('div', {className:'gd-list gd-group-list'}, activeGroups.map((group, index) =>
                h('button', {key:group.id, className:'gd-group-card', 'aria-selected':groupIndex === index, onClick:() => { setGroupIndex(index); setProposalPath(group.paths[0] ?? null); }},
                  h('div', {className:'gd-group-title'},
                    h('span', {className:'gd-num'}, index + 1),
                    h('span', {style:{overflowWrap:'anywhere'}}, group.title || 'Untitled')),
                  h('div', {className:'gd-group-meta'}, group.paths.length, ' ', t('files'))))),
              h('div', {className:'gd-commit-box'},
                h('div', {className:'gd-commit-count'}, h('span', null, activeGroups.length, ' ', t('commits'))),
                h('button', {className:'gd-primary', disabled:!!busy || affected.length === 0 && activeGroups.length === 0 || affected.length > 0, onClick:createCommits, title:affected.length > 0 ? (affected.length > 1 ? t('affectedFiles').replace('{n}', affected.length) : t('affectedFile')) : ''},
                  t('createCommits'), ` (${activeGroups.length})`)));
          }

          function proposalDetail() {
            if (!activeGroup) return h('div', {className:'gd-empty'}, h('p', null, t('proposal')));
            return h(React.Fragment, null,
              h('div', {className:'gd-pad'},
                h('input', {className:'gd-field gd-msg', value:activeGroup.title, maxLength:90, 'aria-label':t('summary'),
                  onChange:e => {
                    const groups = activeGroups.map((g, i) => i === groupIndex ? {...g, title:e.target.value} : g);
                    setProposal({...proposal, groups}); setProposalDirty(true);
                  }, disabled:!!busy}),
                h('textarea', {className:'gd-field', rows:2, value:activeGroup.body || '', maxLength:900, placeholder:t('description'), 'aria-label':t('description'),
                  onChange:e => {
                    const groups = activeGroups.map((g, i) => i === groupIndex ? {...g, body:e.target.value} : g);
                    setProposal({...proposal, groups}); setProposalDirty(true);
                  }, disabled:!!busy}),
                activeGroup.rationale && h('div', {className:'gd-reason'}, h('strong', null, t('why')), h('p', {className:'gd-muted'}, activeGroup.rationale)),
                activeGroup.warnings?.length > 0 && h('ul', {className:'gd-small gd-muted', style:{margin:'6px 0'}}, activeGroup.warnings.map((w, i) => h('li', {key:i}, typeof w === 'string' ? w : w?.message || String(w?.code)))),
                proposalDirty && h('p', {className:'gd-small gd-warn'}, t('reviewEdits'))),
              (proposalPath ? [proposalPath] : activeGroup.paths).map(path => h('details', {key:path, className:'gd-fileblock', style:{margin:'0 16px 10px'}, open:true},
                h('summary', null, path),
                h(DiffText, {data:diffs[path] || diffCache.current.get(path), wrap, split, t}))),
              draft?.warnings?.length > 0 && h('details', {className:'gd-pad gd-small'}, h('summary', null, t('warnings')),
                h('ul', null, draft.warnings.map((w, i) => h('li', {key:i, className:'gd-muted'}, typeof w === 'string' ? w : w?.message)))));
          }

          const commitDiffKey = selectedCommit ? `commit:${selectedCommit}${selectedCommitPath ? ':' + selectedCommitPath : ''}` : '';
          const diffTitle = tab === 'history'
            ? (selectedCommitPath || commits.find(c => c.hash === selectedCommit)?.title || '')
            : tab === 'proposal'
              ? (proposalPath || activeGroup?.title || '')
              : (selectedPath || '');
          const diffData = tab === 'changes' && selectedPath
            ? (diffs[selectedPath] !== undefined ? diffs[selectedPath] : diffCache.current.get(selectedPath))
            : tab === 'history' && selectedCommit
              ? (diffs[commitDiffKey] !== undefined ? diffs[commitDiffKey] : diffCache.current.get(commitDiffKey))
              : null;

          return h('section', {className:'gd', 'aria-label':t('title')},
            h('style', null, CSS),
            h('header', {className:'gd-head'},
              h('div', null,
                h('div', {className:'gd-kicker'}, t('currentRepository')),
                h('div', {className:'gd-repo'}, h(RepoIcon), h('span', {title:snapshot?.root}, repoName(snapshot?.root) || '—'))),
              h('div', {className:'gd-branch-cell'},
                h('div', {className:'gd-kicker'}, t('currentBranch')),
                h('div', {className:'gd-branchwrap', ref:branchRef},
                  h('button', {className:'gd-branchbtn', onClick:openBranchMenu, disabled:!!busy, 'aria-haspopup':'listbox', 'aria-expanded':!!branchMenu, title:t('switchBranch')},
                    h(BranchIcon), h('span', {style:{overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}, snapshot?.branch || t('detached')),
                    h('span', {className:'gd-caret', 'aria-hidden':true}, '▾'),
                    snapshot && h('span', {className:'gd-meta'}, `${snapshot.ahead || 0} ${t('ahead')} / ${snapshot.behind || 0} ${t('behind')}`)),
                  branchMenu && h('div', {className:'gd-menu', role:'listbox', 'aria-label':t('switchBranch')},
                    branchMenu.loading && h('div', {className:'gd-menu-note'}, t('loading')),
                    branchMenu.error && h('div', {className:'gd-menu-error'}, branchMenu.error),
                    !branchMenu.loading && !branchMenu.error && branchMenu.branches.length === 0 && h('div', {className:'gd-menu-note'}, t('noBranches')),
                    branchMenu.branches.map(branch => h('button', {key:branch.name, className:'gd-menu-row', role:'option', 'aria-selected':branch.name === snapshot?.branch, onClick:() => chooseBranch(branch.name)},
                      h('span', {style:{overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}, branch.name),
                      branch.name === snapshot?.branch ? h('span', {className:'gd-muted'}, '✓') : null))))),
              h('div', {className:'gd-head-actions'},
                snapshot?.ahead > 0 && snapshot?.pushTarget?.fingerprint && h('button', {className:'gd-primary', onClick:() => setModal({action:'push'}), disabled:!!busy}, t('pushOrigin'), ` (${snapshot.ahead})`),
                h('button', {onClick:refresh, disabled:!!busy}, busy === 'refresh' ? t('loading') : t('refresh')))),
            error && h('div', {className:'gd-banner gd-bad', role:'alert'}, h('span', null, error), h('button', {onClick:refresh, disabled:!!busy}, t('retry'))),
            notice && h('div', {className:'gd-banner gd-ok', role:'status'}, notice),
            busy === 'organize' && h('div', {className:'gd-banner', role:'status', 'aria-live':'polite'},
              h(Spinner, {size:15}), h('span', null, organizePhase === 'committing' ? t('committing') : t('grouping')), h('span', {className:'gd-small gd-muted'}, t('organizingHint'))),
            snapshot?.warnings?.length > 0 && h('div', {className:'gd-banner gd-warn'}, snapshot.warnings.map(w => typeof w === 'string' ? w : w.message).join(' ')),
            draft && draft.state !== 'committed' && (affected.length > 0 || draft.stale) && h('div', {className:'gd-banner gd-warn'},
              h('span', null, affected.length > 1 ? t('affectedFiles').replace('{n}', affected.length) : affected.length === 1 ? t('affectedFile') : t('stillValid')),
              busy !== 'organize' && h('button', {onClick:organize, disabled:!!busy}, t('groupAgain'))),
            h('div', {className:'gd-main'},
              h('aside', {className:'gd-side', 'aria-label':t('title')},
                !snapshot ? h('div', {className:'gd-empty'}, h('p', null, t('loading')))
                : tab === 'proposal' ? proposalPane()
                : h(React.Fragment, null,
                    h('div', {className:'gd-tabs'},
                      h('button', {className:'gd-tab', role:'tab', 'aria-selected':tab === 'changes', onClick:() => setTab('changes')}, t('changes'), ' ', files.length ? `(${files.length})` : ''),
                      h('button', {className:'gd-tab', role:'tab', 'aria-selected':tab === 'history', onClick:() => setTab('history')}, t('history'))),
                    tab === 'history' ? historyPane() : changesPane())),
              (tab === 'proposal' || tab === 'history') && filesPane(),
              h('main', {className:'gd-diff'},
                h('div', {className:'gd-diff-head'},
                  h('span', {className:'gd-diff-title'}, diffTitle || t('noDiff')),
                  diffTools()),
                h('div', {className:'gd-diff-body'},
                  tab === 'proposal' ? proposalDetail()
                  : tab === 'history'
                    ? (selectedCommit ? h(DiffText, {data:diffData, wrap, split, t}) : h('div', {className:'gd-empty'}, h('p', null, t('noHistory'))))
                    : (selectedPath ? h(DiffText, {data:diffData, wrap, split, t}) : h('div', {className:'gd-empty'}, h(RepoIcon, {size:40}), h('p', null, t('noDiff'))))))),
            ctxMenu && h('div', {className:'gd-ctx', role:'menu', style:{left:ctxMenu.x, top:ctxMenu.y}, onContextMenu:e => e.preventDefault()},
              ctxMenu.kind === 'all'
                ? [
                    h('button', {key:'stash', role:'menuitem', onClick:() => { setCtxMenu(null); setModal({action:'stash'}); }}, t('stashChanges')),
                    h('button', {key:'discard-all', role:'menuitem', onClick:() => { setCtxMenu(null); setModal({action:'discardAll'}); }}, t('discardAll')),
                  ]
                : ctxMenu.kind === 'file'
                ? [
                    h('button', {key:'relative', role:'menuitem', onClick:() => { try { navigator.clipboard?.writeText(ctxMenu.path); } catch {} setCtxMenu(null); }}, t('copyRelative')),
                    h('button', {key:'absolute', role:'menuitem', onClick:() => { try { navigator.clipboard?.writeText((snapshot?.root || '') + '/' + ctxMenu.path); } catch {} setCtxMenu(null); }}, t('copyAbsolute')),
                    h('button', {key:'discard', role:'menuitem', onClick:() => { setCtxMenu(null); setModal({action:'discard', path:ctxMenu.path}); }}, t('discardChanges')),
                  ]
                : [
                    h('button', {key:'amend', role:'menuitem', disabled:ctxMenu.commit.hash !== commits[0]?.hash,
                      title:ctxMenu.commit.hash !== commits[0]?.hash ? t('headOnly') : '',
                      onClick:() => { setAmendDraft({summary:ctxMenu.commit.title, description:ctxMenu.commit.body || ''}); setCtxMenu(null); setModal({action:'amend'}); }}, t('amendMessage')),
                    h('button', {key:'undo', role:'menuitem', disabled:ctxMenu.commit.hash !== commits[0]?.hash,
                      title:ctxMenu.commit.hash !== commits[0]?.hash ? t('headOnly') : '',
                      onClick:() => { setCtxMenu(null); setModal({action:'undo'}); }}, t('undoCommit')),
                    h('button', {key:'copy', role:'menuitem', onClick:() => { try { navigator.clipboard?.writeText(ctxMenu.commit.hash); } catch {} setCtxMenu(null); }}, t('copyHash')),
                  ]),
            modal?.action === 'stash' && h(Dialog, {
              title:t('stashTitle'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmStash, confirmLabel:t('stashChanges')
            },
              h('p', null, t('stashWarning'))),
            modal?.action === 'discardAll' && h(Dialog, {
              title:t('discardAllTitle'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmDiscardAll, confirmLabel:t('discardAll')
            },
              h('p', null, files.length, ' ', t('changedFiles')),
              h('p', {className:'gd-small'}, t('discardAllWarning'))),
            modal?.action === 'discard' && h(Dialog, {
              title:t('discardTitle'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmDiscard, confirmLabel:t('discardChanges')
            },
              h('p', null, modal.path),
              h('p', {className:'gd-small'}, t('discardWarning'))),
            modal?.action === 'undo' && h(Dialog, {
              title:t('undoTitle'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmUndo, confirmLabel:t('undoCommit')
            },
              h('p', null, `${commits[0]?.hash?.slice(0,8) || ''} · ${commits[0]?.title || ''}`),
              h('p', {className:'gd-small'}, t('undoWarning'))),
            modal?.action === 'amend' && h(Dialog, {
              title:t('amendTitle'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmAmend, confirmLabel:t('amendTitle')
            },
              h('input', {className:'gd-field', value:amendDraft.summary, maxLength:120, placeholder:t('summary'),
                onChange:e => setAmendDraft(draft => ({...draft, summary:e.target.value}))}),
              h('textarea', {className:'gd-field', rows:3, value:amendDraft.description, maxLength:4000, placeholder:t('description'),
                onChange:e => setAmendDraft(draft => ({...draft, description:e.target.value}))}),
              h('p', {className:'gd-small'}, t('amendWarning'))),
            modal?.action === 'commitSelected' && h(Dialog, {
              title:t('commitConfirm'), t, busy:false,
              onCancel:() => { setModal(null); modal.resolve?.(false); },
              onConfirm:() => { setModal(null); modal.resolve?.(true); },
              confirmLabel:t('confirm')
            },
              h('p', null, summary, ' · ', checked.length, ' ', t('files')),
              h('p', {className:'gd-small'}, snapshot?.branch)),
            modal?.action === 'checkout' && h(Dialog, {
              title:t('switchBranch'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmCheckout, confirmLabel:t('switchBranch')
            },
              h('p', null, snapshot?.branch, ' → ', modal.branch),
              h('p', {className:'gd-small'}, t('cleanRequired'))),
            modal?.action === 'push' && h(Dialog, {
              title:t('pushOrigin'), t, busy:false,
              onCancel:() => setModal(null), onConfirm:confirmPush, confirmLabel:t('pushOrigin')
            },
              h('p', null, snapshot?.branch, ' → ', snapshot?.upstream || '', ' · ', snapshot?.pushTarget?.displayUrl || ''),
              h('p', {className:'gd-small'}, t('pushNotice')))
          );
        }

        function mainSessionId(list) {
          if (!list?.byId) return undefined;
          const retained = Object.values(list.byId).find(s => (s?.retainedBy?.mainView ?? 0) > 0);
          return retained?.id || (Array.isArray(list.ids) ? list.ids[0] : undefined);
        }
        function SidebarIcon({size = 22, active}) {
          return h('svg', {width:size, height:size, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:1.6, 'aria-hidden':true, style:{opacity:active ? 1 : .85}},
            h('path', {d:'M6 4v16m0-9c0-6 12 0 12-7M11 16h9m-9 4h6'}),
            h('circle', {cx:6, cy:4, r:2, fill:'var(--dsw-specific-sidebar-fill)'}),
            h('circle', {cx:6, cy:20, r:2, fill:'var(--dsw-specific-sidebar-fill)'}),
            h('circle', {cx:18, cy:4, r:2, fill:'var(--dsw-specific-sidebar-fill)'}));
        }
        function MainPanel({useSessions}) {
          React.useSyncExternalStore(fn => ctx.locale.subscribe(fn), () => ctx.locale.getSnapshot());
          const sessionId = useSessions(mainSessionId);
          return h('div', {style:{height:'100%', boxSizing:'border-box', paddingTop:'var(--dsh-frame-top-clearance, 0px)', background:'var(--dsw-alias-bg-base)'}},
            sessionId ? h(Review, {sessionId, key:sessionId})
              : h('div', {style:{height:'100%', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'10px', color:'var(--dsw-alias-label-secondary)'}},
                  h(RepoIcon, {size:44}), h('h2', {style:{margin:0, fontSize:'17px'}}, t('title')), h('p', {style:{margin:0}}, t('noSession'))));
        }

        ctx.slots.inject('conversation.view', () => ctx.slots.register({name:'conversation.view', id:'local-git-review', order:20, label:() => t('title'), locale:'localGitReview'}, props => h(Review, {sessionId:props.sessionId, key:props.sessionId})));
        ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({name:'sidebar.panellist', id:'git-review', order:20, label:() => t('title')}, SidebarIcon));
        ctx.slots.inject('main', () => ctx.slots.register({name:'main', key:'git-review'}, MainPanel));
      }
    };
  }
});
