import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createGitEngine, GitEngine, GitEngineError } from './git-engine.js';

// Every write, Git operation, hook fixture, remote, and recovery artifact lives
// under this disposable tree. Never use the checkout containing these tests.
const execute = promisify(execFile);
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'git-engine-tests-'));
const previousHome = process.env.HOME;
const previousXdg = process.env.XDG_CONFIG_HOME;
process.env.HOME = path.join(temporary, 'home');
process.env.XDG_CONFIG_HOME = path.join(temporary, 'xdg');
await fs.mkdir(process.env.HOME, { recursive: true });
await fs.mkdir(process.env.XDG_CONFIG_HOME, { recursive: true });

after(async () => {
  if (previousHome === undefined) delete process.env.HOME; else process.env.HOME = previousHome;
  if (previousXdg === undefined) delete process.env.XDG_CONFIG_HOME; else process.env.XDG_CONFIG_HOME = previousXdg;
  assert.equal(path.dirname(temporary), os.tmpdir());
  assert.ok(path.basename(temporary).startsWith('git-engine-tests-'));
  await fs.rm(temporary, { recursive: true });
});

async function git(cwd, args, { input, allowed = [0] } = {}) {
  try {
    // execFile cannot accept stdin directly; commit-tree fixtures use the small
    // spawn wrapper below. Ordinary fixture commands have argv only.
    assert.equal(input, undefined);
    const result = await execute('git', args, { cwd, env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_TERMINAL_PROMPT: '0' }, maxBuffer: 16 * 1024 * 1024 });
    return result.stdout.trimEnd();
  } catch (error) {
    if (allowed.includes(error.code)) return error.stdout.trimEnd();
    throw error;
  }
}
async function write(root, name, content) {
  const target = path.join(root, name);
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, content);
}
async function fixture(files = { 'a.txt': 'a base\n', 'b.txt': 'b base\n', 'c.txt': 'c base\n' }, { unborn = false } = {}) {
  const root = await fs.mkdtemp(path.join(temporary, 'repo-'));
  await git(root, ['init', '-b', 'main']);
  await git(root, ['config', 'user.name', 'Engine Test']);
  await git(root, ['config', 'user.email', 'engine@example.invalid']);
  await git(root, ['config', 'commit.gpgSign', 'false']);
  await git(root, ['config', 'core.fileMode', 'true']);
  for (const [name, content] of Object.entries(files)) await write(root, name, content);
  if (!unborn && Object.keys(files).length) {
    await git(root, ['add', '--all']);
    await git(root, ['commit', '-m', 'Initial fixture']);
  }
  return { root, engine: createGitEngine({ cwd: root }), index: path.join(root, '.git', 'index') };
}
const group = (paths, title = 'Reviewed change', body) => ({ title, paths, ...(body === undefined ? {} : { body }) });
async function plan(engine, groups) { return { fingerprint: (await engine.snapshot()).fingerprint, groups }; }
const code = (expected) => (error) => { assert.ok(error instanceof GitEngineError); assert.equal(error.code, expected); return true; };
const head = (root) => git(root, ['rev-parse', 'HEAD']);
const cached = (root, name) => git(root, ['show', `:${name}`]);
async function pushReviewed(engine, expectedHead) {
  const snapshot = await engine.snapshot();
  return engine.push({ expectedHead, expectedTarget: snapshot.pushTarget?.fingerprint });
}

// Read-only operations and content-based staleness.
test('snapshot, history, branches and diff are read-only and expose stable interface', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'a changed\n');
  const indexBefore = await fs.readFile(index);
  const statusBefore = await git(root, ['status', '--porcelain=v2', '-z']);
  const snapshot = await engine.snapshot();
  assert.equal(snapshot.root, await fs.realpath(root));
  assert.equal(snapshot.branch, 'main');
  assert.equal(snapshot.head, await head(root));
  assert.equal(snapshot.upstream, null);
  assert.equal(snapshot.ahead, 0); assert.equal(snapshot.behind, 0);
  assert.equal(snapshot.canCommit, true);
  assert.deepEqual(snapshot.files.map(({ path, status, staged, unstaged }) => ({ path, status, staged, unstaged })), [
    { path: 'a.txt', status: '.M', staged: false, unstaged: true },
  ]);
  assert.equal(snapshot.files[0].additions, 1); assert.equal(snapshot.files[0].deletions, 1);
  assert.match((await engine.diff({ path: 'a.txt' })).text, /\+a changed/);
  const history = await engine.history();
  assert.equal(history.length, 1); assert.equal(history[0].title, 'Initial fixture');
  assert.deepEqual(history[0].parents, []);
  assert.match((await engine.diff({ commit: snapshot.head })).text, /a base/);
  assert.match((await engine.diff({ commit: snapshot.head, path: 'b.txt' })).text, /b base/);
  assert.equal((await engine.branches())[0].current, true);
  assert.deepEqual(await fs.readFile(index), indexBefore);
  assert.equal(await git(root, ['status', '--porcelain=v2', '-z']), statusBefore);
  assert.equal((await engine.snapshot()).fingerprint, snapshot.fingerprint);
});

test('fingerprint ignores mtime but includes complete tracked and untracked contents and modes', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'first dirty\n');
  await write(root, 'untracked', 'one\n');
  const initial = await engine.snapshot();
  const stat = await fs.stat(path.join(root, 'a.txt'));
  await fs.utimes(path.join(root, 'a.txt'), new Date(0), new Date(0));
  assert.equal((await engine.snapshot()).fingerprint, initial.fingerprint);
  await write(root, 'a.txt', 'other dirty\n');
  await fs.utimes(path.join(root, 'a.txt'), stat.atime, stat.mtime);
  const changed = await engine.snapshot();
  assert.notEqual(changed.fingerprint, initial.fingerprint);
  await write(root, 'untracked', 'two\n');
  const untrackedChanged = await engine.snapshot();
  assert.notEqual(untrackedChanged.fingerprint, changed.fingerprint);
  await fs.chmod(path.join(root, 'untracked'), 0o755);
  assert.notEqual((await engine.snapshot()).fingerprint, untrackedChanged.fingerprint);
});

test('fingerprint includes real index bytes even without staged changes', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'dirty\n');
  const original = await engine.snapshot();
  await git(root, ['update-index', '--assume-unchanged', 'b.txt']);
  const changed = await engine.snapshot();
  assert.equal(changed.files.some((file) => file.staged), false);
  assert.notEqual(original.fingerprint, changed.fingerprint);
  await assert.rejects(engine.commitGroups({ fingerprint: original.fingerprint, groups: [group(['a.txt'])] }), code('STALE_SNAPSHOT'));
});

test('staged and unstaged versions are separately detected and never lost', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'staged version\n');
  await git(root, ['add', '--', 'a.txt']);
  await write(root, 'a.txt', 'working version\n');
  await write(root, 'b.txt', 'other dirty\n');
  const snapshot = await engine.snapshot();
  const file = snapshot.files.find((item) => item.path === 'a.txt');
  assert.equal(file.status, 'MM'); assert.equal(file.staged, true); assert.equal(file.unstaged, true);
  assert.equal(snapshot.canCommit, false); assert.ok(snapshot.blockedReasons.includes('STAGED_CHANGES'));
  const diff = await engine.diff({ path: 'a.txt' });
  assert.match(diff.text, /Staged changes/); assert.match(diff.text, /Unstaged changes/);
  assert.match(diff.text, /staged version/); assert.match(diff.text, /working version/);
  const before = await fs.readFile(index); const oldHead = await head(root);
  await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['b.txt'])] }), code('STAGED_CHANGES'));
  assert.deepEqual(await fs.readFile(index), before);
  assert.equal(await cached(root, 'a.txt'), 'staged version');
  assert.equal(await fs.readFile(path.join(root, 'a.txt'), 'utf8'), 'working version\n');
  assert.equal(await head(root), oldHead);
});

test('atomic ordered commit groups include only intended files and preserve unrelated working tree/index flags', async () => {
  const { root, engine } = await fixture({ 'a.txt': 'a base\n', 'b.txt': 'b base\n', 'c.txt': 'c base\n', 'flagged.txt': 'flag\n' });
  const oldHead = await head(root);
  await git(root, ['update-index', '--assume-unchanged', 'flagged.txt']);
  for (const name of ['a.txt', 'b.txt', 'c.txt']) await write(root, name, `${name} changed\n`);
  await write(root, 'unrelated.txt', 'not assigned\n');
  const beforeFiles = await Promise.all(['a.txt', 'b.txt', 'c.txt', 'unrelated.txt'].map((name) => fs.readFile(path.join(root, name))));
  const result = await engine.commitGroups(await plan(engine, [group(['a.txt'], 'First group', 'Detailed body'), group(['b.txt'], 'Second group')]));
  assert.equal(result.atomic, true); assert.equal(result.previousHead, oldHead); assert.equal(result.commits.length, 2);
  assert.equal(await head(root), result.head);
  assert.equal(await git(root, ['show', '--format=', '--name-only', result.commits[0].hash]), 'a.txt');
  assert.equal(await git(root, ['show', '--format=', '--name-only', result.commits[1].hash]), 'b.txt');
  assert.equal(await git(root, ['rev-parse', `${result.commits[0].hash}^`]), oldHead);
  assert.equal(await git(root, ['rev-parse', `${result.head}^`]), result.commits[0].hash);
  assert.match(await git(root, ['log', '-1', '--format=%B', result.commits[0].hash]), /First group\n\nDetailed body/);
  assert.equal(await git(root, ['show', 'HEAD:c.txt']), 'c base');
  assert.equal(await cached(root, 'c.txt'), 'c base');
  assert.equal(await git(root, ['diff', '--cached', '--name-only']), '');
  assert.match(await git(root, ['ls-files', '-v', '--', 'flagged.txt']), /^h /);
  assert.deepEqual(await Promise.all(['a.txt', 'b.txt', 'c.txt', 'unrelated.txt'].map((name) => fs.readFile(path.join(root, name)))), beforeFiles);
  assert.deepEqual((await engine.snapshot()).files.map((file) => file.path), ['c.txt', 'unrelated.txt']);
  assert.equal(await fs.access(path.join(root, '.git', 'index.lock')).then(() => true, () => false), false);
});

test('unborn branch commits selected files without staging unrelated untracked files', async () => {
  const { root, engine } = await fixture({ 'a.txt': 'new\n', 'unrelated.txt': 'leave me\n' }, { unborn: true });
  const before = await engine.snapshot();
  assert.equal(before.head, null); assert.equal(before.branch, 'main'); assert.deepEqual(await engine.history(), []);
  const result = await engine.commitGroups({ fingerprint: before.fingerprint, groups: [group(['a.txt'], 'Root commit')] });
  assert.equal(result.previousHead, null);
  assert.equal(await git(root, ['rev-list', '--count', 'HEAD']), '1');
  assert.equal(await git(root, ['ls-tree', '--name-only', 'HEAD']), 'a.txt');
  assert.equal(await fs.readFile(path.join(root, 'unrelated.txt'), 'utf8'), 'leave me\n');
  assert.deepEqual((await engine.snapshot()).files.map((file) => file.path), ['unrelated.txt']);
});

test('spaces, leading dash, shell metacharacters, newlines, Unicode and literal pathspecs are argv-safe', async () => {
  const { root, engine } = await fixture();
  const names = ['space name.txt', '-leading-dash', '$(touch PWNED)', 'semi;colon.txt', 'line\nbreak.txt', 'emoji-🧪.txt', ':(glob)*.txt', '[wildcard].txt'];
  for (const name of names) await write(root, name, `literal ${name}\n`);
  assert.match((await engine.diff({ path: '-leading-dash' })).text, /literal -leading-dash/);
  const result = await engine.commitGroups(await plan(engine, [group(names)]));
  assert.ok(result.head);
  const tracked = (await execute('git', ['ls-tree', '-r', '--name-only', '-z', 'HEAD'], { cwd: root })).stdout.split('\0');
  for (const name of names) assert.ok(tracked.includes(name));
  assert.equal(await fs.access(path.join(root, 'PWNED')).then(() => true, () => false), false);
});

test('symlinks are hashed and committed as links, never target contents', async () => {
  const { root, engine } = await fixture();
  const external = path.join(temporary, 'outside-secret');
  await fs.writeFile(external, 'NEVER READ THIS TARGET\0');
  await fs.symlink(external, path.join(root, 'link'));
  const snapshot = await engine.snapshot();
  const link = snapshot.files.find((file) => file.path === 'link');
  assert.equal(link.symlink, true); assert.equal(link.binary, false);
  const diff = await engine.diff({ path: 'link' });
  assert.doesNotMatch(diff.text, /NEVER READ THIS TARGET/);
  const firstFingerprint = snapshot.fingerprint;
  await fs.writeFile(external, 'TARGET CHANGED');
  assert.equal((await engine.snapshot()).fingerprint, firstFingerprint);
  await engine.commitGroups(await plan(engine, [group(['link'])]));
  assert.match(await git(root, ['ls-tree', 'HEAD', 'link']), /^120000 blob /);
  assert.equal(await git(root, ['show', 'HEAD:link']), external);
  assert.equal(await fs.readFile(external, 'utf8'), 'TARGET CHANGED');
});

test('deletes, executable modes, binary and untracked additions form whole-file units', async () => {
  const { root, engine } = await fixture({ 'delete.txt': 'remove\n', 'script': '#!/bin/sh\necho ok\n', 'image.bin': Buffer.from([0, 1, 2]) });
  await fs.unlink(path.join(root, 'delete.txt'));
  await fs.chmod(path.join(root, 'script'), 0o755);
  await write(root, 'image.bin', Buffer.from([0, 4, 5]));
  await write(root, 'new.bin', Buffer.from([0, 8]));
  const snapshot = await engine.snapshot();
  assert.equal(snapshot.files.find((file) => file.path === 'delete.txt').status, '.D');
  assert.equal(snapshot.files.find((file) => file.path === 'image.bin').binary, true);
  assert.equal(snapshot.files.find((file) => file.path === 'new.bin').binary, true);
  const diff = await engine.diff({ path: 'image.bin' });
  assert.equal(diff.binary, true); assert.match(diff.text, /Binary files/); assert.doesNotMatch(diff.text, /GIT binary patch/);
  await write(root, '.gitattributes', '*.bin diff\n');
  const forcedText = await engine.diff({ path: 'image.bin' });
  assert.equal(forcedText.binary, true); assert.doesNotMatch(forcedText.text, /\0/); assert.match(forcedText.text, /binary content is not displayed/);
  await fs.unlink(path.join(root, '.gitattributes'));
  await engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['delete.txt']), group(['script', 'image.bin', 'new.bin'])] });
  assert.match(await git(root, ['ls-tree', 'HEAD', 'script']), /^100755 blob /);
  assert.equal(await git(root, ['ls-tree', 'HEAD', 'delete.txt']), '');
  assert.deepEqual((await engine.snapshot()).files, []);
});

test('stale content, new files and HEAD changes reject old plans without writes', async (t) => {
  for (const kind of ['content', 'untracked', 'head']) await t.test(kind, async () => {
    const { root, engine, index } = await fixture();
    await write(root, 'a.txt', 'reviewed\n');
    const prepared = await plan(engine, [group(['a.txt'])]);
    if (kind === 'content') await write(root, 'a.txt', 'unreviewed\n');
    if (kind === 'untracked') await write(root, 'new-file', 'new\n');
    if (kind === 'head') { await git(root, ['commit', '--allow-empty', '-m', 'Concurrent commit']); }
    const expected = await head(root); const indexBefore = await fs.readFile(index);
    await assert.rejects(engine.commitGroups(prepared), code('STALE_SNAPSHOT'));
    assert.equal(await head(root), expected); assert.deepEqual(await fs.readFile(index), indexBefore);
  });
});

test('unrelated working changes do not block commits whose grouped files still match', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'reviewed a\n');
  await write(root, 'b.txt', 'reviewed b\n');
  const snapshot = await engine.snapshot();
  const hash = snapshot.files.find((file) => file.path === 'a.txt').contentHash;
  assert.match(hash, /^[a-f0-9]{64}$/);
  await write(root, 'c.txt', 'concurrent unrelated edit\n');
  await engine.commitGroups({
    fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])],
    expectedHead: snapshot.head, pathHashes: { 'a.txt': hash },
  });
  assert.equal(await git(root, ['show', 'HEAD:a.txt']), 'reviewed a');
  assert.equal(await git(root, ['show', 'HEAD:c.txt']), 'c base');
  assert.equal(await fs.readFile(path.join(root, 'c.txt'), 'utf8'), 'concurrent unrelated edit\n');
});

test('a grouped file changing after the proposal is rejected with its paths', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'reviewed a\n');
  const snapshot = await engine.snapshot();
  const hash = snapshot.files.find((file) => file.path === 'a.txt').contentHash;
  await write(root, 'a.txt', 'changed after review\n');
  await assert.rejects(
    engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])], expectedHead: snapshot.head, pathHashes: { 'a.txt': hash } }),
    (error) => { assert.equal(error.code, 'STALE_SELECTION'); assert.deepEqual(error.changedPaths, ['a.txt']); return true; },
  );
});

test('stash moves tracked and untracked changes aside and keeps them recoverable', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'changed\n');
  await write(root, 'new.txt', 'temporary\n');
  const result = await engine.stashChanges({ message: 'review stash' });
  assert.equal(result.stashed, true);
  assert.deepEqual((await engine.snapshot()).files, []);
  assert.match(await git(root, ['stash', 'list']), /review stash/);
  await git(root, ['stash', 'pop']);
  assert.equal(await fs.readFile(path.join(root, 'a.txt'), 'utf8'), 'changed\n');
  assert.equal(await fs.readFile(path.join(root, 'new.txt'), 'utf8'), 'temporary\n');
});

test('discard restores tracked files and deletes untracked files only', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'changed\n');
  await write(root, 'new.txt', 'temporary\n');
  await fs.unlink(path.join(root, 'b.txt'));
  const snapshot = await engine.snapshot();
  assert.deepEqual(snapshot.files.map((file) => file.path).sort(), ['a.txt', 'b.txt', 'new.txt']);
  await engine.discardChanges({ paths: ['a.txt', 'b.txt', 'new.txt'] });
  assert.equal(await fs.readFile(path.join(root, 'a.txt'), 'utf8'), 'a base\n');
  assert.equal(await fs.readFile(path.join(root, 'b.txt'), 'utf8'), 'b base\n');
  assert.equal(await fs.access(path.join(root, 'new.txt')).then(() => true, () => false), false);
  assert.deepEqual((await engine.snapshot()).files, []);
  await assert.rejects(engine.discardChanges({ paths: ['missing.txt'] }), code('UNKNOWN_PATH'));
});

test('discard refuses staged changes', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'staged\n');
  await git(root, ['add', '--', 'a.txt']);
  await assert.rejects(engine.discardChanges({ paths: ['a.txt'] }), code('STAGED_CHANGES'));
  assert.equal(await fs.readFile(path.join(root, 'a.txt'), 'utf8'), 'staged\n');
});

test('undo latest commit returns committed changes to the worktree', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'reviewed a\n');
  const snapshot = await engine.snapshot();
  const made = await engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] });
  const result = await engine.undoLastCommit({ expectedHead: made.head });
  assert.equal(result.head, snapshot.head);
  assert.equal(await git(root, ['show', 'HEAD:a.txt']), 'a base');
  assert.match(await git(root, ['status', '--porcelain=v2', '--', 'a.txt']), /\.M/);
  assert.equal(await fs.readFile(path.join(root, 'a.txt'), 'utf8'), 'reviewed a\n');
});

test('undo refuses to rewrite a commit already contained in the upstream', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'pushed change\n');
  const snapshot = await engine.snapshot();
  const made = await engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] });
  await git(root, ['update-ref', 'refs/remotes/origin/main', made.head]);
  await git(root, ['config', 'remote.origin.url', 'https://example.invalid/repo.git']);
  await git(root, ['config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*']);
  await git(root, ['config', 'branch.main.remote', 'origin']);
  await git(root, ['config', 'branch.main.merge', 'refs/heads/main']);
  await assert.rejects(engine.undoLastCommit({ expectedHead: made.head }), code('ALREADY_PUSHED'));
  assert.equal(await git(root, ['rev-parse', 'HEAD']), made.head);
});

test('amend changes only the message and keeps tree, parents, and worktree', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'reviewed a\n');
  const snapshot = await engine.snapshot();
  const made = await engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] });
  const tree = await git(root, ['rev-parse', 'HEAD^{tree}']);
  const parents = (await git(root, ['rev-list', '--parents', '-n', '1', 'HEAD'])).split(' ').slice(1).join(' ');
  const statusBefore = await git(root, ['status', '--porcelain=v2']);
  const amended = await engine.amendMessage({ expectedHead: made.head, summary: 'Better title', body: 'More detail' });
  assert.notEqual(amended.head, made.head);
  assert.equal(await git(root, ['show', '-s', '--format=%s', 'HEAD']), 'Better title');
  assert.match(await git(root, ['show', '-s', '--format=%b', 'HEAD']), /More detail/);
  assert.equal(await git(root, ['rev-parse', 'HEAD^{tree}']), tree);
  assert.equal((await git(root, ['rev-list', '--parents', '-n', '1', 'HEAD'])).split(' ').slice(1).join(' '), parents);
  assert.equal(await git(root, ['status', '--porcelain=v2']), statusBefore);
});

test('worktree change while building commits aborts entire series before HEAD moves', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'reviewed a\n'); await write(root, 'b.txt', 'reviewed b\n');
  const prepared = await plan(engine, [group(['a.txt']), group(['b.txt'])]);
  const oldHead = await head(root); const indexBefore = await fs.readFile(index);
  const original = engine._git.bind(engine); let changed = false;
  engine._git = async (repo, args, options) => {
    const result = await original(repo, args, options);
    if (args[0] === 'commit-tree' && !changed) { changed = true; await write(root, 'c.txt', 'concurrent edit\n'); }
    return result;
  };
  await assert.rejects(engine.commitGroups(prepared), code('STALE_SNAPSHOT'));
  assert.equal(await head(root), oldHead); assert.deepEqual(await fs.readFile(index), indexBefore);
  assert.equal(await cached(root, 'a.txt'), 'a base');
  assert.equal(await fs.readFile(path.join(root, 'c.txt'), 'utf8'), 'concurrent edit\n');
});

test('ABA content captured during add then restored is rejected despite matching final fingerprint', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'reviewed content\n');
  const prepared = await plan(engine, [group(['a.txt'])]);
  const oldHead = await head(root); const before = await fs.readFile(index);
  const original = engine._git.bind(engine); let injected = false;
  engine._git = async (repo, args, options) => {
    if (args[0] === 'add' && !injected) {
      injected = true;
      await write(root, 'a.txt', 'INJECTED content\n');
      const result = await original(repo, args, options);
      await write(root, 'a.txt', 'reviewed content\n');
      return result;
    }
    return original(repo, args, options);
  };
  await assert.rejects(engine.commitGroups(prepared), code('STALE_SNAPSHOT'));
  assert.equal((await engine.snapshot()).fingerprint, prepared.fingerprint);
  assert.equal(await head(root), oldHead); assert.deepEqual(await fs.readFile(index), before);
});

test('failure in second commit-tree leaves no partially applied first commit', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'a dirty\n'); await write(root, 'b.txt', 'b dirty\n');
  const prepared = await plan(engine, [group(['a.txt']), group(['b.txt'])]);
  const oldHead = await head(root); const before = await fs.readFile(index);
  const original = engine._git.bind(engine); let count = 0;
  engine._git = async (repo, args, options) => {
    if (args[0] === 'commit-tree' && ++count === 2) throw new GitEngineError('INJECTED_FAILURE', 'Test failure.');
    return original(repo, args, options);
  };
  await assert.rejects(engine.commitGroups(prepared), code('INJECTED_FAILURE'));
  assert.equal(await head(root), oldHead); assert.deepEqual(await fs.readFile(index), before);
});

test('CAS refuses a branch ref that changed immediately before update-ref', async () => {
  const { root, engine, index } = await fixture();
  await git(root, ['commit', '--allow-empty', '-m', 'Competing ref target']);
  const competitor = await head(root);
  await git(root, ['update-ref', 'refs/heads/main', await git(root, ['rev-parse', 'HEAD^']), competitor]);
  await write(root, 'a.txt', 'a dirty\n');
  const prepared = await plan(engine, [group(['a.txt'])]); const before = await fs.readFile(index);
  const original = engine._git.bind(engine); let injected = false;
  engine._git = async (repo, args, options) => {
    if (args[0] === 'update-ref' && !injected) {
      injected = true; await git(root, ['update-ref', 'refs/heads/main', competitor]);
    }
    return original(repo, args, options);
  };
  await assert.rejects(engine.commitGroups(prepared), code('GIT_FAILED'));
  assert.equal(await head(root), competitor); assert.deepEqual(await fs.readFile(index), before);
});

test('post-CAS index failure explicitly reports partial success and retains locked recovery data', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'a dirty\n');
  const prepared = await plan(engine, [group(['a.txt'])]); const oldHead = await head(root); const before = await fs.readFile(index);
  engine._installIndex = async () => { throw new Error('private failure with SECRET'); };
  let error;
  try { await engine.commitGroups(prepared); } catch (caught) { error = caught; }
  assert.ok(error instanceof GitEngineError); assert.equal(error.code, 'PARTIAL_COMMIT'); assert.equal(error.partial, true);
  assert.notEqual(await head(root), oldHead); assert.equal(await head(root), error.recovery.newHead);
  assert.deepEqual(await fs.readFile(index), before);
  assert.ok((await fs.readFile(`${index}.lock`)).length > 0);
  assert.deepEqual(await fs.readFile(error.recovery.originalIndex), before);
  assert.equal(JSON.parse(await fs.readFile(path.join(error.recovery.directory, 'recovery.json'), 'utf8')).oldHead, oldHead);
  assert.doesNotMatch(error.message, /SECRET/);
});

test('existing index lock is not removed or overwritten', async () => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'dirty\n'); const prepared = await plan(engine, [group(['a.txt'])]);
  await fs.writeFile(`${index}.lock`, 'other owner');
  await assert.rejects(engine.commitGroups(prepared), code('INDEX_LOCKED'));
  assert.equal(await fs.readFile(`${index}.lock`, 'utf8'), 'other owner');
});

test('invalid, duplicate, unknown, traversal and absolute assignments cannot change HEAD or index', async (t) => {
  const { root, engine, index } = await fixture();
  await write(root, 'a.txt', 'dirty\n'); const snapshot = await engine.snapshot();
  const before = await fs.readFile(index); const oldHead = await head(root);
  const cases = [
    [[], 'INVALID_GROUPS'], [[group([])], 'INVALID_GROUP'], [[group(['a.txt'], 'bad\ntitle')], 'INVALID_GROUP'],
    [[group(['a.txt', 'a.txt'])], 'DUPLICATE_PATH'], [[group(['a.txt']), group(['a.txt'])], 'DUPLICATE_PATH'],
    [[group(['missing'])], 'UNKNOWN_PATH'], [[group(['b.txt'])], 'UNKNOWN_PATH'],
    [[group(['../outside'])], 'UNSAFE_PATH'], [[group(['/etc/passwd'])], 'UNSAFE_PATH'],
    [[group(['.git/config'])], 'UNSAFE_PATH'], [[group(['a\0.txt'])], 'UNSAFE_PATH'], [[group(['dir/../a.txt'])], 'UNSAFE_PATH'],
  ];
  for (const [groups, expected] of cases) await t.test(expected, async () => {
    await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups }), code(expected));
    assert.deepEqual(await fs.readFile(index), before); assert.equal(await head(root), oldHead);
  });
});

test('environment, credential and private key paths are flagged and rejected by default', async (t) => {
  const { root, engine } = await fixture();
  const names = ['.env', '.env.production', 'nested/credentials.json', 'keys/private.pem', '.ssh/id_ed25519', '.aws/config', '.npmrc', 'service-account.json'];
  for (const name of names) await write(root, name, 'DUMMY TEST DATA\n');
  const snapshot = await engine.snapshot();
  for (const name of names) await t.test(name, async () => {
    assert.equal(snapshot.files.find((file) => file.path === name).sensitive, true);
    await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group([name])] }), code('SENSITIVE_PATH'));
  });
});

test('hooks are bypassed like GitHub Desktop and reported; signing is still refused', async (t) => {
  for (const kind of ['hook', 'hooksPath']) await t.test(kind, async () => {
    const { root, engine } = await fixture(); await write(root, 'a.txt', 'dirty\n');
    if (kind === 'hook') { await write(root, '.git/hooks/pre-commit', '#!/bin/sh\ntouch EXECUTED\n'); await fs.chmod(path.join(root, '.git/hooks/pre-commit'), 0o755); }
    if (kind === 'hooksPath') await git(root, ['config', 'core.hooksPath', '/dev/null']);
    const result = await engine.commitGroups(await plan(engine, [group(['a.txt'])]));
    assert.ok(result.warnings.some((warning) => warning.code === 'HOOKS_SKIPPED'));
    assert.equal(await fs.access(path.join(root, 'EXECUTED')).then(() => true, () => false), false);
  });
  const { root, engine } = await fixture(); await write(root, 'a.txt', 'dirty\n');
  await git(root, ['config', 'commit.gpgSign', 'true']);
  await assert.rejects(engine.commitGroups(await plan(engine, [group(['a.txt'])])), code('SIGNING_CONFIGURED'));
});

test('review refuses external content filters; fsmonitor and external diff are never executed', async () => {
  const { root, engine } = await fixture(); await write(root, 'a.txt', 'dirty\n');
  await git(root, ['config', 'filter.danger.clean', 'touch FILTER_EXECUTED']);
  await engine.snapshot(); // An unused global/LFS-style driver is harmless.
  await write(root, '.gitattributes', '*.txt filter=danger\n');
  await assert.rejects(engine.snapshot(), code('FILTERS_CONFIGURED'));
  assert.equal(await fs.access(path.join(root, 'FILTER_EXECUTED')).then(() => true, () => false), false);
  await git(root, ['config', '--unset', 'filter.danger.clean']);
  await write(root, '.git/evil-command', '#!/bin/sh\ntouch EXTERNAL_EXECUTED\n');
  await fs.chmod(path.join(root, '.git/evil-command'), 0o755);
  await git(root, ['config', 'core.fsmonitor', path.join(root, '.git/evil-command')]);
  await git(root, ['config', 'diff.external', path.join(root, '.git/evil-command')]);
  await engine.snapshot(); await engine.diff({ path: 'a.txt' });
  assert.equal(await fs.access(path.join(root, 'EXTERNAL_EXECUTED')).then(() => true, () => false), false);
});

test('merge conflicts and rebase states are detected and mutations refused', async (t) => {
  await t.test('merge', async () => {
    const { root, engine, index } = await fixture();
    await git(root, ['checkout', '-b', 'side']); await write(root, 'a.txt', 'side\n'); await git(root, ['commit', '-am', 'Side']);
    await git(root, ['checkout', 'main']); await write(root, 'a.txt', 'main\n'); await git(root, ['commit', '-am', 'Main']);
    await git(root, ['merge', 'side'], { allowed: [0, 1] });
    const snapshot = await engine.snapshot(); assert.ok(snapshot.states.includes('MERGE_HEAD'));
    assert.equal(snapshot.files.find((file) => file.path === 'a.txt').conflict, true);
    const before = await fs.readFile(index);
    await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] }), code('OPERATION_IN_PROGRESS'));
    assert.deepEqual(await fs.readFile(index), before);
  });
  await t.test('rebase', async () => {
    const { root, engine } = await fixture(); await write(root, 'a.txt', 'dirty\n');
    await fs.mkdir(path.join(root, '.git/rebase-merge'));
    const snapshot = await engine.snapshot(); assert.ok(snapshot.states.includes('rebase-merge'));
    await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] }), code('OPERATION_IN_PROGRESS'));
  });
});

test('dirty submodule contents affect fingerprint and cannot be group committed', async () => {
  const source = await fixture({ 'inside.txt': 'inside\n' });
  const { root, engine } = await fixture();
  await git(root, ['-c', 'protocol.file.allow=always', 'submodule', 'add', source.root, 'nested module']);
  await git(root, ['commit', '-am', 'Add submodule']);
  await write(root, 'nested module/inside.txt', 'first dirty\n');
  const snapshot = await engine.snapshot();
  assert.equal(snapshot.files.find((file) => file.path === 'nested module').submodule, true);
  await write(root, 'nested module/inside.txt', 'other dirty\n');
  assert.notEqual((await engine.snapshot()).fingerprint, snapshot.fingerprint);
  await assert.rejects(engine.commitGroups(await plan(engine, [group(['nested module'])])), code('SUBMODULES'));
});

test('rename records retain original paths and staged renames are never overwritten', async () => {
  const { root, engine } = await fixture();
  await git(root, ['mv', '--', 'a.txt', 'renamed file.txt']);
  const snapshot = await engine.snapshot();
  const renamed = snapshot.files.find((file) => file.path === 'renamed file.txt');
  assert.equal(renamed.originalPath, 'a.txt'); assert.equal(renamed.staged, true);
  assert.match((await engine.diff({ path: renamed.path })).text, /a base/);
  await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group([renamed.path])] }), code('STAGED_CHANGES'));
});

test('diff UI truncation is explicit and historical full-commit diffs work', async () => {
  const { root, engine } = await fixture();
  await write(root, 'large.txt', 'long review line\n'.repeat(30_000));
  const diff = await engine.diff({ path: 'large.txt' });
  assert.equal(diff.truncated, true); assert.match(diff.text, /Diff truncated/);
  assert.ok(Buffer.byteLength(diff.text) < diff.limits.maxBytes + 200);
  assert.ok(diff.text.split('\n').length < diff.limits.maxLines + 5);
  await assert.rejects(engine.diff({ commit: 'HEAD~1' }), code('INVALID_COMMIT'));
  await assert.rejects(engine.diff({ path: '../outside' }), code('UNSAFE_PATH'));
  await assert.rejects(engine.diff({}), code('INVALID_PATH'));
  await assert.rejects(engine.history({ limit: 1000 }), code('INVALID_LIMIT'));
});

test('checkout requires reviewed HEAD, a clean tree, existing branch and no hooks', async () => {
  const { root, engine } = await fixture();
  const initial = await head(root); await git(root, ['branch', 'other']);
  await assert.rejects(engine.checkout({ branch: 'other' }), code('EXPECTED_HEAD_REQUIRED'));
  await assert.rejects(engine.checkout({ branch: 'other', expectedHead: '0'.repeat(40) }), code('STALE_HEAD'));
  await assert.rejects(engine.checkout({ branch: '--detach', expectedHead: initial }), code('INVALID_BRANCH'));
  await assert.rejects(engine.checkout({ branch: 'missing', expectedHead: initial }), code('UNKNOWN_BRANCH'));
  await write(root, 'a.txt', 'dirty\n');
  await assert.rejects(engine.checkout({ branch: 'other', expectedHead: initial }), code('DIRTY_WORKTREE'));
  await write(root, 'a.txt', 'a base\n');
  assert.equal((await engine.checkout({ branch: 'other', expectedHead: initial })).branch, 'other');
  assert.equal((await engine.snapshot()).branch, 'other');
  await write(root, '.git/hooks/post-checkout', '#!/bin/sh\ntouch CHECKOUT_HOOK\n'); await fs.chmod(path.join(root, '.git/hooks/post-checkout'), 0o755);
  const switched = await engine.checkout({ branch: 'main', expectedHead: await head(root) });
  assert.equal(switched.branch, 'main');
  assert.ok(switched.warnings.some((warning) => warning.code === 'HOOKS_SKIPPED'));
  assert.equal(await fs.access(path.join(root, 'CHECKOUT_HOOK')).then(() => true, () => false), false);
});

async function remoteFixture() {
  const result = await fixture();
  const remote = await fs.mkdtemp(path.join(temporary, 'remote-'));
  await git(remote, ['init', '--bare', '-b', 'main']);
  await git(result.root, ['remote', 'add', 'origin', remote]);
  await git(result.root, ['config', 'branch.main.remote', 'origin']);
  await git(result.root, ['config', 'branch.main.merge', 'refs/heads/review-target']);
  return { ...result, remote };
}

test('push is explicit, non-force, single configured upstream, with no tags or extra refspecs', async () => {
  const { root, engine, remote } = await remoteFixture();
  const initial = await head(root);
  await git(root, ['config', 'push.followTags', 'true']);
  await git(root, ['tag', '-a', 'do-not-push', '-m', 'Do not push']);
  await git(root, ['config', 'remote.origin.push', 'HEAD:refs/heads/WRONG']);
  const result = await pushReviewed(engine, initial);
  assert.equal(result.forced, false); assert.equal(result.branch, 'review-target');
  assert.equal(await git(remote, ['rev-parse', 'refs/heads/review-target']), initial);
  assert.equal(await git(remote, ['for-each-ref', '--format=%(refname)']), 'refs/heads/review-target');
  assert.equal(await head(root), initial);
  const snapshot = await engine.snapshot(); assert.equal(snapshot.pushTarget.ref, 'refs/heads/review-target');
  assert.ok(result.warnings.some((warning) => warning.code === 'TRACKING_REFS_UNCHANGED'));
  assert.equal(await git(root, ['for-each-ref', '--format=%(refname)', 'refs/remotes/']), '');
  await git(root, ['commit', '--allow-empty', '-m', 'Local new commit']);
  await assert.rejects(pushReviewed(engine, initial), code('STALE_HEAD'));
  assert.equal(await git(remote, ['rev-parse', 'refs/heads/review-target']), initial);
});

test('non-fast-forward push fails without overwriting remote or local HEAD', async () => {
  const { root, engine, remote } = await remoteFixture();
  await pushReviewed(engine, await head(root));
  const other = await fs.mkdtemp(path.join(temporary, 'other-'));
  await git(other, ['clone', '-b', 'review-target', remote, '.']);
  await git(other, ['config', 'user.name', 'Other']); await git(other, ['config', 'user.email', 'other@example.invalid']);
  await git(other, ['config', 'commit.gpgSign', 'false']);
  await git(other, ['commit', '--allow-empty', '-m', 'Remote divergent commit']);
  await git(other, ['push', 'origin', 'HEAD:refs/heads/review-target']);
  await git(root, ['commit', '--allow-empty', '-m', 'Local divergent commit']);
  const local = await head(root); const remoteHead = await head(other);
  await assert.rejects(pushReviewed(engine, local), code('PUSH_FAILED'));
  assert.equal(await head(root), local); assert.equal(await git(remote, ['rev-parse', 'refs/heads/review-target']), remoteHead);
});

test('unsafe transports, embedded credentials, mirrors and custom commands are refused', async (t) => {
  for (const kind of ['ext', 'credentials', 'mirror', 'receivepack', 'sshCommand', 'multiple']) await t.test(kind, async () => {
    const { root, engine } = await remoteFixture();
    if (kind === 'ext') await git(root, ['remote', 'set-url', 'origin', 'ext::touch PWNED']);
    if (kind === 'credentials') await git(root, ['remote', 'set-url', 'origin', 'https://name:SUPERSECRET@example.invalid/repo']);
    if (kind === 'mirror') await git(root, ['config', 'remote.origin.mirror', 'true']);
    if (kind === 'receivepack') await git(root, ['config', 'remote.origin.receivepack', 'touch PWNED']);
    if (kind === 'sshCommand') await git(root, ['config', 'core.sshCommand', 'touch PWNED']);
    if (kind === 'multiple') { await git(root, ['remote', 'set-url', '--add', '--push', 'origin', '/tmp/dummy-one']); await git(root, ['remote', 'set-url', '--add', '--push', 'origin', '/tmp/dummy-two']); }
    await assert.rejects(pushReviewed(engine, await head(root)), (error) => {
      assert.equal(error.code, 'UNSAFE_REMOTE');
      assert.doesNotMatch(JSON.stringify(error), /SUPERSECRET|touch PWNED/); return true;
    });
    assert.equal(await fs.access(path.join(root, 'PWNED')).then(() => true, () => false), false);
  });
});

test('pre-push hooks are bypassed and reported rather than executed', async () => {
  const { root, engine } = await remoteFixture();
  await write(root, '.git/hooks/pre-push', '#!/bin/sh\ntouch PWNED\n');
  await fs.chmod(path.join(root, '.git/hooks/pre-push'), 0o755);
  const result = await pushReviewed(engine, await head(root));
  assert.ok(result.warnings.some((warning) => warning.code === 'HOOKS_SKIPPED'));
  assert.equal(await fs.access(path.join(root, 'PWNED')).then(() => true, () => false), false);
});

test('standard SSH push uses fixed noninteractive transport without networking in tests', async (t) => {
  for (const url of ['git@github.com:example/repo.git', 'ssh://git@github.com:2222/example/repo.git']) await t.test(url, async () => {
    const { root, engine } = await remoteFixture();
    await git(root, ['remote', 'set-url', 'origin', url]);
    const original = engine._git.bind(engine); let captured;
    engine._git = async (repo, args, options) => {
      if (args.includes('push') && args.includes('--porcelain')) { captured = { args, options }; return { stdout: Buffer.alloc(0), exitCode: 0 }; }
      return original(repo, args, options);
    };
    const initial = await head(root); await pushReviewed(engine, initial);
    assert.ok(captured); assert.ok(captured.args.includes(`${initial}:refs/heads/review-target`));
    assert.ok(captured.args.includes('credential.helper=')); assert.ok(captured.args.includes('protocol.ssh.allow=always'));
    assert.equal(captured.args.some((arg) => arg.startsWith('--force') || arg.startsWith('+')), false);
    assert.match(captured.options.env.GIT_SSH_COMMAND, /BatchMode=yes/);
    assert.match(captured.options.env.GIT_SSH_COMMAND, /StrictHostKeyChecking=yes/);
    assert.match(captured.options.env.GIT_SSH_COMMAND, /-F \/dev\/null/);
    assert.match(captured.options.env.GIT_SSH_COMMAND, /UpdateHostKeys=no/);
  });
});

test('public validation and non-repository errors do not expose arbitrary stderr', async () => {
  assert.throws(() => new GitEngine({}), code('INVALID_CWD'));
  const empty = await fs.mkdtemp(path.join(temporary, 'not-repo-'));
  await assert.rejects(createGitEngine({ cwd: empty }).snapshot(), code('NOT_REPOSITORY'));
  const { engine } = await fixture();
  await assert.rejects(engine.commitGroups({ groups: [] }), code('FINGERPRINT_REQUIRED'));
  await assert.rejects(engine.push({}), code('EXPECTED_HEAD_REQUIRED'));
});

test('push requires an approved destination fingerprint and rejects URL/upstream changes at unchanged HEAD', async (t) => {
  for (const kind of ['missing', 'url', 'ref', 'transport']) await t.test(kind, async () => {
    const { root, engine, remote } = await remoteFixture();
    const snapshot = await engine.snapshot();
    assert.equal(snapshot.pushTarget.remote, 'origin'); assert.equal(snapshot.pushTarget.ref, 'refs/heads/review-target');
    if (kind === 'url') await git(root, ['remote', 'set-url', 'origin', path.join(temporary, 'other-destination')]);
    if (kind === 'ref') await git(root, ['config', 'branch.main.merge', 'refs/heads/other']);
    if (kind === 'transport') await git(root, ['config', 'http.proxy', 'http://example.invalid:8080']);
    await assert.rejects(engine.push({ expectedHead: snapshot.head, ...(kind === 'missing' ? {} : { expectedTarget: snapshot.pushTarget.fingerprint }) }),
      code(kind === 'missing' ? 'EXPECTED_TARGET_REQUIRED' : 'STALE_PUSH_TARGET'));
    assert.equal(await git(remote, ['for-each-ref', '--format=%(refname)']), '');
  });
});

test('push target display redacts credentials and raw config values never appear in snapshots', async () => {
  const { root, engine } = await remoteFixture();
  await git(root, ['remote', 'set-url', 'origin', 'https://SECRETUSER:SECRETPASSWORD@example.invalid/repo?token=SECRETTOKEN']);
  const snapshot = await engine.snapshot();
  assert.equal(snapshot.pushTarget.displayUrl, 'https://example.invalid/repo');
  assert.doesNotMatch(JSON.stringify(snapshot), /SECRETUSER|SECRETPASSWORD|SECRETTOKEN/);
  await assert.rejects(engine.push({ expectedHead: snapshot.head, expectedTarget: snapshot.pushTarget.fingerprint }), code('UNSAFE_REMOTE'));
});

test('transient alternate URL reads cannot pass a restored destination fingerprint', async () => {
  const { engine } = await remoteFixture();
  const snapshot = await engine.snapshot();
  const original = engine._git.bind(engine); let reads = 0, pushed = false;
  engine._git = async (repo, args, options) => {
    const result = await original(repo, args, options);
    if (args[0] === 'remote' && args[1] === 'get-url' && ++reads === 2) return { ...result, stdout: Buffer.from('/an/unreviewed/destination\n') };
    if (args.includes('push') && args.includes('--porcelain')) pushed = true;
    return result;
  };
  await assert.rejects(engine.push({ expectedHead: snapshot.head, expectedTarget: snapshot.pushTarget.fingerprint }), code('STALE_PUSH_TARGET'));
  assert.equal(pushed, false);
});

test('late insteadOf configuration cannot redirect frozen push destination', async () => {
  const { root, engine, remote } = await remoteFixture();
  const wrong = await fs.mkdtemp(path.join(temporary, 'wrong-remote-'));
  await git(wrong, ['init', '--bare', '-b', 'main']);
  const snapshot = await engine.snapshot(); const original = engine._git.bind(engine); let injected = false;
  engine._git = async (repo, args, options) => {
    if (args.includes('push') && args.includes('--porcelain')) {
      injected = true;
      assert.ok(args.includes(remote)); assert.equal(args.includes('origin'), false);
      await git(root, ['config', `url.${wrong}.insteadOf`, remote]);
    }
    return original(repo, args, options);
  };
  await engine.push({ expectedHead: snapshot.head, expectedTarget: snapshot.pushTarget.fingerprint });
  assert.equal(injected, true);
  assert.equal(await git(remote, ['rev-parse', 'refs/heads/review-target']), snapshot.head);
  assert.equal(await git(wrong, ['for-each-ref', '--format=%(refname)']), '');
});

test('checkout checks destination attributes before any target smudge filter can execute', async () => {
  const { root, engine } = await fixture();
  await git(root, ['checkout', '-b', 'filtered']);
  await write(root, '.gitattributes', '*.txt filter=danger\n'); await git(root, ['add', '.gitattributes']); await git(root, ['commit', '-m', 'Target attributes']);
  await git(root, ['checkout', 'main']);
  await git(root, ['config', 'filter.danger.smudge', 'touch FILTER_EXECUTED']);
  const snapshot = await engine.snapshot();
  await assert.rejects(engine.checkout({ branch: 'filtered', expectedHead: snapshot.head }), code('FILTERS_CONFIGURED'));
  assert.equal(await git(root, ['branch', '--show-current']), 'main');
  assert.equal(await fs.access(path.join(root, 'FILTER_EXECUTED')).then(() => true, () => false), false);
});

test('active submodule filters are refused before recursive status can execute them', async () => {
  const source = await fixture({ 'inside.txt': 'inside\n' });
  const { root, engine } = await fixture();
  await git(root, ['-c', 'protocol.file.allow=always', 'submodule', 'add', source.root, 'module']);
  await git(root, ['commit', '-am', 'Add submodule']);
  await write(root, 'module/.gitattributes', '*.txt filter=danger\n');
  await git(path.join(root, 'module'), ['config', 'filter.danger.clean', 'touch FILTER_EXECUTED']);
  await assert.rejects(engine.snapshot(), code('FILTERS_CONFIGURED'));
  assert.equal(await fs.access(path.join(root, 'module/FILTER_EXECUTED')).then(() => true, () => false), false);
});

test('unrelated intent-to-add index entries remain intent-to-add and are not committed', async () => {
  const { root, engine } = await fixture();
  await write(root, 'a.txt', 'reviewed\n'); await write(root, 'pending.txt', 'pending\n');
  await git(root, ['add', '-N', '--', 'pending.txt']);
  const indexEntry = await git(root, ['ls-files', '--stage', '--', 'pending.txt']);
  const snapshot = await engine.snapshot();
  assert.equal(snapshot.files.find((file) => file.path === 'pending.txt').staged, false);
  await engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] });
  assert.equal(await git(root, ['ls-tree', 'HEAD', '--', 'pending.txt']), '');
  assert.equal(await git(root, ['ls-files', '--stage', '--', 'pending.txt']), indexEntry);
  assert.equal(await git(root, ['diff', '--cached', '--name-only']), '');
  assert.equal(await fs.readFile(path.join(root, 'pending.txt'), 'utf8'), 'pending\n');
});

test('uncertain update-ref success is resolved without retrying or losing index state', async () => {
  const { root, engine } = await fixture(); await write(root, 'a.txt', 'reviewed\n');
  const prepared = await plan(engine, [group(['a.txt'])]); const original = engine._git.bind(engine); let updates = 0;
  engine._git = async (repo, args, options) => {
    const result = await original(repo, args, options);
    if (args[0] === 'update-ref') { updates++; throw new GitEngineError('GIT_TIMEOUT', 'Test timeout.', { mayHaveSucceeded: true }); }
    return result;
  };
  const result = await engine.commitGroups(prepared);
  assert.equal(updates, 1); assert.equal(await head(root), result.head);
  assert.equal(await git(root, ['diff', '--cached', '--name-only']), '');
  assert.equal(await cached(root, 'a.txt'), 'reviewed');
});

test('assume-unchanged hidden contents are fingerprinted without changing index flags', async () => {
  const { root, engine } = await fixture();
  await git(root, ['update-index', '--assume-unchanged', 'b.txt']);
  await write(root, 'a.txt', 'reviewed\n');
  const snapshot = await engine.snapshot();
  assert.ok(snapshot.warnings.some((warning) => warning.code === 'INDEX_FLAGS'));
  await write(root, 'b.txt', 'hidden concurrent edit\n');
  assert.notEqual((await engine.snapshot()).fingerprint, snapshot.fingerprint);
  await assert.rejects(engine.commitGroups({ fingerprint: snapshot.fingerprint, groups: [group(['a.txt'])] }), code('STALE_SNAPSHOT'));
  assert.match(await git(root, ['ls-files', '-v', '--', 'b.txt']), /^h /);
});

test('lock cleanup failure after success reports applied commits and retained recovery', async () => {
  const { root, engine } = await fixture(); await write(root, 'a.txt', 'reviewed\n');
  const prepared = await plan(engine, [group(['a.txt'])]); const release = engine._releaseLock.bind(engine);
  engine._releaseLock = async (lock, preserve) => {
    if (lock?.file.endsWith('HEAD.lock')) { await lock.handle.close(); throw new Error('SECRET cleanup diagnostic'); }
    return release(lock, preserve);
  };
  await assert.rejects(engine.commitGroups(prepared), (error) => {
    assert.equal(error.code, 'PARTIAL_COMMIT'); assert.equal(error.partial, true);
    assert.equal(error.recovery.indexInstalled, true); assert.doesNotMatch(error.message, /SECRET/); return true;
  });
  assert.equal(await git(root, ['diff', '--cached', '--name-only']), '');
  assert.equal(await git(root, ['show', 'HEAD:a.txt']), 'reviewed');
});

test('concurrent symbolic HEAD switch after validation retains original index and reports recovery', async () => {
  const { root, engine, index } = await fixture();
  await git(root, ['branch', 'other']); await write(root, 'a.txt', 'reviewed\n');
  const prepared = await plan(engine, [group(['a.txt'])]); const original = engine._git.bind(engine); const before = await fs.readFile(index);
  engine._git = async (repo, args, options) => {
    if (args[0] === 'update-ref') await git(root, ['symbolic-ref', 'HEAD', 'refs/heads/other']);
    return original(repo, args, options);
  };
  await assert.rejects(engine.commitGroups(prepared), (error) => {
    assert.equal(error.code, 'PARTIAL_COMMIT'); assert.equal(error.partial, true); assert.equal(error.recovery.ref, 'refs/heads/main'); return true;
  });
  assert.deepEqual(await fs.readFile(index), before);
  assert.equal(await git(root, ['branch', '--show-current']), 'other');
  assert.equal(await fs.access(`${index}.lock`).then(() => true, () => false), true);
});
