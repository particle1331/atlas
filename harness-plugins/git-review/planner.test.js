import test from 'node:test';
import assert from 'node:assert/strict';
import { PLANNER_LIMITS, PlannerError, isSensitivePath, collectRecentSessions, organizeChanges, validatePlan } from './planner.js';

const ROOT = '/repo';
const selection = { provider: 'mock-provider', model: 'mock-model', reasoningEffort: 'low' };
const user = (text, time = 10, seq = time) => ({ type: 'user/message', seq, time, data: { role: 'user', content: [{ type: 'text', text }] } });
const assistant = (text, turn = 1, time = 20, extra = {}) => ({ type: 'assistant/message', seq: time, time, data: { turn, message: { role: 'assistant', content: [{ type: 'text', text }] }, ...extra } });
const end = (turn = 1, time = 21, kind = 'completed') => ({ type: 'turn/end', seq: time, time, data: { turn, reason: { kind } } });
const header = (id = 's1', cwd = ROOT, createdAt = 1) => ({ id, cwd, createdAt });
const session = (id = 's1', events = [user('Update search'), assistant('Updated search'), end()], cwd = ROOT) => ({ session: header(id, cwd), events, inheritedEventCount: 0 });
const rootResolver = async directory => directory === '/repo/foreign' || directory.startsWith('/repo/foreign/') ? '/repo/foreign' : directory === '/elsewhere' || directory.startsWith('/elsewhere/') ? '/elsewhere' : directory === '/repo' || directory.startsWith('/repo/') || directory === '/alias' ? ROOT : null;
const source = (id = 's1', text = 'Update search', extra = {}) => ({ id, root: ROOT, title: 'Search', excerpts: [{ role: 'user', text }], touchedPaths: [], mentionedPaths: [], warnings: [], ...extra });
const proposal = (paths = ['src/search.js'], sessionIds = []) => ({ groups: [{ title: 'Improve search', body: 'Keep search behavior and tests together.', rationale: 'These files implement the same search change.', paths, sessionIds, warnings: [] }], warnings: [] });
const snapshot = (files = ['src/search.js']) => ({ root: ROOT, files: files.map(file => typeof file === 'string' ? { path: file, status: 'M' } : file) });

function fakeLlm(value, options = {}) {
  const calls = [];
  return {
    calls,
    async *stream(request) {
      calls.push(request);
      if (options.throw) throw new Error('Provider secret error text must not leak');
      if (options.before) options.before(request);
      const text = typeof value === 'string' ? value : JSON.stringify(value);
      yield { type: 'reasoning-delta', text: 'Private chain of thought must not be included' };
      yield { type: 'text-delta', text: text.slice(0, Math.ceil(text.length / 2)) };
      yield { type: 'text-delta', text: text.slice(Math.ceil(text.length / 2)) };
      if (!options.noFinish) yield { type: 'finish', reason: { kind: options.finish || 'stop', failure: { message: 'Provider failure secret' } } };
      if (options.afterFinish) yield { type: 'text-delta', text: 'unexpected' };
    },
  };
}

function promptData(llm) {
  const text = llm.calls[0].messages[0].content[0].text;
  return JSON.parse(text.slice(text.indexOf('\n') + 1));
}

function queryFor(snapshots) {
  const reads = [];
  const titles = [];
  return {
    reads, titles,
    async listSessions() { return snapshots.map(item => ({ header: item.session })); },
    async listEvents(id) { return snapshots.find(item => item.session.id === id).events.map(({ type, seq, time }) => ({ type, seq, time })); },
    async readSession(id) { reads.push(id); return snapshots.find(item => item.session.id === id); },
    async readTitle(id) { titles.push(id); return { title: `Title ${id}` }; },
  };
}

async function organize(options = {}) {
  const llm = options.llm || fakeLlm(proposal());
  const result = await organizeChanges({ snapshot: snapshot(), diffs: [{ path: 'src/search.js', text: '+ improveSearch()' }], sessions: [], llm, selection, ...options });
  return { result, llm };
}

function codeIs(code) { return error => error instanceof PlannerError && error.code === code; }

test('uses injected LLM stream and produces a coherent whole-file plan', async () => {
  const llm = fakeLlm(proposal(['src/search.js', 'test/search.test.js', 'docs/search.md'], ['s1']));
  const { result } = await organize({ snapshot: snapshot(['src/search.js', 'test/search.test.js', 'docs/search.md']), sessions: [source()], llm });
  assert.equal(result.groups.length, 1);
  assert.equal('targetCount' in result, false);
  assert.deepEqual(result.groups[0].sessionIds, ['s1']);
  assert.equal(result.sourceSessions[0].id, 's1');
  assert.match(result.warnings.join(' '), /Whole-file/);
  const request = llm.calls[0];
  assert.equal(request.provider, selection.provider);
  assert.equal(request.model, selection.model);
  assert.equal(request.reasoningEffort, 'low');
  assert.equal(request.maxTokens, PLANNER_LIMITS.maxTokens);
  assert.deepEqual(request.tools, []);
  assert.match(request.system, /UNTRUSTED DATA/);
  assert.match(request.system, /Let the changes decide the number of groups/);
  assert.match(request.system, /between 1 and 10/);
  assert.match(request.system, /Metadata-only/);
  assert.match(request.system, /mixed-file/);
  assert.equal(promptData(llm).eligibleFiles.length, 3);
});

test('group count comes from the changes with a hard cap of ten, not a requested count', async () => {
  const { llm } = await organize();
  assert.equal('targetCount' in promptData(llm), false);
  assert.equal(promptData(llm).maxGroups, 10);
  const files = Array.from({ length: 11 }, (_, index) => `src/file${index}.js`);
  const groups = files.map(file => ({ title: file, body: '', rationale: '', paths: [file], sessionIds: [], warnings: [] }));
  await assert.rejects(() => organize({ snapshot: snapshot(files), llm: fakeLlm({ groups, warnings: [] }) }), codeIs('INVALID_PLAN'));
});

test('sensitive names are conservatively detected including credentials and key stores', () => {
  for (const value of ['.env', '.env.local', 'deploy/.ENV.production', '.aws/config', '.ssh/id_ed25519', '.npmrc', 'credentials.json', 'secret.yaml', 'cert/server.key', 'keys/client.pem', 'service-account-prod.json', 'id_rsa.pub']) assert.equal(isSensitivePath(value), true, value);
  for (const value of ['src/search.js', 'docs/security.md', 'assets/cover.png', 'content/posts/notebook.ipynb']) assert.equal(isSensitivePath(value), false, value);
});

test('excludes sensitive, conflicted, submodule and explicitly excluded rows without leaking content', async () => {
  const files = ['src/search.js', '.env', { path: 'config/public.json', originalPath: '.env.local' }, { path: 'merge.txt', conflict: true }, { path: 'vendor/repo', submodule: true }, { path: 'skip.txt', eligible: false }];
  const { result, llm } = await organize({ snapshot: snapshot(files), diffs: files.map(file => ({ path: typeof file === 'string' ? file : file.path, text: 'SENSITIVE-RAW-CONTENT' })) });
  assert.deepEqual(result.unassigned, ['.env', 'config/public.json', 'merge.txt', 'vendor/repo', 'skip.txt']);
  assert.deepEqual(promptData(llm).eligibleFiles.map(file => file.path), ['src/search.js']);
  assert.equal(promptData(llm).eligibleFiles[0].evidence, 'SENSITIVE-RAW-CONTENT');
  assert.equal(promptData(llm).evidenceWarnings.filter(item => /Unassigned/.test(item)).length, 5);
  const onlySensitiveLlm = fakeLlm('should not call');
  const empty = await organizeChanges({ snapshot: snapshot(['.env']), llm: onlySensitiveLlm, selection });
  assert.deepEqual(empty.groups, []);
  assert.equal(onlySensitiveLlm.calls.length, 0);
});

test('does not send sensitive diff bodies even when entries were supplied', async () => {
  const { llm } = await organize({ snapshot: snapshot(['src/search.js', '.env']), diffs: [{ path: 'src/search.js', text: '+ safe' }, { path: '.env', text: 'DO-NOT-SEND-THIS-CREDENTIAL' }] });
  assert.doesNotMatch(llm.calls[0].messages[0].content[0].text, /DO-NOT-SEND/);
});

test('redacts high-confidence credentials in diffs and session text', async () => {
  const token = 'ghp_' + 'X'.repeat(30);
  const { result, llm } = await organize({ diffs: [{ path: 'src/search.js', text: `+ token=${token}\n+ password=supersecret123\n+ -----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----` }], sessions: [source('s1', `api_key=abcdefghijk ${token}`)] });
  const input = llm.calls[0].messages[0].content[0].text;
  assert.doesNotMatch(input, /supersecret123|abcdefghijk|ghp_XXX|BEGIN PRIVATE KEY/);
  assert.match(input, /REDACTED POSSIBLE SECRET/);
  assert.match(result.warnings.join(' '), /redacted/i);
});

test('rejects malformed JSON and prose/code-fenced responses without repair', async () => {
  for (const response of ['', '{"groups":', '```json\n' + JSON.stringify(proposal()) + '\n```', 'Here is a plan: ' + JSON.stringify(proposal())]) await assert.rejects(() => organize({ llm: fakeLlm(response) }), codeIs('INVALID_PLAN'));
});

test('strictly validates complete partition, exact paths, sources and schema', async () => {
  const invalid = [];
  invalid.push({ ...proposal(), groups: [] });
  invalid.push(proposal([]));
  invalid.push(proposal(['src/made-up.js']));
  invalid.push(proposal(['src/search.js', 'src/search.js']));
  invalid.push(proposal(['src/search.js'], ['invented-session']));
  invalid.push({ ...proposal(), extra: 'no' });
  invalid.push({ ...proposal(), warnings: 'not-an-array' });
  invalid.push({ groups: [{ ...proposal().groups[0], hunks: ['invented-hunk'] }], warnings: [] });
  invalid.push({ groups: [{ ...proposal().groups[0], title: 'x'.repeat(101) }], warnings: [] });
  invalid.push({ groups: [{ ...proposal().groups[0], title: 'line one\nline two' }], warnings: [] });
  invalid.push({ groups: [{ ...proposal().groups[0], body: 'x'.repeat(901) }], warnings: [] });
  invalid.push({ groups: [{ ...proposal().groups[0], rationale: '' }], warnings: [] });
  invalid.push({ groups: [{ ...proposal().groups[0], warnings: Array(9).fill('warning') }], warnings: [] });
  for (const value of invalid) await assert.rejects(() => organize({ llm: fakeLlm(value) }), codeIs('INVALID_PLAN'));
  await assert.rejects(() => organize({ snapshot: snapshot(['src/search.js', 'test/search.test.js']) }), codeIs('INVALID_PLAN'));
  const two = proposal();
  two.groups.push({ ...two.groups[0] });
  await assert.rejects(() => organize({ llm: fakeLlm(two) }), codeIs('INVALID_PLAN'));
});

test('source citations must be from actually supplied and root-verified excerpts', async () => {
  await assert.rejects(() => organize({ sessions: [source('foreign', 'OTHER-REPOSITORY-CONTENT', { root: '/other' })], llm: fakeLlm(proposal(['src/search.js'], ['foreign'])) }), codeIs('INVALID_PLAN'));
  const { llm } = await organize({ sessions: [source('foreign', 'OTHER-REPOSITORY-CONTENT', { root: '/other' }), source('empty', '', { excerpts: [] })] });
  assert.deepEqual(promptData(llm).sessions, []);
  assert.doesNotMatch(llm.calls[0].messages[0].content[0].text, /OTHER-REPOSITORY-CONTENT/);
  await assert.rejects(() => organize({ sessions: [source()], llm: fakeLlm(proposal(['src/search.js'], ['s1', 's1'])) }), codeIs('INVALID_PLAN'));
});

test('fails closed for terminal error, aborted, max-token, missing or unexpected finish', async () => {
  for (const finish of ['error', 'max-tokens', 'tool-calls']) await assert.rejects(() => organize({ llm: fakeLlm(proposal(), { finish }) }), codeIs('MODEL_FAILED'));
  await assert.rejects(() => organize({ llm: fakeLlm(proposal(), { finish: 'aborted' }) }), codeIs('MODEL_ABORTED'));
  await assert.rejects(() => organize({ llm: fakeLlm(proposal(), { noFinish: true }) }), codeIs('MODEL_FAILED'));
  await assert.rejects(() => organize({ llm: fakeLlm(proposal(), { afterFinish: true }) }), codeIs('MODEL_FAILED'));
  await assert.rejects(() => organize({ llm: fakeLlm(proposal(), { throw: true }) }), error => codeIs('MODEL_FAILED')(error) && !error.message.includes('secret'));
});

test('retries once with compact, low-effort output after a max-token truncation', async () => {
  let calls = 0; const requests = [];
  const llm = {
    async *stream(request) {
      requests.push(request); calls++;
      if (calls === 1) {
        yield { type: 'text-delta', text: '{"groups":[{"title":"partial' };
        yield { type: 'finish', reason: { kind: 'max-tokens' } };
        return;
      }
      yield { type: 'text-delta', text: JSON.stringify(proposal()) };
      yield { type: 'finish', reason: { kind: 'stop' } };
    },
  };
  const { result } = await organize({ llm, selection: { ...selection, reasoningEffort: 'high' } });
  assert.equal(calls, 2);
  assert.equal(result.groups.length, 1);
  assert.equal(requests[1].reasoningEffort, 'low');
  assert.match(requests[1].messages[0].content[0].text, /exceeded the output token limit/);
  assert.ok(requests[1].messages[0].content[0].text.length > requests[0].messages[0].content[0].text.length);
  assert.match(requests[0].system, /under 6000 tokens/);
});

test('cancellation is passed through and partial output never accepted', async () => {
  const controller = new AbortController();
  const llm = fakeLlm(proposal(), { before: request => { assert.equal(request.signal, controller.signal); controller.abort(); } });
  await assert.rejects(() => organize({ llm, signal: controller.signal }), codeIs('MODEL_ABORTED'));
  await assert.rejects(() => organize({ signal: AbortSignal.abort() }), codeIs('MODEL_ABORTED'));
});

test('bounds oversized model output', async () => {
  await assert.rejects(() => organize({ llm: fakeLlm('x'.repeat(PLANNER_LIMITS.responseChars + 1)) }), codeIs('MODEL_FAILED'));
});

test('every large-repository path receives bounded evidence rather than prefix loss', async () => {
  const paths = Array.from({ length: 137 }, (_, index) => `content/posts/topic-${index}.md`);
  const diffs = paths.map((name, index) => ({ path: name, text: `+ BEGIN FILE ${index}\n` + 'detail\n'.repeat(3000) + `+ END FILE ${index}` }));
  const { result, llm } = await organize({ snapshot: snapshot(paths), diffs, llm: fakeLlm(proposal(paths)) });
  const data = promptData(llm);
  assert.deepEqual(data.eligibleFiles.map(file => file.path), paths);
  assert.equal(result.groups[0].paths.length, 137);
  assert.ok(data.eligibleFiles.every((file, index) => file.detailTruncated && file.evidence.includes(`BEGIN FILE ${index}`) && file.evidence.includes(`END FILE ${index}`) && file.evidence.includes('TRUNCATED')));
  assert.ok(data.eligibleFiles.reduce((sum, file) => sum + file.evidence.length, 0) <= PLANNER_LIMITS.diffChars);
  assert.ok(llm.calls[0].messages[0].content[0].text.length < PLANNER_LIMITS.promptChars);
  assert.equal(result.warnings.filter(item => item.includes('shared per-file budget')).length, 137);
});

test('upstream diff truncation, missing diffs and binary omissions are explicit', async () => {
  const files = ['src/search.js', { path: 'cover.png', binary: true }, 'missing.txt'];
  const { result, llm } = await organize({ snapshot: snapshot(files), diffs: [{ path: 'src/search.js', text: '+ changed', truncated: true }, { path: 'cover.png', text: 'BINARY-SECRET', binary: true }], llm: fakeLlm(proposal(['src/search.js', 'cover.png', 'missing.txt'])) });
  assert.match(result.warnings.join(' '), /already truncated upstream/);
  assert.match(result.warnings.join(' '), /Binary content/);
  assert.match(result.warnings.join(' '), /Diff unavailable/);
  assert.equal(promptData(llm).eligibleFiles[0].detailTruncated, true);
  assert.doesNotMatch(llm.calls[0].messages[0].content[0].text, /BINARY-SECRET/);
});

test('notebook source summaries never include outputs, attachments or execution metadata', async () => {
  const notebookDiff = `diff --git a/post.ipynb b/post.ipynb\n@@ -1,4 +1,4 @@\n+   "outputs": [{"text":"RAW-OUTPUT-SECRET"}],\n+   "attachments": {"image":"ATTACHMENT-SECRET"},\n+   "execution_count": 999,\n    "source": [\n-    "old source\\n"\n+    "new source\\n"\n    ]\n+   "source": ["inline source"], "outputs": ["INLINE-OUTPUT-SECRET"]\n+   "source": "string source", "metadata": {"token":"METADATA-SECRET"}\n+${JSON.stringify({ cells: [{ cell_type: 'code', source: ['compact source'], outputs: ['COMPACT-OUTPUT-SECRET'], metadata: { private: 'PRIVATE-CELL-SECRET' } }], metadata: { private: 'PRIVATE-NOTEBOOK-SECRET' } })}`;
  const { result, llm } = await organize({ snapshot: snapshot(['post.ipynb']), diffs: [{ path: 'post.ipynb', text: notebookDiff }], llm: fakeLlm(proposal(['post.ipynb'])) });
  const evidence = promptData(llm).eligibleFiles[0].evidence;
  for (const text of ['old source', 'new source', 'inline source', 'string source', 'compact source']) assert.ok(evidence.includes(text), text);
  assert.doesNotMatch(evidence, /RAW-OUTPUT-SECRET|ATTACHMENT-SECRET|INLINE-OUTPUT-SECRET|METADATA-SECRET|COMPACT-OUTPUT-SECRET|PRIVATE-CELL-SECRET|PRIVATE-NOTEBOOK-SECRET|999/);
  assert.match(result.warnings.join(' '), /outputs, attachments and metadata omitted/);
});

test('unrecognizable notebook fragments never fall back to raw patch', async () => {
  const { llm } = await organize({ snapshot: snapshot(['post.ipynb']), diffs: [{ path: 'post.ipynb', text: '+ "outputs": [{ "text": "DO-NOT-EXPOSE" }]' }], llm: fakeLlm(proposal(['post.ipynb'])) });
  assert.doesNotMatch(llm.calls[0].messages[0].content[0].text, /DO-NOT-EXPOSE/);
  assert.match(promptData(llm).eligibleFiles[0].evidence, /No safely recognizable/);
});

test('fails explicitly rather than dropping filenames when the full inventory cannot fit', async () => {
  const paths = Array.from({ length: 1000 }, (_, index) => `long/${String(index).padStart(4, '0')}-${'x'.repeat(200)}.js`);
  const llm = fakeLlm('not called');
  await assert.rejects(() => organize({ snapshot: snapshot(paths), diffs: [], llm }), codeIs('CONTEXT_LIMIT'));
  assert.equal(llm.calls.length, 0);
});

test('invalid and duplicate snapshot paths are rejected before model use', async () => {
  for (const files of [['src/search.js', 'src/search.js'], ['../outside.txt'], ['/absolute.txt'], ['']]) await assert.rejects(() => organize({ snapshot: snapshot(files) }), codeIs('INVALID_INPUT'));
});

test('collects only sessions whose canonical root is identical, including aliases but not nested repos', async () => {
  const query = queryFor([session('main'), session('nested', [user('FOREIGN-NESTED-CONTENT')], '/repo/foreign'), session('other', [user('FOREIGN-OTHER-CONTENT')], '/elsewhere'), session('alias', [user('Alias same repository')], '/alias')]);
  const result = await collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(query.reads.sort(), ['alias', 'main']);
  assert.deepEqual(result.sessions.map(item => item.id).sort(), ['alias', 'main']);
  assert.doesNotMatch(JSON.stringify(result), /FOREIGN-NESTED|FOREIGN-OTHER/);
});

test('ranks resumed older sessions by event activity and reads no more than twelve logs', async () => {
  const snapshots = Array.from({ length: 20 }, (_, index) => {
    const value = session(`s${index}`, [user(`Work ${index}`, index + 20)]);
    value.session.createdAt = index + 1;
    return value;
  });
  snapshots[0].events.push(user('Old resumed work', 9999));
  const query = queryFor(snapshots);
  const { sessions, warnings } = await collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver });
  assert.equal(query.reads.length, 12);
  assert.equal(query.reads[0], 's0');
  assert.equal(sessions[0].id, 's0');
  assert.match(warnings.join(' '), /12 of 20/);
});

test('excerpts contain user and completed final assistant text only, never tools/reasoning/system', async () => {
  const events = [
    user('Please improve search'),
    { type: 'system/message', time: 11, data: { message: { role: 'system', content: [{ type: 'text', text: 'SYSTEM-SECRET' }] } } },
    { type: 'developer/message', time: 12, data: { message: { role: 'developer', content: [{ type: 'text', text: 'DEVELOPER-SECRET' }] } } },
    assistant('COMMENTARY-NOT-FINAL', 1, 13),
    { type: 'tool/call', time: 14, data: { turn: 1, callId: 'c1', name: 'bash', arguments: '{"command":"PRIVATE-COMMAND"}' } },
    { type: 'tool/result', time: 15, data: { message: { role: 'tool', toolCallId: 'c1', content: [{ type: 'text', text: 'TOOL-OUTPUT-SECRET' }] } } },
    assistant('Updated search and tests', 1, 16, { message: { role: 'assistant', content: [{ type: 'reasoning', text: 'REASONING-SECRET' }, { type: 'text', text: 'Updated search and tests' }] } }),
    end(1, 17),
    assistant('INTERRUPTED-SECRET', 2, 18, { interrupted: true }), end(2, 19),
    assistant('UNCOMPLETED-CONTENT', 3, 20),
    { type: 'assistant/attempt', time: 21, data: { stream: [{ text: 'FAILED-ATTEMPT-SECRET' }] } },
  ];
  const result = await collectRecentSessions({ sessionQuery: queryFor([session('s1', events)]), root: ROOT, resolveRoot: rootResolver });
  const text = result.sessions[0].excerpts.map(item => item.text).join('\n');
  assert.match(text, /Please improve search/);
  assert.match(text, /Updated search and tests/);
  assert.doesNotMatch(text, /SECRET|PRIVATE-COMMAND|COMMENTARY-NOT-FINAL|UNCOMPLETED-CONTENT/);
});

test('successful mutation paths corroborate but failed/read-only/outside/nested paths do not', async () => {
  const call = (id, file, name = 'edit', command) => ({ type: 'tool/call', time: 12, data: { turn: 1, callId: id, name, arguments: JSON.stringify({ file_path: file, path: file, ...(command ? { command } : {}) }) } });
  const result = (id, extra = {}) => ({ type: 'tool/result', time: 13, data: { message: { role: 'tool', source: { callId: id }, isError: false }, ...extra } });
  const events = [user('Update `src/search.js` and [docs](docs/search.md).'), call('ok', 'src/search.js'), result('ok'), call('fail', 'bad.js'), result('fail', { error: { code: 'NO' } }), call('err', 'error.js'), result('err', { message: { role: 'tool', toolCallId: 'err', isError: true } }), call('outside', '/elsewhere/private.js'), result('outside'), call('nested', '/repo/foreign/private.js'), result('nested'), call('sensitive', '.env'), result('sensitive'), call('read', 'read.js', 'read'), result('read'), call('view', 'view.js', 'str_replace_editor', 'view'), result('view', { meta: { path: '/repo/view.js' } }), call('meta', 'ignored.js'), result('meta', { meta: { path: '/repo/src/meta.js' } })];
  const output = await collectRecentSessions({ sessionQuery: queryFor([session('s1', events)]), root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(output.sessions[0].touchedPaths, ['src/search.js', 'src/meta.js']);
  assert.deepEqual(output.sessions[0].mentionedPaths.sort(), ['docs/search.md', 'src/search.js']);
});

test('changing cwd filters foreign repository segments and titles, including nested repositories', async () => {
  const events = [user('Own repository work', 10), { type: 'working-directory/change', time: 11, data: { cwd: '/repo/foreign' } }, user('FOREIGN-REPOSITORY-SECRET', 12), assistant('FOREIGN-ASSISTANT-SECRET', 1, 13), end(1, 14), { type: 'working-directory/change', time: 15, data: { cwd: '/repo/src' } }, user('Returned own work', 16)];
  const query = queryFor([session('s1', events)]);
  const result = await collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(query.titles, []);
  assert.equal(result.sessions[0].title, '');
  assert.doesNotMatch(JSON.stringify(result), /FOREIGN-REPOSITORY-SECRET|FOREIGN-ASSISTANT-SECRET/);
  assert.match(JSON.stringify(result), /Returned own work/);
  assert.match(result.warnings.join(' '), /outside this canonical repository/);
});

test('does not include inherited fork log content', async () => {
  const value = session('child', [user('ANCESTOR-OTHER-REPOSITORY-SECRET'), user('Own child request', 30)]);
  value.inheritedEventCount = 1;
  const query = queryFor([value]);
  const output = await collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver });
  assert.doesNotMatch(JSON.stringify(output), /ANCESTOR-OTHER-REPOSITORY-SECRET/);
  assert.deepEqual(query.titles, []);
  assert.match(output.warnings.join(' '), /inherited events omitted/);
});

test('session excerpt count and character budgets are enforced with explicit notices', async () => {
  const snapshots = Array.from({ length: 12 }, (_, index) => session(`s${index}`, Array.from({ length: 20 }, (_, eventIndex) => user(`Recent work ${index}-${eventIndex} ` + 'x'.repeat(10000), eventIndex + 20))));
  const output = await collectRecentSessions({ sessionQuery: queryFor(snapshots), root: ROOT, resolveRoot: rootResolver });
  assert.equal(output.sessions.length, 12);
  assert.ok(output.sessions.every(item => item.excerpts.length <= PLANNER_LIMITS.excerptsPerSession && item.excerpts.reduce((sum, entry) => sum + entry.text.length, 0) <= PLANNER_LIMITS.sessionChars));
  assert.ok(output.sessions.reduce((sum, item) => sum + item.excerpts.reduce((subtotal, entry) => subtotal + entry.text.length, 0), 0) <= PLANNER_LIMITS.allSessionChars);
  assert.match(output.warnings.join(' '), /older conversation excerpts omitted/);
  assert.match(output.warnings.join(' '), /shared session-context budget/);
  assert.match(JSON.stringify(output), /TRUNCATED/);
});

test('organize re-bounds injected sessions and filters non-user/assistant excerpt roles', async () => {
  const sessions = Array.from({ length: 15 }, (_, index) => source(`s${index}`, '', { excerpts: [{ role: 'system', text: 'DO-NOT-SEND-SYSTEM' }, ...Array.from({ length: 20 }, () => ({ role: 'user', text: 'x'.repeat(10000) }))], touchedPaths: ['src/search.js', '.env', 'outside.js'] }));
  const { result, llm } = await organize({ sessions });
  const data = promptData(llm);
  assert.ok(data.sessions.length <= 12);
  assert.doesNotMatch(llm.calls[0].messages[0].content[0].text, /DO-NOT-SEND-SYSTEM/);
  assert.ok(data.sessions.every(item => item.excerpts.length <= 8 && item.touchedPaths.every(name => name === 'src/search.js')));
  assert.ok(data.sessions.reduce((sum, item) => sum + item.excerpts.reduce((subtotal, entry) => subtotal + entry.text.length, 0), 0) <= PLANNER_LIMITS.allSessionChars);
  assert.match(result.warnings.join(' '), /omitted|shortened/);
});

test('canonical root failures and changed snapshot identity fail closed', async () => {
  const query = queryFor([session()]);
  await assert.rejects(() => collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: async () => '/other' }), codeIs('INVALID_INPUT'));
  assert.equal(query.reads.length, 0);
  const changedQuery = { ...query, async readSession() { return session('s1', [user('FOREIGN-CONTENT')], '/elsewhere'); } };
  const output = await collectRecentSessions({ sessionQuery: changedQuery, root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(output.sessions, []);
  assert.doesNotMatch(JSON.stringify(output), /FOREIGN-CONTENT/);
});

test('session query failures are explicit and degrade to diff-only rather than accepting foreign context', async () => {
  const failedListing = { async listSessions() { throw new Error('DO-NOT-LEAK'); }, async readSession() { assert.fail('must not read'); } };
  const output = await collectRecentSessions({ sessionQuery: failedListing, root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(output.sessions, []);
  assert.match(output.warnings.join(' '), /listing failed/);
  assert.doesNotMatch(JSON.stringify(output), /DO-NOT-LEAK/);
  const query = queryFor([session()]);
  query.readSession = async () => { query.reads.push('s1'); throw new Error('DO-NOT-LEAK'); };
  const failedRead = await collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver });
  assert.deepEqual(failedRead.sessions, []);
  assert.match(failedRead.warnings.join(' '), /could not be read/);
  assert.equal(query.reads.length, 1);
});

test('collect cancellation and invalid limits are rejected', async () => {
  const query = queryFor([session()]);
  await assert.rejects(() => collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver, signal: AbortSignal.abort() }), codeIs('MODEL_ABORTED'));
  for (const limit of [0, 13, 1.2]) await assert.rejects(() => collectRecentSessions({ sessionQuery: query, root: ROOT, resolveRoot: rootResolver, limit }), codeIs('INVALID_INPUT'));
});

test('validatePlan can validate client-edited plans with the same full partition guard', () => {
  assert.deepEqual(validatePlan(proposal(), { paths: ['src/search.js'] }), proposal());
  assert.throws(() => validatePlan(proposal(), { paths: ['src/search.js', 'missing.js'] }), codeIs('INVALID_PLAN'));
});
