import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { realpath, lstat, mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createGitEngine } from './git-engine.js';
import { PLANNER_LIMITS, collectRecentSessions, organizeChanges, isSensitivePath } from './planner.js';

const exec = promisify(execFile);
const MUTATIONS = new Set(['organize', 'save', 'commit', 'commitSelected', 'stashChanges', 'discardChanges', 'undoCommit', 'amendCommit', 'push', 'checkout']);
// Grouping is a bulk file-reading task; never let it silently select an
// expensive scanning model to protect the user's credits.
const BLOCKED_MODEL = /astra/i;
const isBlockedModel = (id, name = '') => BLOCKED_MODEL.test(String(id)) || BLOCKED_MODEL.test(String(name));
export const TOOL_SCHEMA = {
  name: 'git_review',
  description: 'Review repository changes, propose related commits using diffs and recent repository sessions, and edit the proposal. Creating commits, switching branches, and pushing require separate approval. No automatic push or destructive Git operations.',
  parameters: {type:'object', properties:{
    action:{type:'string',enum:['status','diff','history','commitFiles','branches','models','modelInfo','organize','save','commit','commitSelected','stashChanges','discardChanges','undoCommit','amendCommit','push','checkout']},
    path:{type:'string',description:'Explicit non-sensitive repository-relative file for diff, including historical diffs.'},
    commit:{type:'string',description:'Commit hash to inspect instead of working changes.'},
    includeSessions:{type:'boolean',description:'Use recent sessions from this repository for organizing; defaults to true. Sends bounded excerpts and diffs to the selected model.'},
    provider:{type:'string',description:'Provider for organizing instead of the session model.'},
    model:{type:'string',description:'Model id for organizing instead of the session model.'},
    reasoningEffort:{type:'string',description:'Reasoning effort id for the grouping call.'},
    planId:{type:'string',description:'Current proposal id returned by status or organize.'},
    revision:{type:'integer',description:'Exact proposal revision for save or commit.'},
    groups:{type:'array',description:'Replacement groups for save. Omitted files remain unassigned.',items:{type:'object',properties:{id:{type:'string'},title:{type:'string'},body:{type:'string'},rationale:{type:'string'},paths:{type:'array',items:{type:'string'}}},required:['title','paths'],additionalProperties:false}},
    expectedHead:{type:'string',description:'Exact current HEAD required for push or checkout.'},
    expectedTarget:{type:'string',description:'Exact snapshot.pushTarget.fingerprint required for push; binds the reviewed upstream destination.'},
    branch:{type:'string',description:'Existing local branch for checkout; requires a clean working tree.'},
    summary:{type:'string',description:'Required one-line commit summary for commitSelected.'},
    description:{type:'string',description:'Optional commit description for commitSelected.'},
    paths:{type:'array',description:'Selected changed-file paths for commitSelected.',items:{type:'string'}}
  },required:['action'],additionalProperties:false}
};

function fail(code, message) { throw Object.assign(new Error(message), {code}); }
async function git(cwd, args) {
  const {stdout} = await exec('git', ['--no-optional-locks', '-C', cwd, ...args], {encoding:'utf8',timeout:15000,maxBuffer:1024*1024,env:{...process.env,GIT_TERMINAL_PROMPT:'0'}});
  return stdout.trim();
}
export async function resolveRoot(cwd) { return realpath(await git(cwd, ['rev-parse','--show-toplevel'])); }

/** Drafts are local to this worktree's Git directory, never tracked or pushed. */
export class DraftStore {
  async filename(root) {
    const dir = path.resolve(await git(root, ['rev-parse','--absolute-git-dir']), 'dsh-git-review');
    const info = await lstat(dir).catch(e => { if(e.code !== 'ENOENT') throw e; });
    if (info?.isSymbolicLink() || (info && !info.isDirectory())) fail('UNSAFE_STORAGE','The Git Review draft directory must be a real directory, not a link.');
    return path.join(dir,'proposal.json');
  }
  async read(root) {
    const filename = await this.filename(root);
    try {
      const info = await lstat(filename);
      if (!info.isFile() || info.isSymbolicLink() || info.size > 4*1024*1024) fail('INVALID_DRAFT','The saved proposal is not a bounded regular file.');
      const draft = JSON.parse(await readFile(filename,'utf8'));
      if (draft.version !== 1 || draft.root !== root || !Array.isArray(draft.groups)) fail('INVALID_DRAFT','The saved proposal is incompatible. Organize again.');
      return draft;
    } catch(e) { if(e.code === 'ENOENT') return null; throw e; }
  }
  async write(root, draft) {
    const filename = await this.filename(root);
    const dir = path.dirname(filename);
    await mkdir(dir,{recursive:true,mode:0o700});
    // Both resolved targets are fixed filenames within this verified owned directory.
    const target = path.resolve(filename);
    if (path.dirname(target) !== path.resolve(dir) || path.basename(target) !== 'proposal.json') fail('UNSAFE_STORAGE','Unexpected proposal destination.');
    const temporary = path.join(dir, `proposal-${randomUUID()}.tmp`);
    await writeFile(temporary,JSON.stringify(draft),{flag:'wx',mode:0o600});
    await rename(temporary,target);
  }
}

/** Both the UI command and agent tool call this one application service. */
export class GitReviewService {
  constructor({engineFactory=createGitEngine,store=new DraftStore(),collect=collectRecentSessions,organize=organizeChanges,rootResolver=resolveRoot,services,authorize=async()=>{}}) {
    Object.assign(this,{engineFactory,store,collect,organize,rootResolver,services,authorize});
    this.busy = new Set();
    this.controller = new AbortController();
  }
  dispose() { this.controller.abort(); }
  async run(agent, request, {caller='tool',signal}={}) {
    const action = request?.action;
    if (!['status','diff','history','commitFiles','branches','models','modelInfo','organize','save','commit','commitSelected','stashChanges','discardChanges','undoCommit','amendCommit','push','checkout'].includes(action)) fail('INVALID_ACTION','Unknown Git Review action.');
    const deps = this.services(agent);
    const engine = this.engineFactory({cwd:deps.cwd});
    if (action === 'diff') {
      if (!request.path && !request.commit) fail('INVALID_INPUT','Choose a changed file or commit.');
      if (caller==='tool' && (!request.path || isSensitivePath(request.path))) fail('EXCLUDED_DIFF','Model-facing diffs require an explicit non-sensitive file path. Review whole commits or sensitive files locally in the Git Review panel.');
      return engine.diff({path:request.path,commit:request.commit});
    }
    if (action === 'history') return {commits:await engine.history({limit:60})};
    if (action === 'commitFiles') {
      if (typeof request.commit !== 'string' || !request.commit) fail('INVALID_INPUT','A commit hash is required.');
      return engine.commitFiles({commit:request.commit});
    }
    if (action === 'branches') return {branches:await engine.branches()};
    if (action === 'models') {
      if (!deps.llm?.listProviders) fail('MODEL_UNAVAILABLE','The model catalog is unavailable in this session.');
      const providers = [];
      for (const provider of deps.llm.listProviders()) {
        let models = [];
        let error = null;
        try { models = (await deps.llm.listModels(provider.id)).filter(model => !isBlockedModel(model.id, model.name)).map(model => ({id:model.id,name:model.name || model.id})); }
        catch (e) { error = e.message; }
        providers.push({provider:provider.id,name:provider.name || provider.id,models,error});
      }
      return {providers,selection:deps.selection};
    }
    if (action === 'modelInfo') {
      if (!deps.llm?.resolveModelInfo) fail('MODEL_UNAVAILABLE','Model metadata is unavailable in this session.');
      if (typeof request.provider !== 'string' || !request.provider || typeof request.model !== 'string' || !request.model) fail('INVALID_INPUT','Provider and model are required.');
      const info = await deps.llm.resolveModelInfo(request.provider, request.model);
      const efforts = (info.reasoning?.efforts || []).map(effort => ({id:effort.id,name:effort.name || effort.id,description:effort.description}));
      return {provider:request.provider,model:request.model,efforts,defaultEffort:info.reasoning?.defaultEffort ?? null};
    }
    const snapshot = await engine.snapshot();
    if (MUTATIONS.has(action)) await this.authorize({agent,request,caller,root:snapshot.root,snapshot,signal});
    if (action === 'status') {
      const stored = await this.store.read(snapshot.root);
      let draft = null;
      if (stored) {
        const current = new Map(snapshot.files.map(f => [f.path, f]));
        const grouped = [...new Set(stored.groups.flatMap(g => g.paths))];
        const affectedPaths = grouped.filter(p => { const f = current.get(p); return !f || !stored.pathHashes || f.contentHash !== stored.pathHashes[p]; });
        draft = {...stored,
          stale: stored.fingerprint !== snapshot.fingerprint || stored.state === 'committed',
          affectedPaths,
          canCommit: stored.state === 'draft' && stored.head === snapshot.head && affectedPaths.length === 0};
      }
      return {snapshot,draft,busy:this.busy.has(snapshot.root),selection:deps.selection,policy:{maxGroups:PLANNER_LIMITS.maxGroups,selectiveProposals:true}};
    }
    if(this.busy.has(snapshot.root)) fail('BUSY','Another Git Review operation is running for this repository.');
    this.busy.add(snapshot.root);
    try {
      if (action === 'organize') {
        if (!snapshot.files.length) fail('NO_CHANGES','There are no working changes to organize.');
        let selection = deps.selection;
        if (request.provider !== undefined || request.model !== undefined) {
          if (typeof request.provider !== 'string' || !request.provider || typeof request.model !== 'string' || !request.model) fail('INVALID_INPUT','Provider and model are required together.');
          selection = {provider:request.provider,model:request.model,...(typeof request.reasoningEffort === 'string' && request.reasoningEffort ? {reasoningEffort:request.reasoningEffort} : {})};
        }
        if (isBlockedModel(selection?.model || '')) fail('MODEL_BLOCKED','That model is disabled for grouping to protect credits. Pick another model in the panel.');
        const planSignal = AbortSignal.any([this.controller.signal,AbortSignal.timeout(180000),...(signal?[signal]:[])]);
        let context = {sessions:[],warnings:[]};
        if (request.includeSessions !== false) {
          if (deps.sessionQuery) context = await this.collect({sessionQuery:deps.sessionQuery,root:snapshot.root,resolveRoot:this.rootResolver,signal:planSignal,limit:12});
          else context.warnings.push('Session history is unavailable; this proposal uses diffs only.');
        }
        if (!deps.llm || !selection?.provider || !selection?.model) fail('MODEL_UNAVAILABLE','Select a working model for this session before organizing changes.');
        const diffs = [];
        for (const file of snapshot.files) {
          if (file.sensitive || file.eligible===false || file.excluded || isSensitivePath(file.path) || isSensitivePath(file.originalPath || '') || file.conflict || file.submodule) continue;
          planSignal.throwIfAborted();
          diffs.push(await engine.diff({path:file.path}));
        }
        const result = await this.organize({snapshot,diffs,sessions:context.sessions,llm:deps.llm,selection,signal:planSignal});
        const current = await engine.snapshot();
        if(current.fingerprint !== snapshot.fingerprint) fail('STALE_PLAN','Files changed while organizing. Refresh and organize again; no commits were created.');
        const groups = result.groups.map((g,i)=>({...g,id:`g${i+1}`}));
        const grouped = new Set(groups.flatMap(g=>g.paths));
        const pathHashes = Object.fromEntries(snapshot.files.filter(f=>grouped.has(f.path) && f.contentHash).map(f=>[f.path,f.contentHash]));
        const draft = {version:1,id:randomUUID(),revision:1,state:'draft',root:snapshot.root,head:snapshot.head,fingerprint:snapshot.fingerprint,pathHashes,createdAt:Date.now(),model:{provider:selection.provider,model:selection.model},reasoningEffort:selection.reasoningEffort ?? null,groups,unassigned:result.unassigned||[],sourceSessions:result.sourceSessions||context.sessions.map(s=>({id:s.id,title:s.title})),warnings:[...(snapshot.warnings||[]).map(w=>typeof w==='string'?w:w.message||String(w.code)),...context.warnings,...(result.warnings||[])]};
        await this.store.write(snapshot.root,draft);
        return {draft,snapshot};
      }
      if(action === 'commitSelected') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm the selected files and message before committing.');
        const summary = typeof request.summary === 'string' ? request.summary.trim() : '';
        if(!summary || summary.length > 120 || /[\r\n\x00]/.test(summary)) fail('INVALID_INPUT','A one-line commit summary is required.');
        const description = request.description == null ? '' : request.description;
        if(typeof description !== 'string' || description.length > 4000 || description.includes('\x00')) fail('INVALID_INPUT','The commit description is invalid or too long.');
        if(!Array.isArray(request.paths) || !request.paths.length || request.paths.length > 500) fail('INVALID_INPUT','Select between 1 and 500 changed files.');
        const paths = [...new Set(request.paths)];
        if(paths.length !== request.paths.length || paths.some(p => typeof p !== 'string')) fail('INVALID_INPUT','Selected files must be unique paths.');
        const result = await engine.commitGroups({fingerprint:snapshot.fingerprint,groups:[{title:summary,body:description,paths}]});
        return result;
      }
      if(action === 'save' || action === 'commit') {
        const draft = await this.store.read(snapshot.root);
        if (!draft || draft.id !== request.planId || draft.revision !== request.revision) fail('STALE_DRAFT','The proposal was changed in another view. Refresh before continuing.');
        if(draft.state !== 'draft' || draft.head !== snapshot.head) fail('STALE_PLAN','HEAD changed after this proposal. Organize again before saving or committing.');
        if(action === 'save') {
          const groups = validateEditedGroups(request.groups,snapshot,draft);
          const assigned = new Set(groups.flatMap(g=>g.paths));
          const grouped = [...assigned];
          const pathHashes = Object.fromEntries(grouped.filter(p=>draft.pathHashes?.[p]).map(p=>[p,draft.pathHashes[p]]));
          const next = {...draft,revision:draft.revision+1,groups,pathHashes,unassigned:snapshot.files.filter(f=>!assigned.has(f.path)).map(f=>f.path)};
          await this.store.write(snapshot.root,next);
          return {draft:next,snapshot};
        }
        // The UI button itself is the deliberate action; tools use separate approval.
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm creating the commit series.');
        if (!draft.groups.length) fail('INVALID_PLAN','The proposal has no commits.');
        const verifiedGroups = validateEditedGroups(draft.groups,snapshot,draft);
        const grouped = [...new Set(verifiedGroups.flatMap(g=>g.paths))];
        if (grouped.some(p => !draft.pathHashes?.[p])) fail('STALE_PLAN','The proposal lacks reviewed file hashes. Organize again before committing.');
        const pathHashes = Object.fromEntries(grouped.map(p => [p, draft.pathHashes[p]]));
        const result = await engine.commitGroups({fingerprint:draft.fingerprint,groups:verifiedGroups,expectedHead:draft.head,pathHashes});
        const saved = {...draft,state:'committed',revision:draft.revision+1,result,committedAt:Date.now()};
        try { await this.store.write(snapshot.root,saved); }
        catch { return {...result,warning:'Commits were created, but saving the review receipt failed. Refresh history; do not retry blindly.'}; }
        return result;
      }
      if(action === 'stashChanges') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm stashing all changes.');
        return engine.stashChanges({message:request.message});
      }
      if(action === 'discardChanges') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm discarding the selected changes.');
        if(!Array.isArray(request.paths)) fail('INVALID_INPUT','Selected paths are required.');
        return engine.discardChanges({paths:request.paths});
      }
      if(action === 'undoCommit') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm undoing the latest commit.');
        return engine.undoLastCommit({expectedHead:request.expectedHead});
      }
      if(action === 'amendCommit') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm amending the latest commit.');
        return engine.amendMessage({expectedHead:request.expectedHead, summary:request.summary, body:request.description ?? ''});
      }
      if(action === 'push') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm the branch and upstream before pushing.');
        return engine.push({expectedHead:request.expectedHead,expectedTarget:request.expectedTarget});
      }
      if(action === 'checkout') {
        if(caller === 'ui' && request.confirmed !== true) fail('CONFIRM_REQUIRED','Confirm switching branches.');
        return engine.checkout({branch:request.branch,expectedHead:request.expectedHead});
      }
    } finally {this.busy.delete(snapshot.root);}
  }
}

export function validateEditedGroups(groups,snapshot,draft) {
  if(!Array.isArray(groups) || groups.length > 30) fail('INVALID_PLAN','Supply at most 30 nonempty groups.');
  const files = new Map(snapshot.files.map(f=>[f.path,f]));
  const seen = new Set();
  const ids = new Set();
  return groups.map((g,i)=>{
    if(!g || typeof g.title !== 'string' || !g.title.trim() || g.title.length > 200 || /[\r\n\x00]/.test(g.title) || !Array.isArray(g.paths) || !g.paths.length) fail('INVALID_PLAN','Each group needs a one-line title and at least one file.');
    if(g.body != null && (typeof g.body !== 'string' || g.body.length > 12000 || g.body.includes('\x00'))) fail('INVALID_PLAN','Commit body is invalid or too long.');
    for(const p of g.paths) {
      const f=files.get(p);
      if(!f || f.sensitive || f.eligible===false || f.excluded || seen.has(p) || isSensitivePath(p) || isSensitivePath(f.originalPath||'') || f.conflict || f.submodule) fail('INVALID_PLAN','A file is duplicated, excluded, or no longer eligible.');
      seen.add(p);
    }
    const previous=draft.groups.find(old=>old.id===g.id);
    const id=previous?.id || `custom-${i+1}`;
    if(ids.has(id)) fail('INVALID_PLAN','Group identifiers must be unique.');
    ids.add(id);
    return {id,title:g.title.trim(),body:g.body||'',rationale:typeof g.rationale==='string'?g.rationale.slice(0,4000):previous?.rationale||'',paths:[...g.paths],sessionIds:previous?.sessionIds||[],warnings:previous?.warnings||[]};
  });
}
