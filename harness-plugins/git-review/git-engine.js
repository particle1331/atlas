/**
 * Read-only review plus explicitly requested, conservative Git mutations.
 * No shell, packages, hooks, filters, credential helpers, or automatic actions.
 *
 * Group commits are whole-file units. Existing staging must first be removed.
 * A private copy of the real index builds an orphan commit series; only after a
 * second content fingerprint check does one compare-and-swap advance the branch.
 * The real index is held locked throughout. A post-CAS failure retains recovery
 * material and the index lock instead of pretending the operation was atomic.
 */
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import * as fs from 'node:fs/promises';
import { constants, createReadStream } from 'node:fs';
import path from 'node:path';

const PROCESS_TIMEOUT = 15_000;
const PUSH_TIMEOUT = 30_000;
const PROCESS_LIMIT = 8 * 1024 * 1024;
const DIFF_BYTES = 256 * 1024;
const DIFF_LINES = 4_000;
const MAX_DIRTY_FILES = 10_000;
const MAX_FINGERPRINT_BYTES = 256 * 1024 * 1024;
const HASH = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;
const SAFE_REV = /^[a-f0-9]{7,64}$/i;
const STATES = ['MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer', 'BISECT_LOG'];

export class GitEngineError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'GitEngineError';
    this.code = code;
    Object.assign(this, details);
  }
}

const fail = (code, message, details) => { throw new GitEngineError(code, message, details); };
const exists = async (file) => {
  try { await fs.lstat(file); return true; }
  catch (error) { if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false; throw error; }
};
const optionalRead = async (file) => {
  try { return await fs.readFile(file); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
};
const field = (hash, value) => {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(String(value));
  hash.update(String(bytes.length)); hash.update(':'); hash.update(bytes);
};
const sensitivePath = (name) => /(?:^|\/)(?:\.env(?:\.[^/]*)?|\.ssh|\.aws|\.gnupg|\.netrc|\.npmrc|\.pypirc|credentials(?:\.[^/]*)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.[^/]*)?|[^/]*\.(?:pem|key|p12|pfx)|(?:service[-_]?account|secrets?)(?:[._-][^/]*)?)(?:\/|$)/i.test(name);

function validPath(name) {
  if (typeof name !== 'string' || !name || name.includes('\0') || name.includes('\\') || path.posix.isAbsolute(name)
      || name.split('/').some((part) => !part || part === '.' || part === '..' || part.toLowerCase() === '.git')
      || Buffer.byteLength(name) > 16_384 || !Buffer.from(name).equals(Buffer.from(name, 'utf8')) || /[\uD800-\uDFFF]/u.test(name)) {
    fail('UNSAFE_PATH', 'A repository-relative, non-traversing file path is required.');
  }
  return name;
}

function parseStatus(output) {
  const parts = output.toString('utf8').split('\0');
  // Never silently alias two invalid UTF-8 names.
  if (!Buffer.from(parts.join('\0')).equals(output)) fail('UNSUPPORTED_PATH_ENCODING', 'Non-UTF-8 repository paths are not supported.');
  const files = [];
  for (let i = 0; i < parts.length; i++) {
    const entry = parts[i];
    if (!entry) continue;
    if (entry.startsWith('? ')) {
      const name = validPath(entry.slice(2));
      files.push({ path: name, status: '??', staged: false, unstaged: true, untracked: true, sensitive: sensitivePath(name) });
      continue;
    }
    let match;
    if (entry.startsWith('1 ')) match = /^1 (\S{2}) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) ([\s\S]*)$/.exec(entry);
    else if (entry.startsWith('2 ')) match = /^2 (\S{2}) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) \S+ ([\s\S]*)$/.exec(entry);
    else if (entry.startsWith('u ')) {
      const unmerged = /^u (\S{2}) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) ([\s\S]*)$/.exec(entry);
      if (!unmerged) fail('BAD_STATUS', 'Git returned an unsupported status record.');
      const name = validPath(unmerged[10]);
      files.push({ path: name, status: unmerged[1], staged: true, unstaged: true, conflict: true,
        submodule: unmerged[2] !== 'N...', sensitive: sensitivePath(name) });
      continue;
    } else fail('BAD_STATUS', 'Git returned an unsupported status record.');
    if (!match) fail('BAD_STATUS', 'Git returned an unsupported status record.');
    const name = validPath(match[8]);
    const file = { path: name, status: match[1], staged: match[1][0] !== '.', unstaged: match[1][1] !== '.',
      submodule: match[2] !== 'N...' || match[3] === '160000' || match[4] === '160000',
      sensitive: sensitivePath(name) };
    if (entry.startsWith('2 ')) {
      file.originalPath = validPath(parts[++i]);
      file.sensitive ||= sensitivePath(file.originalPath);
    }
    files.push(file);
  }
  return files.sort((a, b) => Buffer.compare(Buffer.from(a.path), Buffer.from(b.path)));
}

/** All subprocess output, including stderr, stays private on failures. */
function runGit(cwd, args, { input, env = {}, timeout = PROCESS_TIMEOUT, maxBytes = PROCESS_LIMIT, truncate = false, allowed = [0] } = {}) {
  return new Promise((resolve, reject) => {
    const childEnv = { ...process.env };
    for (const key of Object.keys(childEnv)) if (key.startsWith('GIT_')) delete childEnv[key];
    Object.assign(childEnv, { LC_ALL: 'C', LANG: 'C', GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'never',
      GIT_OPTIONAL_LOCKS: '0', GIT_LITERAL_PATHSPECS: '1', ...env });
    const child = spawn('git', ['-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false', ...args], {
      cwd, env: childEnv, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, shell: false,
      detached: process.platform !== 'win32',
    });
    let size = 0, stderrSize = 0, timedOut = false, overflow = false, spawnFailed = false;
    const chunks = [];
    const kill = () => {
      try {
        if (process.platform !== 'win32' && child.pid) process.kill(-child.pid, 'SIGKILL');
        else child.kill('SIGKILL');
      } catch { child.kill('SIGKILL'); }
    };
    const timer = setTimeout(() => { timedOut = true; kill(); }, timeout);
    child.stdout.on('data', (chunk) => {
      const remaining = Math.max(0, maxBytes - size);
      if (remaining) chunks.push(chunk.subarray(0, remaining));
      size += chunk.length;
      if (size > maxBytes) { overflow = true; kill(); }
    });
    child.stderr.on('data', (chunk) => {
      stderrSize += chunk.length;
      if (stderrSize > PROCESS_LIMIT) { overflow = true; kill(); }
    });
    child.on('error', () => { spawnFailed = true; });
    child.stdin.on('error', () => {}); // Early exit may close stdin; close determines the result.
    child.on('close', (code) => {
      clearTimeout(timer);
      if (spawnFailed) return reject(new GitEngineError('GIT_UNAVAILABLE', 'Git could not be started.'));
      if (timedOut) return reject(new GitEngineError('GIT_TIMEOUT', 'Git exceeded the operation time limit.', { mayHaveSucceeded: true }));
      if (overflow && !truncate) return reject(new GitEngineError('GIT_OUTPUT_LIMIT', 'Git output exceeded the safety limit.'));
      if (!overflow && !allowed.includes(code)) return reject(new GitEngineError('GIT_FAILED', 'Git refused the operation.', { exitCode: code }));
      resolve({ stdout: Buffer.concat(chunks), truncated: overflow, exitCode: code });
    });
    child.stdin.end(input);
  });
}

export class GitEngine {
  constructor({ cwd } = {}) {
    if (typeof cwd !== 'string' || !cwd) fail('INVALID_CWD', 'An explicit repository directory is required.');
    this.cwd = path.resolve(cwd);
    this._queue = Promise.resolve();
  }

  async _git(repo, args, options) { return runGit(repo.root, args, options); }
  async _text(repo, args, options) { return (await this._git(repo, args, options)).stdout.toString('utf8').trim(); }
  async _optionalText(repo, args) {
    try { return await this._text(repo, args); }
    catch (error) { if (error.code === 'GIT_FAILED' && [1, 128].includes(error.exitCode)) return null; throw error; }
  }
  async _repo() {
    const provisional = { root: this.cwd };
    let root;
    try { root = await this._text(provisional, ['rev-parse', '--show-toplevel']); }
    catch (error) { if (error.code === 'GIT_FAILED') fail('NOT_REPOSITORY', 'The selected directory is not a working-tree Git repository.'); throw error; }
    root = await fs.realpath(root);
    const repo = { root };
    repo.gitDir = await this._text(repo, ['rev-parse', '--absolute-git-dir']);
    repo.index = await this._gitPath(repo, 'index');
    return repo;
  }
  async _gitPath(repo, name) {
    return path.resolve(repo.root, await this._text(repo, ['rev-parse', '--git-path', name]));
  }
  async _head(repo) {
    const head = await this._optionalText(repo, ['rev-parse', '--verify', 'HEAD']);
    if (head && !HASH.test(head)) fail('BAD_HEAD', 'Git returned an invalid HEAD.');
    return head;
  }
  async _branch(repo) {
    return this._optionalText(repo, ['symbolic-ref', '--quiet', '--short', 'HEAD']);
  }
  async _states(repo) {
    const states = [];
    for (const state of STATES) if (await exists(await this._gitPath(repo, state))) states.push(state);
    return states;
  }

  async _safeDiskPath(repo, name) {
    validPath(name);
    const parts = name.split('/');
    for (let i = 1; i < parts.length; i++) {
      try {
        const info = await fs.lstat(path.join(repo.root, ...parts.slice(0, i)));
        if (info.isSymbolicLink() || !info.isDirectory()) fail('UNSAFE_PATH', 'A file has an unsafe parent directory.');
      } catch (error) { if (error.code === 'ENOENT') break; throw error; }
    }
    return path.join(repo.root, ...parts);
  }

  async _hashDisk(repo, name, hash, budget, metadata = null) {
    if (++budget.entries > MAX_DIRTY_FILES) fail('FINGERPRINT_LIMIT', 'Too many dirty files for a safe content snapshot.');
    const target = await this._safeDiskPath(repo, name);
    field(hash, name);
    const own = createHash('sha256');
    const ownField = (value) => field(own, value);
    ownField(name);
    let info;
    try { info = await fs.lstat(target, { bigint: true }); }
    catch (error) {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
        field(hash, 'missing'); ownField('missing');
        if (metadata) metadata.contentHash = own.digest('hex');
        return;
      }
      throw error;
    }
    field(hash, String(info.mode)); ownField(String(info.mode));
    if (info.isSymbolicLink()) {
      field(hash, 'symlink'); ownField('symlink');
      const link = await fs.readlink(target, { encoding: 'buffer' });
      field(hash, link); ownField(link); budget.bytes += link.length;
      if (metadata) { metadata.symlink = true; metadata.binary = false; metadata.contentHash = own.digest('hex'); }
    } else if (info.isFile()) {
      field(hash, 'file'); field(hash, String(info.size)); ownField('file'); ownField(String(info.size));
      if (budget.bytes + Number(info.size) > MAX_FINGERPRINT_BYTES) fail('FINGERPRINT_LIMIT', 'Dirty file contents exceed the fingerprint safety limit.');
      let binary = false, newlineCount = 0, lastByte = null, bytes = 0;
      const contentHash = createHash('sha256');
      // O_NOFOLLOW closes the usual lstat/open symlink race on POSIX.
      const handle = await fs.open(target, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
      try {
        const opened = await handle.stat({ bigint: true });
        if (!opened.isFile() || opened.ino !== info.ino || opened.dev !== info.dev) fail('SNAPSHOT_CHANGED', 'A file changed while its content was being read.');
        for await (const chunk of createReadStream(target, { fd: handle.fd, autoClose: false })) {
          budget.bytes += chunk.length; bytes += chunk.length;
          if (budget.bytes > MAX_FINGERPRINT_BYTES) fail('FINGERPRINT_LIMIT', 'Dirty file contents exceed the fingerprint safety limit.');
          contentHash.update(chunk);
          if (chunk.includes(0)) binary = true;
          for (const byte of chunk) if (byte === 10) newlineCount++;
          if (chunk.length) lastByte = chunk[chunk.length - 1];
        }
        const after = await handle.stat({ bigint: true });
        if (after.size !== opened.size || after.mtimeNs !== opened.mtimeNs || after.ctimeNs !== opened.ctimeNs || bytes !== Number(opened.size)) {
          fail('SNAPSHOT_CHANGED', 'A file changed while its content was being read.');
        }
      } finally { await handle.close(); }
      const contentDigest = contentHash.digest();
      field(hash, contentDigest); ownField(contentDigest);
      if (metadata) {
        metadata.contentHash = own.digest('hex');
        metadata.binary = binary;
        if (metadata.untracked && !binary) { metadata.additions = newlineCount + (lastByte !== null && lastByte !== 10 ? 1 : 0); metadata.deletions = 0; }
      }
    } else if (info.isDirectory()) {
      if (!metadata?.submodule) fail('UNSAFE_FILE_TYPE', 'A dirty path unexpectedly refers to a directory.');
      field(hash, 'submodule-directory'); ownField('submodule-directory');
      // Never follow the submodule's .git indirection or symlinks. Contents are
      // hashed for staleness, but group commits of dirty submodules are refused.
      const walk = async (relative) => {
        const entries = await fs.readdir(path.join(repo.root, relative), { withFileTypes: true });
        entries.sort((a, b) => Buffer.compare(Buffer.from(a.name), Buffer.from(b.name)));
        for (const entry of entries) {
          if (entry.name === '.git') continue;
          const child = `${relative}/${entry.name}`;
          if (entry.isDirectory()) {
            if (++budget.entries > MAX_DIRTY_FILES) fail('FINGERPRINT_LIMIT', 'Too many submodule files for a safe snapshot.');
            field(hash, child); field(hash, String((await fs.lstat(path.join(repo.root, child))).mode));
            await walk(child);
          } else await this._hashDisk(repo, child, hash, budget);
        }
      };
      await walk(name);
      const subHead = await this._optionalText({ root: target }, ['rev-parse', '--verify', 'HEAD']);
      field(hash, subHead ?? 'unborn-submodule'); ownField(subHead ?? 'unborn-submodule');
      if (metadata) metadata.contentHash = own.digest('hex');
    } else fail('UNSAFE_FILE_TYPE', 'Special files cannot be safely reviewed.');
    if (budget.bytes > MAX_FINGERPRINT_BYTES) fail('FINGERPRINT_LIMIT', 'Dirty file contents exceed the fingerprint safety limit.');
  }

  async _pushTarget(repo, branch, { includeUrls = false } = {}) {
    if (!branch) return null;
    const remote = await this._optionalText(repo, ['config', '--get', `branch.${branch}.remote`]);
    const ref = await this._optionalText(repo, ['config', '--get-all', `branch.${branch}.merge`]);
    if (!remote || remote === '.' || remote.startsWith('-') || /[\s\0]/.test(remote) || !ref || ref.includes('\n')) return null;
    const rawUrls = await this._optionalText(repo, ['remote', 'get-url', '--push', '--all', remote]);
    if (!rawUrls) return null;
    const urls = rawUrls.split('\n');
    let displayUrl = '(multiple destinations)';
    if (urls.length === 1) {
      const url = urls[0];
      if (/^(?:https|ssh|file):\/\//.test(url)) {
        try {
          const parsed = new URL(url);
          parsed.username = ''; parsed.password = ''; parsed.search = ''; parsed.hash = '';
          displayUrl = parsed.href;
        } catch { displayUrl = '(invalid destination)'; }
      } else if (/^(?:[^@/:]+@)?[a-zA-Z0-9.-]+:[a-zA-Z0-9_./~@+-]+$/.test(url)) displayUrl = url.replace(/^[^@/:]+@/, '');
      else if (!url.includes(':') && !/[\0\r\n]/.test(url)) displayUrl = url;
      else displayUrl = '(unsupported destination)';
    }
    const config = (await this._git(repo, ['config', '--null', '--list', '--includes'])).stdout;
    const hash = createHash('sha256');
    for (const value of [branch, remote, ref, rawUrls, config]) field(hash, value);
    for (const key of Object.keys(process.env).filter((name) => name.startsWith('GIT_SSH')).sort()) { field(hash, key); field(hash, process.env[key]); }
    return { remote, ref, displayUrl, fingerprint: hash.digest('hex'), ...(includeUrls ? { urls } : {}) };
  }

  async _assertReviewSafety(repo, visited = new Set()) {
    const canonical = await fs.realpath(repo.root);
    if (visited.has(canonical)) return;
    if (visited.size >= 100) fail('SUBMODULE_LIMIT', 'Too many nested submodules for a safe review.');
    visited.add(canonical);
    await this._assertNoFilters(repo);
    const entries = (await this._git(repo, ['ls-files', '--stage', '-z'])).stdout.toString('utf8').split('\0');
    for (const entry of entries) {
      const match = /^160000 [a-f0-9]+ 0\t([\s\S]*)$/.exec(entry);
      if (!match) continue;
      const target = await this._safeDiskPath(repo, validPath(match[1]));
      const info = await fs.lstat(target).catch((error) => { if (error.code === 'ENOENT') return null; throw error; });
      if (info?.isDirectory() && await exists(path.join(target, '.git'))) await this._assertReviewSafety({ root: target }, visited);
    }
  }

  async _snapshot(repo) {
    // Even status (including recursive submodule status) may execute a filter.
    await this._assertReviewSafety(repo);
    const head = await this._head(repo);
    const branch = await this._branch(repo);
    const upstream = head ? await this._optionalText(repo, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}']) : null;
    let ahead = 0, behind = 0;
    if (upstream) {
      const counts = await this._text(repo, ['rev-list', '--left-right', '--count', 'HEAD...@{upstream}']);
      [ahead, behind] = counts.split(/\s+/).map(Number);
    }
    const status = (await this._git(repo, ['status', '--porcelain=v2', '-z', '--untracked-files=all', '--ignore-submodules=none'])).stdout;
    const files = parseStatus(status);
    if (files.length > MAX_DIRTY_FILES) fail('FINGERPRINT_LIMIT', 'Too many dirty files for a safe content snapshot.');
    const states = await this._states(repo);
    const index = await optionalRead(repo.index);
    const hash = createHash('sha256');
    field(hash, 'harness-git-review-v1'); field(hash, repo.root); field(hash, branch ?? 'detached'); field(hash, head ?? 'unborn');
    field(hash, index === null ? 'absent-index' : 'index'); if (index) field(hash, index);
    field(hash, status); field(hash, JSON.stringify(states));
    // Split-index backing bytes are part of the actual index's contents too.
    const shared = await this._optionalText(repo, ['rev-parse', '--shared-index-path']);
    if (shared) field(hash, await fs.readFile(path.resolve(repo.root, shared)));
    const budget = { bytes: 0, entries: 0 };
    for (const file of files) {
      await this._hashDisk(repo, file.path, hash, budget, file);
      if (file.originalPath) await this._hashDisk(repo, file.originalPath, hash, budget);
    }
    // assume-unchanged/skip-worktree may hide physically modified tracked files
    // from status. Hash those contents too, without clearing any index flags.
    const flaggedOutput = (await this._git(repo, ['ls-files', '-v', '-z'])).stdout;
    const flaggedText = flaggedOutput.toString('utf8');
    if (!Buffer.from(flaggedText).equals(flaggedOutput)) fail('UNSUPPORTED_PATH_ENCODING', 'Non-UTF-8 repository paths are not supported.');
    const flaggedPaths = flaggedText.split('\0').filter((entry) => /^[a-zS] /.test(entry)).map((entry) => validPath(entry.slice(2)));
    for (const name of flaggedPaths) {
      field(hash, `flagged:${name}`);
      if (!files.some((file) => file.path === name || file.originalPath === name)) {
        const entry = await this._text(repo, ['ls-files', '--stage', '--', name]);
        await this._hashDisk(repo, name, hash, budget, { submodule: entry.startsWith('160000 ') });
      }
    }
    if (head && files.some((file) => !file.untracked)) {
      const stats = (await this._git(repo, ['diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--numstat', '-z', head, '--'])).stdout.toString('utf8');
      const byPath = new Map(files.map((file) => [file.path, file]));
      for (const line of stats.split('\0')) {
        const match = /^(\d+|-)\t(\d+|-)\t([\s\S]*)$/.exec(line);
        const file = match && byPath.get(match[3]);
        if (!file) continue;
        if (match[1] === '-') file.binary = true;
        else { file.additions = Number(match[1]); file.deletions = Number(match[2]); }
      }
    }
    // A snapshot is observational: never return one assembled across an index,
    // branch, or status transition. Callers can retry on SNAPSHOT_CHANGED.
    const finalIndex = await optionalRead(repo.index);
    const finalStatus = (await this._git(repo, ['status', '--porcelain=v2', '-z', '--untracked-files=all', '--ignore-submodules=none'])).stdout;
    if (head !== await this._head(repo) || branch !== await this._branch(repo)
        || !status.equals(finalStatus) || (index === null) !== (finalIndex === null)
        || (index && !index.equals(finalIndex))) fail('SNAPSHOT_CHANGED', 'The repository changed while the snapshot was being read.');
    const warnings = [];
    const blockedReasons = [];
    if (!branch) blockedReasons.push('DETACHED_HEAD');
    if (states.length) blockedReasons.push('OPERATION_IN_PROGRESS');
    if (files.some((file) => file.conflict)) blockedReasons.push('CONFLICTS');
    if (files.some((file) => file.staged)) blockedReasons.push('STAGED_CHANGES');
    if (files.some((file) => file.submodule)) blockedReasons.push('SUBMODULES');
    for (const code of blockedReasons) warnings.push({ code, message: {
      DETACHED_HEAD: 'Group commits require a named branch.', OPERATION_IN_PROGRESS: 'Finish the current Git operation before committing.',
      CONFLICTS: 'Resolve conflicts before committing.', STAGED_CHANGES: 'Unstage all existing staged changes before using group commits.',
      SUBMODULES: 'Dirty submodules cannot be committed by this engine.',
    }[code] });
    if (files.some((file) => file.sensitive)) warnings.push({ code: 'SENSITIVE_PATHS', message: 'Credential and environment files cannot be assigned to commit groups.' });
    if (flaggedPaths.length) warnings.push({ code: 'INDEX_FLAGS', message: 'Some index flags hide files from ordinary Git status. Their contents are still fingerprinted; clear those flags manually before assigning such files.' });
    const pushTarget = await this._pushTarget(repo, branch);
    return { root: repo.root, branch, head, upstream, ahead, behind, files, states, warnings, pushTarget,
      fingerprint: hash.digest('hex'), canCommit: blockedReasons.length === 0 && files.length > 0, blockedReasons };
  }

  async snapshot() {
    try { return await this._snapshot(await this._repo()); }
    catch (error) { throw this._publicError(error); }
  }

  async diff({ path: name, commit } = {}) {
    try {
      const repo = await this._repo();
      if (name !== undefined) validPath(name);
      if (!commit && name === undefined) fail('INVALID_PATH', 'Choose a file for a working-tree diff.');
      let binary = false, parts = [], truncated = false;
      const base = ['--no-ext-diff', '--no-textconv', '--no-color', '--no-renames', '--patch', '--full-index'];
      const capture = async (args, options = {}) => {
        const result = await this._git(repo, args, { maxBytes: DIFF_BYTES, truncate: true, ...options });
        truncated ||= result.truncated;
        return result.stdout.toString('utf8');
      };
      if (commit) {
        if (typeof commit !== 'string' || !SAFE_REV.test(commit)) fail('INVALID_COMMIT', 'A hexadecimal commit identifier is required.');
        commit = await this._text(repo, ['rev-parse', '--verify', '--end-of-options', `${commit}^{commit}`]);
        parts.push(await capture(['show', '--no-show-signature', '--format=', ...base, commit, '--', ...(name === undefined ? [] : [name])]));
      } else {
        const snapshot = await this._snapshot(repo);
        const file = snapshot.files.find((item) => item.path === name);
        if (!file) fail('UNKNOWN_PATH', 'The selected file is not dirty.');
        binary = Boolean(file.binary);
        const names = [name, ...(file.originalPath ? [file.originalPath] : [])];
        if (file.untracked) {
          await this._safeDiskPath(repo, name);
          parts.push(await capture(['diff', '--no-index', ...base, '--', '/dev/null', name], { allowed: [0, 1] }));
        } else {
          const staged = await capture(['diff', '--cached', ...base, '--', ...names]);
          const unstaged = await capture(['diff', ...base, '--', ...names]);
          if (staged) parts.push(`--- Staged changes ---\n${staged}`);
          if (unstaged) parts.push(`--- Unstaged changes ---\n${unstaged}`);
        }
      }
      let text = parts.join('\n');
      binary ||= /(?:^|\n)Binary files .* differ(?:\n|$)/.test(text);
      if (text.includes('\0')) {
        binary = true;
        text = 'Binary files changed; binary content is not displayed. Select individual text files for a readable review.\n';
      }
      const bytes = Buffer.from(text);
      if (bytes.length > DIFF_BYTES) { text = bytes.subarray(0, DIFF_BYTES).toString('utf8'); truncated = true; }
      const lines = text.split('\n');
      if (lines.length > DIFF_LINES) { text = lines.slice(0, DIFF_LINES).join('\n'); truncated = true; }
      if (truncated) text += '\n[Diff truncated: review the complete change with Git before approval.]\n';
      if (binary && !text) text = 'Binary file change; content is not displayed.\n';
      return { ...(name === undefined ? {} : { path: name }), ...(commit ? { commit } : {}), text, binary, truncated,
        limits: { maxBytes: DIFF_BYTES, maxLines: DIFF_LINES }, summary: binary ? 'Binary change: inspect with an appropriate local viewer.' : undefined };
    } catch (error) { throw this._publicError(error); }
  }

  async history({ limit = 30 } = {}) {
    try {
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) fail('INVALID_LIMIT', 'History limit must be between 1 and 100.');
      const repo = await this._repo();
      if (!await this._head(repo)) return [];
      const raw = (await this._git(repo, ['log', '--no-show-signature', `-${limit}`, '-z', '--format=%H%x00%P%x00%an%x00%aI%x00%s%x00%b'], { maxBytes: 2 * 1024 * 1024 })).stdout.toString('utf8');
      const fields = raw.split('\0');
      if (fields.at(-1) === '') fields.pop();
      const commits = [];
      for (let i = 0; i < fields.length; i += 6) {
        if (!HASH.test(fields[i]) || fields[i + 5] === undefined) fail('BAD_HISTORY', 'Git returned unsupported history data.');
        commits.push({ hash: fields[i], parents: fields[i + 1].split(' ').filter(Boolean), author: fields[i + 2],
          date: fields[i + 3], title: fields[i + 4], body: fields[i + 5].trimEnd() });
      }
      return commits;
    } catch (error) { throw this._publicError(error); }
  }

  async commitFiles({ commit } = {}) {
    try {
      if (typeof commit !== 'string' || !SAFE_REV.test(commit)) fail('INVALID_COMMIT', 'A hexadecimal commit identifier is required.');
      const repo = await this._repo();
      const resolved = await this._text(repo, ['rev-parse', '--verify', '--end-of-options', `${commit}^{commit}`]);
      const raw = (await this._git(repo, ['show', '--no-show-signature', '--no-ext-diff', '--no-textconv', '--format=', '--name-status', '-z', '--no-renames', resolved, '--'], { maxBytes: 8 * 1024 * 1024 })).stdout.toString('utf8');
      const parts = raw.split('\0').filter(Boolean);
      const files = [];
      for (let i = 0; i + 1 < parts.length; i += 2) {
        const status = parts[i];
        const pathName = parts[i + 1];
        if (!/^[A-Z][0-9]*$/.test(status) || typeof pathName !== 'string' || !pathName) continue;
        files.push({ path: pathName, status: status[0] });
      }
      return { commit: resolved, files };
    } catch (error) { throw this._publicError(error); }
  }

  async stashChanges({ message } = {}) {
    return this._exclusive(async () => {
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      if (!snapshot.files.length) fail('NO_CHANGES', 'There are no changes to stash.');
      if (snapshot.states.length) fail('OPERATION_IN_PROGRESS', 'Finish the current Git operation before stashing.');
      if (snapshot.files.some((file) => file.conflict)) fail('CONFLICTS', 'Resolve conflicts before stashing.');
      if (snapshot.files.some((file) => file.submodule)) fail('SUBMODULES', 'Submodule changes cannot be stashed here.');
      const label = typeof message === 'string' && message.trim() ? message.trim().slice(0, 200) : `Git Review ${new Date().toISOString()}`;
      await this._git(repo, ['stash', 'push', '--include-untracked', `--message=${label}`], { env: { GIT_LITERAL_PATHSPECS: '0' } });
      return { stashed: true, message: label, head: snapshot.head };
    });
  }

  async discardChanges({ paths } = {}) {
    if (!Array.isArray(paths) || !paths.length || paths.length > 500) fail('INVALID_PATHS', 'Choose between 1 and 500 changed files.');
    const unique = [...new Set(paths)];
    if (unique.length !== paths.length) fail('INVALID_PATHS', 'Discard targets must be unique paths.');
    return this._exclusive(async () => {
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      const byPath = new Map(snapshot.files.map((file) => [file.path, file]));
      const tracked = [];
      const untracked = [];
      for (const name of unique) {
        validPath(name);
        const file = byPath.get(name);
        if (!file) fail('UNKNOWN_PATH', 'A discard target is no longer changed.');
        if (file.conflict) fail('CONFLICTS', 'Resolve conflicts instead of discarding them.');
        if (file.submodule) fail('SUBMODULES', 'Submodule changes cannot be discarded here.');
        if (file.staged) fail('STAGED_CHANGES', 'Unstage the selection before discarding it.');
        if (file.untracked) untracked.push(name);
        else tracked.push(name, ...(file.originalPath ? [file.originalPath] : []));
      }
      if (tracked.length) {
        await this._git(repo, ['restore', '--worktree', '--no-overlay', '--source=HEAD', '--', ...tracked]);
      }
      for (const name of untracked) {
        const target = await this._safeDiskPath(repo, name);
        const info = await fs.lstat(target).catch((error) => { if (error.code === 'ENOENT') return null; throw error; });
        if (!info) continue;
        if (!info.isFile() && !info.isSymbolicLink()) fail('UNSAFE_FILE_TYPE', 'Only untracked files can be discarded.');
        await fs.unlink(target);
      }
      return { discarded: unique, head: snapshot.head };
    });
  }

  async undoLastCommit({ expectedHead } = {}) {
    return this._exclusive(async () => {
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      this._validateExpected(expectedHead, snapshot.head);
      if (!snapshot.branch) fail('DETACHED_HEAD', 'Undo requires a named branch.');
      if (snapshot.states.length) fail('OPERATION_IN_PROGRESS', 'Finish the current Git operation before undoing a commit.');
      if (snapshot.files.some((file) => file.staged)) fail('STAGED_CHANGES', 'Unstage changes before undoing a commit.');
      const parents = (await this._text(repo, ['rev-list', '--parents', '-n', '1', snapshot.head])).split(' ').slice(1).filter(Boolean);
      if (parents.length !== 1) fail('UNSUPPORTED_COMMIT', 'Only a single-parent commit can be undone.');
      const upstream = await this._optionalText(repo, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}']);
      if (upstream) {
        const contained = await this._git(repo, ['merge-base', '--is-ancestor', snapshot.head, upstream], { allowed: [0, 1] });
        if (contained.exitCode === 0) fail('ALREADY_PUSHED', 'The latest commit is already on the upstream; refusing to rewrite published history.');
      }
      await this._git(repo, ['reset', '--mixed', parents[0]]);
      return { previousHead: snapshot.head, head: await this._head(repo), undone: true };
    });
  }

  async amendMessage({ expectedHead, summary, body = '' } = {}) {
    if (typeof summary !== 'string' || !summary.trim() || summary.length > 500 || /[\r\n\0]/.test(summary)) fail('INVALID_MESSAGE', 'A one-line commit message is required.');
    if (typeof body !== 'string' || body.length > 100_000 || body.includes('\0')) fail('INVALID_MESSAGE', 'The commit description is invalid or too long.');
    return this._exclusive(async () => {
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      this._validateExpected(expectedHead, snapshot.head);
      if (!snapshot.branch) fail('DETACHED_HEAD', 'Amend requires a named branch.');
      await this._assertCommitPolicy(repo);
      const upstream = await this._optionalText(repo, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}']);
      if (upstream) {
        const contained = await this._git(repo, ['merge-base', '--is-ancestor', snapshot.head, upstream], { allowed: [0, 1] });
        if (contained.exitCode === 0) fail('ALREADY_PUSHED', 'The latest commit is already on the upstream; refusing to amend published history.');
      }
      const tree = await this._text(repo, ['rev-parse', 'HEAD^{tree}']);
      const parents = (await this._text(repo, ['rev-list', '--parents', '-n', '1', 'HEAD'])).split(' ').slice(1).filter(Boolean);
      const message = summary.trim() + (body.trim() ? `\n\n${body.trimEnd()}` : '') + '\n';
      const hash = await this._text(repo, ['commit-tree', tree, ...parents.flatMap((parent) => ['-p', parent])], { input: message });
      if (!HASH.test(hash)) fail('BAD_COMMIT', 'Git returned an invalid commit identifier.');
      await this._git(repo, ['update-ref', '-m', 'Git Review: amend message', `refs/heads/${snapshot.branch}`, hash, snapshot.head]);
      const skippedHooks = await this._hooksSkipped(repo);
      return { previousHead: snapshot.head, head: hash, amended: true,
        warnings: skippedHooks.length ? [{ code: 'HOOKS_SKIPPED', message: `Git hooks were present but not run: ${skippedHooks.map((hook) => hook.name).join(', ')}.` }] : [] };
    });
  }

  async branches() {
    try {
      const repo = await this._repo();
      const raw = await this._text(repo, ['for-each-ref', '--format=%(refname:short)%00%(objectname)%00%(upstream:short)%00%(HEAD)', 'refs/heads/']);
      if (!raw) return [];
      return raw.split('\n').map((record) => {
        const [name, head, upstream, current] = record.split('\0');
        return { name, head, upstream: upstream || null, current: current === '*' };
      });
    } catch (error) { throw this._publicError(error); }
  }

  _exclusive(action) {
    const result = this._queue.then(action);
    this._queue = result.catch(() => {});
    return result.catch((error) => { throw this._publicError(error); });
  }
  _publicError(error) {
    if (error instanceof GitEngineError) return error;
    // Filesystem errors may contain paths, file content, or remote credentials.
    return new GitEngineError('FILESYSTEM_ERROR', 'A repository file could not be safely accessed.');
  }
  _validateExpected(expectedHead, actual) {
    if (expectedHead !== null && (typeof expectedHead !== 'string' || !HASH.test(expectedHead))) fail('EXPECTED_HEAD_REQUIRED', 'The reviewed HEAD must be supplied.');
    if (expectedHead !== actual) fail('STALE_HEAD', 'HEAD changed; review the repository again.');
  }
  _assertState(snapshot, { staged = false, clean = false } = {}) {
    if (!snapshot.branch) fail('DETACHED_HEAD', 'This operation requires a named branch.');
    if (snapshot.states.length) fail('OPERATION_IN_PROGRESS', 'Finish the current merge, rebase, cherry-pick, revert, or bisect first.');
    if (snapshot.files.some((file) => file.conflict)) fail('CONFLICTS', 'Resolve conflicts before this operation.');
    if (!staged && snapshot.files.some((file) => file.staged)) fail('STAGED_CHANGES', 'Unstage all existing staged changes first; no staged data was changed.');
    if (snapshot.files.some((file) => file.submodule)) fail('SUBMODULES', 'Dirty submodules are not supported.');
    if (clean && snapshot.files.length) fail('DIRTY_WORKTREE', 'Switching branches requires a completely clean working tree and index.');
  }

  /**
   * Hooks are never executed by this engine: commits are built with
   * commit-tree and pushes run in an isolated bare repository. Report what was
   * present so callers can disclose the same behavior GitHub Desktop has.
   */
  async _hooksSkipped(repo) {
    const configured = await this._optionalText(repo, ['config', '--get', 'core.hooksPath']);
    if (configured !== null) return [{ name: 'core.hooksPath', path: configured }];
    const hookDir = await this._gitPath(repo, 'hooks');
    let entries;
    try { entries = await fs.readdir(hookDir); }
    catch (error) { if (error.code === 'ENOENT') return []; throw error; }
    const hooks = [];
    for (const name of entries) {
      if (name.endsWith('.sample')) continue;
      const info = await fs.stat(path.join(hookDir, name));
      if (info.isFile() && ((info.mode & 0o111) !== 0 || process.platform === 'win32')) hooks.push({ name, path: path.join(hookDir, name) });
    }
    return hooks;
  }
  async _assertNoFilters(repo, { strict = false, source } = {}) {
    const filters = await this._optionalText(repo, ['config', '--name-only', '--get-regexp', String.raw`^filter\..*\.(clean|smudge|process)$`]);
    if (!filters) return;
    const drivers = new Set(filters.split('\n').map((key) => /^filter\.(.*)\.(?:clean|smudge|process)$/.exec(key)?.[1]));
    if (!strict) {
      // Global Git LFS installation alone is harmless. Refuse only when current
      // tracked/untracked attributes actually select a configured driver.
      const names = (await this._git(repo, source ? ['ls-tree', '-r', '--name-only', '-z', source, '--'] : ['ls-files', '-z', '--cached', '--others', '--exclude-standard'])).stdout;
      const attributes = (await this._git(repo, ['check-attr', ...(source ? ['--source', source] : []), '-z', '--stdin', 'filter'], { input: names })).stdout.toString('utf8').split('\0');
      if (!attributes.some((value, index) => index % 3 === 2 && drivers.has(value))) return;
    }
    fail('FILTERS_CONFIGURED', 'External content filters apply to this repository; this engine will not execute or bypass them.');
  }
  async _assertCommitPolicy(repo) {
    await this._assertNoFilters(repo);
    if ((await this._optionalText(repo, ['config', '--type=bool', '--get', 'commit.gpgSign'])) === 'true') {
      fail('SIGNING_CONFIGURED', 'Commit signing is configured; commit-tree cannot silently bypass signing policy.');
    }
    if ((await this._optionalText(repo, ['config', '--type=bool', '--get', 'core.sparseCheckout'])) === 'true'
        || (await this._optionalText(repo, ['rev-parse', '--shared-index-path']))) {
      fail('UNSUPPORTED_INDEX', 'Sparse and split indexes are not supported for group commits.');
    }
  }

  _validateGroups(snapshot, groups) {
    if (!Array.isArray(groups) || !groups.length || groups.length > 50) fail('INVALID_GROUPS', 'Provide between 1 and 50 nonempty commit groups.');
    const byPath = new Map(snapshot.files.map((file) => [file.path, file]));
    const assigned = new Set();
    return groups.map((group) => {
      if (!group || typeof group.title !== 'string' || !group.title.trim() || /[\r\n\0]/.test(group.title)
          || group.title.length > 500 || (group.body !== undefined && (typeof group.body !== 'string' || group.body.includes('\0') || group.body.length > 100_000))
          || !Array.isArray(group.paths) || !group.paths.length) fail('INVALID_GROUP', 'Each group needs a one-line title and at least one file.');
      const files = group.paths.map((name) => {
        validPath(name);
        if (assigned.has(name)) fail('DUPLICATE_PATH', 'A file may belong to exactly one group.');
        assigned.add(name);
        const file = byPath.get(name);
        if (!file) fail('UNKNOWN_PATH', 'A group includes a file that is not dirty.');
        if (file.sensitive) fail('SENSITIVE_PATH', 'Environment and credential files cannot be committed by this engine.');
        if (file.submodule) fail('SUBMODULES', 'Submodules cannot be assigned to groups.');
        return file;
      });
      return { title: group.title.trim(), body: group.body || '', paths: [...group.paths], files };
    });
  }

  async _lock(file) {
    try {
      const handle = await fs.open(file, 'wx', 0o600);
      const identity = await handle.stat();
      return { file, handle, identity, owned: true };
    } catch (error) {
      if (error.code === 'EEXIST') fail('INDEX_LOCKED', 'Another Git operation holds a repository lock.');
      throw error;
    }
  }
  async _releaseLock(lock, preserve = false) {
    if (!lock) return;
    await lock.handle.close().catch(() => {});
    if (!lock.owned || preserve) return;
    try {
      const current = await fs.lstat(lock.file);
      if (current.ino === lock.identity.ino && current.dev === lock.identity.dev) await fs.unlink(lock.file);
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  async _verifyPreparedIndex(repo, env, names, { invalidate = false } = {}) {
    if (invalidate) {
      // Remove and reinsert entries so no cached stat tuple can hide an ABA
      // change captured by add and later restored to the reviewed worktree.
      const entries = (await this._git(repo, ['ls-files', '--stage', '-z', '--', ...names], { env })).stdout;
      await this._git(repo, ['update-index', '--force-remove', '--', ...names], { env });
      if (entries.length) await this._git(repo, ['update-index', '-z', '--index-info'], { env, input: entries });
    }
    const result = await this._git(repo, ['diff', '--quiet', '--no-ext-diff', '--no-textconv', '--ignore-submodules=none', '--', ...names], { env, allowed: [0, 1] });
    if (result.exitCode !== 0) fail('STALE_SNAPSHOT', 'Prepared file contents differ from the reviewed worktree; no commits were applied.');
  }
  async _installIndex(lock, index) {
    const current = await fs.lstat(lock.file);
    if (current.ino !== lock.identity.ino || current.dev !== lock.identity.dev || !current.isFile()) fail('LOCK_CHANGED', 'The index lock changed ownership before finalization.');
    await fs.rename(lock.file, index);
    lock.owned = false;
  }
  async _removeTemp(repo, directory) {
    if (path.dirname(directory) !== repo.gitDir || !path.basename(directory).startsWith('harness-git-review-')) {
      fail('UNSAFE_RECOVERY_PATH', 'Recovery cleanup refused an unexpected directory.');
    }
    await fs.rm(directory, { recursive: true, force: false });
  }

  _assertProposalSelection(snapshot, expectedHead, pathHashes) {
    if (typeof expectedHead !== 'string' || !HASH.test(expectedHead)) fail('EXPECTED_HEAD_REQUIRED', 'The proposal HEAD must be supplied.');
    if (snapshot.head !== expectedHead) fail('STALE_HEAD', 'HEAD changed since the proposal; organize again.');
    if (!pathHashes || typeof pathHashes !== 'object' || Array.isArray(pathHashes)) fail('STALE_SNAPSHOT', 'A grouped-file hash manifest is required.');
    const current = new Map(snapshot.files.map((file) => [file.path, file]));
    const changed = [];
    for (const [name, digest] of Object.entries(pathHashes)) {
      const file = current.get(name);
      if (!file || file.contentHash !== digest) changed.push(name);
    }
    if (changed.length) fail('STALE_SELECTION', 'Grouped files changed since the proposal: ' + changed.slice(0, 5).join(', ')
      + (changed.length > 5 ? ` and ${changed.length - 5} more` : '') + '; no commits were applied.', { changedPaths: changed });
  }

  commitGroups({ fingerprint, groups, expectedHead, pathHashes } = {}) {
    return this._exclusive(async () => {
      if (typeof fingerprint !== 'string' || !/^[a-f0-9]{64}$/.test(fingerprint)) fail('FINGERPRINT_REQUIRED', 'Supply the reviewed snapshot fingerprint.');
      const repo = await this._repo();
      const indexInfo = await fs.lstat(repo.index).catch((error) => { if (error.code === 'ENOENT') return null; throw error; });
      if (indexInfo && !indexInfo.isFile()) fail('UNSUPPORTED_INDEX', 'The real index must be an ordinary file.');
      const lock = await this._lock(`${repo.index}.lock`);
      let headLock, directory, advanced = false, preserve = false, completed = false, recovery;
      try {
        const snapshot = await this._snapshot(repo);
        if (pathHashes !== undefined) this._assertProposalSelection(snapshot, expectedHead, pathHashes);
        else if (snapshot.fingerprint !== fingerprint) fail('STALE_SNAPSHOT', 'Files, index, or HEAD changed; regenerate the commit plan.');
        this._assertState(snapshot);
        const validated = this._validateGroups(snapshot, groups);
        await this._assertCommitPolicy(repo);
        const skippedHooks = await this._hooksSkipped(repo);
        const ref = await this._text(repo, ['symbolic-ref', '--quiet', 'HEAD']);
        directory = await fs.mkdtemp(path.join(repo.gitDir, 'harness-git-review-'));
        const alternateIndex = path.join(directory, 'index');
        const originalIndex = await optionalRead(repo.index);
        if (originalIndex) {
          await fs.writeFile(alternateIndex, originalIndex, { mode: 0o600 });
          await fs.writeFile(path.join(directory, 'original-index'), originalIndex, { mode: 0o600 });
        }
        const env = { GIT_INDEX_FILE: alternateIndex };
        if (!originalIndex) await this._git(repo, ['read-tree', '--empty'], { env });
        let previous = snapshot.head;
        let previousTree = await this._text(repo, ['write-tree'], { env });
        const commits = [];
        for (const group of validated) {
          const selected = [...new Set(group.files.flatMap((file) => [file.path, ...(file.originalPath ? [file.originalPath] : [])]))];
          const present = [];
          for (const name of selected) {
            await this._safeDiskPath(repo, name);
            try { await fs.lstat(path.join(repo.root, ...name.split('/'))); present.push(name); }
            catch (error) { if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error; }
          }
          // A copied index carries stat data from the real index. `git add` may
          // trust a stale stat tuple and keep the pre-review blob (notably for
          // same-size edits). Drop selected entries so add must stage content.
          // Absent (deleted) paths are removed but cannot be passed to add.
          await this._git(repo, ['update-index', '--force-remove', '--', ...selected], { env });
          if (present.length) await this._git(repo, ['add', '--all', '--', ...present], { env });
          const tree = await this._text(repo, ['write-tree'], { env });
          if (tree === previousTree) fail('EMPTY_GROUP', 'A group has no committable changes; no commits were applied.');
          const message = `${group.title}\n${group.body ? `\n${group.body.replace(/\n*$/, '')}\n` : ''}`;
          const hash = await this._text(repo, ['commit-tree', tree, ...(previous ? ['-p', previous] : [])], { env, input: message });
          if (!HASH.test(hash)) fail('BAD_COMMIT', 'Git returned an invalid commit identifier.');
          commits.push({ hash, title: group.title, paths: group.paths });
          previous = hash; previousTree = tree;
        }
        const selectedAll = [...new Set(validated.flatMap((group) => group.files.flatMap((file) => [file.path, ...(file.originalPath ? [file.originalPath] : [])])))];
        await this._verifyPreparedIndex(repo, env, selectedAll, { invalidate: true });
        const finalIndex = await fs.readFile(alternateIndex);
        await lock.handle.writeFile(finalIndex);
        if (originalIndex) await lock.handle.chmod((await fs.stat(repo.index)).mode & 0o777);
        await lock.handle.sync();
        recovery = { version: 1, ref, oldHead: snapshot.head, newHead: previous, commits, alternateIndex,
          originalIndex: originalIndex ? path.join(directory, 'original-index') : null, index: repo.index, indexLock: lock.file,
          state: 'prepared', directory };
        await fs.writeFile(path.join(directory, 'recovery.json'), JSON.stringify(recovery, null, 2), { mode: 0o600 });
        const recoveryHandle = await fs.open(path.join(directory, 'recovery.json'), 'r');
        try { await recoveryHandle.sync(); } finally { await recoveryHandle.close(); }
        await this._assertCommitPolicy(repo);
        const checked = await this._snapshot(repo);
        if (pathHashes !== undefined) this._assertProposalSelection(checked, expectedHead, pathHashes);
        else if (checked.fingerprint !== fingerprint) fail('STALE_SNAPSHOT', 'Files, index, or HEAD changed while building the commit series; no commits were applied.');
        await this._verifyPreparedIndex(repo, env, selectedAll);
        const old = snapshot.head ?? '0'.repeat(previous.length);
        try {
          await this._git(repo, ['update-ref', '-m', 'Harness Git review: grouped commits', ref, previous, old]);
          advanced = true;
        } catch (error) {
          // A killed process may have completed the ref transaction. Resolve the
          // exact ref, never retry the write or assume the operation failed.
          let actual;
          try { actual = await this._optionalText(repo, ['rev-parse', '--verify', ref]); }
          catch { preserve = true; fail('PARTIAL_COMMIT', 'The branch update outcome is uncertain; recovery files and the index lock were retained.', { partial: true, recovery }); }
          if (actual === previous) advanced = true;
          else throw error;
        }
        // update-ref itself locks HEAD when updating its referent. Holding
        // HEAD.lock earlier would deadlock that transaction. Acquire it now and
        // verify the symbolic target before installing the matching index.
        headLock = await this._lock(await this._gitPath(repo, 'HEAD.lock'));
        if (await this._text(repo, ['symbolic-ref', '--quiet', 'HEAD']) !== ref || await this._head(repo) !== previous) {
          preserve = true;
          fail('PARTIAL_COMMIT', 'The branch was committed but HEAD changed concurrently; recovery files and the index lock were retained.', { partial: true, recovery });
        }
        try {
          await this._installIndex(lock, repo.index);
        } catch {
          preserve = true;
          fail('PARTIAL_COMMIT', 'The commits exist and HEAD advanced, but the index could not be installed. Recovery files and the index lock were retained.',
            { partial: true, recovery: { ...recovery, state: 'head-updated' } });
        }
        completed = true;
        const warnings = skippedHooks.length
          ? [{ code: 'HOOKS_SKIPPED', message: `Git hooks were present but not run: ${skippedHooks.map((hook) => hook.name).join(', ')}.` }]
          : [];
        return { head: previous, previousHead: snapshot.head, commits, atomic: true, warnings };
      } catch (error) {
        if (advanced && !completed && !error.partial) {
          preserve = true;
          fail('PARTIAL_COMMIT', 'HEAD advanced but finalization failed. Recovery files and the index lock were retained.', { partial: true, recovery });
        }
        throw error;
      } finally {
        let cleanupFailed = false;
        try { await this._releaseLock(headLock); } catch { cleanupFailed = true; }
        try { await this._releaseLock(lock, preserve); } catch { cleanupFailed = true; }
        if (cleanupFailed) {
          preserve = true;
          fail(advanced ? 'PARTIAL_COMMIT' : 'RECOVERY_REQUIRED',
            advanced ? 'The commits were applied but repository lock cleanup failed; inspect retained recovery data.' : 'Repository lock cleanup failed; inspect the retained locks before retrying.',
            { partial: advanced, recovery: { ...recovery, indexLock: lock.file, headLock: headLock?.file, indexInstalled: completed } });
        }
        if (directory && !preserve) await this._removeTemp(repo, directory).catch(() => {});
      }
    });
  }

  push({ expectedHead, expectedTarget } = {}) {
    return this._exclusive(async () => {
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      this._validateExpected(expectedHead, snapshot.head);
      this._assertState(snapshot, { staged: true });
      if (!snapshot.head) fail('UNBORN_HEAD', 'There is no commit to push.');
      if (!snapshot.pushTarget) fail('NO_UPSTREAM', 'A configured upstream destination is required.');
      if (typeof expectedTarget !== 'string' || !/^[a-f0-9]{64}$/.test(expectedTarget)) fail('EXPECTED_TARGET_REQUIRED', 'Supply the reviewed push destination fingerprint.');
      if (snapshot.pushTarget.fingerprint !== expectedTarget) fail('STALE_PUSH_TARGET', 'The push destination or transport configuration changed; review again.');
      const skippedHooks = await this._hooksSkipped(repo);
      if (Object.keys(process.env).some((key) => key.startsWith('GIT_SSH') && process.env[key])) fail('UNSAFE_REMOTE', 'Custom SSH environment commands are configured; pushing is disabled.');
      const resolvedTarget = await this._pushTarget(repo, snapshot.branch, { includeUrls: true });
      if (resolvedTarget?.fingerprint !== expectedTarget) fail('STALE_PUSH_TARGET', 'The push destination changed while it was being resolved; review again.');
      const remote = resolvedTarget.remote;
      const mergeRaw = resolvedTarget.ref;
      if (!remote || remote === '.' || remote.startsWith('-') || /[\s\0]/.test(remote) || !mergeRaw
          || mergeRaw.includes('\n') || !mergeRaw.startsWith('refs/heads/')) fail('NO_UPSTREAM', 'A single remote branch upstream must be configured before pushing.');
      const merge = mergeRaw;
      await this._git(repo, ['check-ref-format', merge]);
      if ((await this._optionalText(repo, ['config', '--type=bool', '--get', `remote.${remote}.mirror`])) === 'true') fail('UNSAFE_REMOTE', 'Mirror remotes are not supported.');
      for (const key of [`remote.${remote}.receivepack`, `remote.${remote}.uploadpack`, `remote.${remote}.vcs`, 'core.sshCommand']) {
        if (await this._optionalText(repo, ['config', '--get', key]) !== null) fail('UNSAFE_REMOTE', 'Custom transport commands are configured; pushing is disabled.');
      }
      const urls = resolvedTarget.urls;
      if (urls.length !== 1) fail('UNSAFE_REMOTE', 'Pushing requires exactly one configured destination.');
      const url = urls[0];
      let allowed = false;
      const sshHost = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?|\[[a-fA-F0-9:]+\])$/;
      const sshUser = /^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$/;
      if (url.startsWith('https://')) {
        let parsed;
        try { parsed = new URL(url); } catch { fail('UNSAFE_REMOTE', 'The push destination is not supported.'); }
        allowed = !parsed.username && !parsed.password;
      } else if (url.startsWith('ssh://')) {
        let parsed;
        try { parsed = new URL(url); } catch { fail('UNSAFE_REMOTE', 'The push destination is not supported.'); }
        allowed = sshHost.test(parsed.hostname) && (!parsed.username || sshUser.test(parsed.username)) && !parsed.password;
      } else if (url.startsWith('file://')) {
        let parsed;
        try { parsed = new URL(url); } catch { fail('UNSAFE_REMOTE', 'The push destination is not supported.'); }
        allowed = (!parsed.hostname || parsed.hostname === 'localhost') && !parsed.username && !parsed.password;
      } else if (url.includes(':')) {
        const scp = /^(?:([^@/:]+)@)?([^/:]+):(.+)$/.exec(url);
        allowed = Boolean(scp && (!scp[1] || sshUser.test(scp[1])) && sshHost.test(scp[2]) && /^[a-zA-Z0-9_./~@+-]+$/.test(scp[3]));
      } else allowed = Boolean(url) && !url.startsWith('-') && !/[\0\r\n]/.test(url);
      if (!allowed || /[\0\r\n]/.test(url)) fail('UNSAFE_REMOTE', 'Only local/file, credential-free HTTPS, and standard SSH upstreams are supported; custom helpers and embedded credentials are refused.');
      const beforePush = await this._snapshot(repo);
      this._validateExpected(expectedHead, beforePush.head);
      if (beforePush.branch !== snapshot.branch) fail('STALE_HEAD', 'The current branch changed; review again.');
      if (beforePush.pushTarget?.fingerprint !== expectedTarget) fail('STALE_PUSH_TARGET', 'The push destination or transport configuration changed; review again.');
      // An explicit URL still honors url.*.insteadOf in an ordinary repository.
      // Use a private bare Git directory with only controlled configuration, so
      // a late config rewrite cannot redirect the already approved destination.
      const sandbox = await fs.mkdtemp(path.join(repo.gitDir, 'harness-git-review-push-'));
      const objects = await this._gitPath(repo, 'objects');
      const format = await this._text(repo, ['rev-parse', '--show-object-format']);
      await fs.mkdir(path.join(sandbox, 'refs'), { recursive: true });
      await fs.mkdir(path.join(sandbox, 'objects'), { recursive: true });
      await fs.writeFile(path.join(sandbox, 'HEAD'), `${expectedHead}\n`, { mode: 0o600 });
      await fs.writeFile(path.join(sandbox, 'config'), `[core]\nrepositoryformatversion = ${format === 'sha256' ? '1' : '0'}\nbare = true\n${format === 'sha256' ? '[extensions]\nobjectformat = sha256\n' : ''}`, { mode: 0o600 });
      try {
        await this._git(repo, ['-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always', '-c', 'protocol.https.allow=always', '-c', 'protocol.ssh.allow=always',
          '-c', 'credential.helper=', '-c', 'core.askPass=', '-c', 'credential.interactive=false',
          '-c', 'push.followTags=false', '-c', 'push.recurseSubmodules=no',
          'push', '--porcelain', '--no-recurse-submodules', '--', url, `${expectedHead}:${merge}`], {
          timeout: PUSH_TIMEOUT,
          env: { GIT_DIR: sandbox, GIT_OBJECT_DIRECTORY: objects, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null',
            GIT_SSH_VARIANT: 'ssh', GIT_SSH_COMMAND: 'ssh -F /dev/null -oBatchMode=yes -oStrictHostKeyChecking=yes -oUpdateHostKeys=no -oAddKeysToAgent=no -oPermitLocalCommand=no -oProxyCommand=none -oProxyJump=none -oKnownHostsCommand=none -oControlMaster=no -oControlPath=none -oForwardAgent=no -oForwardX11=no -oRequestTTY=no' },
        });
      } catch (error) {
        throw new GitEngineError('PUSH_FAILED', 'Push did not report success. No force was used. Authentication must already work noninteractively; SSH requires a known host and an available key/agent. Check the remote before retrying.', { mayHaveSucceeded: true, causeCode: error.code });
      } finally { await this._removeTemp(repo, sandbox).catch(() => {}); }
      return { head: expectedHead, remote, branch: merge.slice('refs/heads/'.length), upstream: `${remote}/${merge.slice('refs/heads/'.length)}`, forced: false,
        warnings: [
          { code: 'TRACKING_REFS_UNCHANGED', message: 'Remote-tracking refs were not refreshed; ahead/behind remain based on the last local fetch.' },
          ...(skippedHooks.length ? [{ code: 'HOOKS_SKIPPED', message: `Git hooks were present but not run: ${skippedHooks.map((hook) => hook.name).join(', ')}.` }] : []),
        ] };
    });
  }

  checkout({ branch, expectedHead } = {}) {
    return this._exclusive(async () => {
      if (typeof branch !== 'string' || !branch || branch.startsWith('-') || /[\s\0]/.test(branch)) fail('INVALID_BRANCH', 'An existing local branch name is required.');
      const repo = await this._repo();
      const snapshot = await this._snapshot(repo);
      this._validateExpected(expectedHead, snapshot.head);
      this._assertState(snapshot, { clean: true });
      await this._assertNoFilters(repo);
      const skippedHooks = await this._hooksSkipped(repo);
      if (!(await this.branches()).some((item) => item.name === branch)) fail('UNKNOWN_BRANCH', 'The selected local branch does not exist.');
      await this._assertNoFilters(repo, { source: `refs/heads/${branch}` });
      if (branch === snapshot.branch) return { branch, head: snapshot.head, changed: false };
      // Git itself obtains index/ref locks and refuses overwrites. No force,
      // autostash, branch creation, remote guessing, or submodule recursion.
      try {
        await this._git(repo, ['-c', 'submodule.recurse=false', '-c', 'core.hooksPath=/dev/null', 'switch', '--no-guess', '--no-recurse-submodules', '--', branch]);
      } catch (error) {
        throw new GitEngineError('CHECKOUT_FAILED', 'Git did not report a successful branch switch; refresh repository state.', { mayHaveSucceeded: true, causeCode: error.code });
      }
      return { branch: await this._branch(repo), head: await this._head(repo), changed: true,
        warnings: skippedHooks.length ? [{ code: 'HOOKS_SKIPPED', message: `Git hooks were present but not run: ${skippedHooks.map((hook) => hook.name).join(', ')}.` }] : [] };
    });
  }
}

export function createGitEngine(options) { return new GitEngine(options); }
