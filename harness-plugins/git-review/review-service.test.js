import test from 'node:test';
import assert from 'node:assert/strict';
import {GitReviewService,validateEditedGroups,TOOL_SCHEMA} from './review-service.js';
const agent={id:'test-session'};
function fixture(overrides={}) {
  const snapshot={root:'/repo',head:'a'.repeat(40),branch:'main',fingerprint:'f'.repeat(64),files:[{path:'src/a.js',contentHash:'h1'},{path:'test/a.js',contentHash:'h2'},{path:'.env',contentHash:'h3'}],warnings:[],states:[]};
  const draft={version:1,id:'p1',revision:1,state:'draft',root:'/repo',head:snapshot.head,fingerprint:snapshot.fingerprint,pathHashes:{'src/a.js':'h1','test/a.js':'h2'},groups:[{id:'g1',title:'Fix a',body:'',rationale:'Source and tests',paths:['src/a.js','test/a.js'],sessionIds:[]}],unassigned:['.env']};
  const calls=[];let saved=structuredClone(draft);
  const engine={snapshot:async()=>{calls.push('snapshot');return structuredClone(snapshot);},diff:async args=>{calls.push(['diff',args]);return {path:args.path,text:'diff'};},history:async()=>[{hash:snapshot.head,title:'Previous'}],branches:async()=>[{name:'main'}],commitGroups:async args=>{calls.push(['commit',args]);return {head:'b'.repeat(40),commits:[{hash:'b'.repeat(40)}]};},push:async args=>{calls.push(['push',args]);return {pushed:true};},checkout:async args=>{calls.push(['checkout',args]);return {branch:args.branch};},undoLastCommit:async args=>{calls.push(['undo',args]);return {head:'c'.repeat(40),undone:true};},discardChanges:async args=>{calls.push(['discard',args]);return {discarded:args.paths};},stashChanges:async args=>{calls.push(['stash',args]);return {stashed:true};},amendMessage:async args=>{calls.push(['amend',args]);return {head:'d'.repeat(40),amended:true};}};
  const store={read:async()=>structuredClone(saved),write:async(_root,value)=>{calls.push('write');saved=structuredClone(value);}};
  const deps={cwd:'/repo',selection:{provider:'mock',model:'mock'},llm:{},sessionQuery:{}};
  const service=new GitReviewService({engineFactory:()=>engine,store,services:()=>deps,collect:async()=>({sessions:[],warnings:['Context note']}),organize:async()=>({groups:draft.groups,warnings:[],unassigned:['.env'],sourceSessions:[]}),authorize:async args=>{calls.push(['authorize',args.request.action,args.caller]);},...overrides});
  return {snapshot,draft,calls,engine,store,deps,service,get saved(){return saved;},set saved(value){saved=value;}};
}
test('status returns saved proposal and stale indicator without authorizing writes',async()=>{
  const f=fixture();const result=await f.service.run(agent,{action:'status'});assert.equal(result.draft.stale,false);assert.deepEqual(f.calls,['snapshot']);
  f.snapshot.fingerprint='0'.repeat(64);const stale=await f.service.run(agent,{action:'status'});
  assert.equal(stale.draft.stale,true);assert.deepEqual(stale.draft.affectedPaths,[]);assert.equal(stale.draft.canCommit,true);
  f.snapshot.files[0].contentHash='changed';
  const affected=await f.service.run(agent,{action:'status'});
  assert.deepEqual(affected.draft.affectedPaths,['src/a.js']);assert.equal(affected.draft.canCommit,false);
});
test('diff and history do not fingerprint the entire working tree for every file',async()=>{
  const f=fixture();await f.service.run(agent,{action:'diff',path:'src/a.js'});await f.service.run(agent,{action:'history'});assert.equal(f.calls.includes('snapshot'),false);
  await assert.rejects(f.service.run(agent,{action:'diff'}),{code:'INVALID_INPUT'});
});
test('model catalog and reasoning metadata are available for the selectors',async()=>{
  const f=fixture();
  f.deps.llm={
    listProviders:()=>[{id:'p',name:'Provider'}],
    listModels:async()=>[{id:'deepseek-flash',name:'DeepSeek Flash'},{id:'astra-scan',name:'Astra Scout'},{id:'m',name:'Model'}],
    resolveModelInfo:async()=>({reasoning:{efforts:[{id:'low',name:'Low'}],defaultEffort:'low'}}),
  };
  const models=await f.service.run(agent,{action:'models'});
  assert.equal(models.providers[0].provider,'p');
  assert.deepEqual(models.providers[0].models,[{id:'deepseek-flash',name:'DeepSeek Flash'},{id:'m',name:'Model'}]);
  const info=await f.service.run(agent,{action:'modelInfo',provider:'p',model:'m'});
  assert.equal(info.efforts[0].id,'low');assert.equal(info.defaultEffort,'low');
  await assert.rejects(f.service.run(agent,{action:'modelInfo',provider:'p'}),{code:'INVALID_INPUT'});
});

test('organize can use an explicit model and reasoning override',async()=>{
  let request;const f=fixture({organize:async args=>{request=args;return {groups:[{title:'Fix',paths:['src/a.js','test/a.js']}]}}});
  f.deps.llm={};
  await f.service.run(agent,{action:'organize',provider:'p',model:'m',reasoningEffort:'low'});
  assert.equal(request.selection.provider,'p');assert.equal(request.selection.model,'m');assert.equal(request.selection.reasoningEffort,'low');
  assert.equal(f.saved.model.provider,'p');assert.equal(f.saved.reasoningEffort,'low');
  await assert.rejects(f.service.run(agent,{action:'organize',provider:'p'}),{code:'INVALID_INPUT'});
  await assert.rejects(f.service.run(agent,{action:'organize',provider:'p',model:'astra-scan',reasoningEffort:'low'}),{code:'MODEL_BLOCKED'});
});

test('organize skips secrets, passes session context, persists proposal without commits',async()=>{
  let request;const f=fixture({organize:async args=>{request=args;return {groups:[{title:'Fix',paths:['src/a.js','test/a.js']}],warnings:[],unassigned:['.env']};}});
  const result=await f.service.run(agent,{action:'organize'},{caller:'ui'});
  assert.equal('targetCount' in request,false);assert.deepEqual(request.diffs.map(d=>d.path),['src/a.js','test/a.js']);assert.equal(result.draft.groups[0].id,'g1');assert.deepEqual(result.draft.pathHashes,{'src/a.js':'h1','test/a.js':'h2'});assert.ok(result.draft.warnings.includes('Context note'));assert.equal(f.calls.some(c=>Array.isArray(c)&&c[0]==='commit'),false);
});
test('organize requires a working model and no requested group count',async()=>{
  const missing=fixture();missing.deps.selection=null;await assert.rejects(missing.service.run(agent,{action:'organize'}),{code:'MODEL_UNAVAILABLE'});assert.equal(missing.calls.includes('write'),false);
  const f=fixture();const ok=await f.service.run(agent,{action:'organize'});assert.ok(ok.draft.groups.length);
});
test('organize can disable session collection',async()=>{
  let collected=false;const f=fixture({collect:async()=>{collected=true;throw new Error('must not collect');}});await f.service.run(agent,{action:'organize',includeSessions:false});assert.equal(collected,false);
});
test('organize discards stale generated proposals',async()=>{
  const f=fixture({organize:async()=>{f.snapshot.fingerprint='changed';return {groups:f.draft.groups};}});await assert.rejects(f.service.run(agent,{action:'organize'}),{code:'STALE_PLAN'});assert.equal(f.calls.includes('write'),false);
});
test('draft edits use exact revisions, exclude secrets, reject duplicates',async()=>{
  const f=fixture();await assert.rejects(f.service.run(agent,{action:'save',planId:'p1',revision:0,groups:[]}),{code:'STALE_DRAFT'});
  await assert.rejects(f.service.run(agent,{action:'save',planId:'p1',revision:1,groups:[{title:'Oops',paths:['.env']}]}),{code:'INVALID_PLAN'});
  await assert.rejects(f.service.run(agent,{action:'save',planId:'p1',revision:1,groups:[{title:'One',paths:['src/a.js']},{title:'Two',paths:['src/a.js']}]}),{code:'INVALID_PLAN'});
  const next=await f.service.run(agent,{action:'save',planId:'p1',revision:1,groups:[{id:'g1',title:'Improve a',paths:['src/a.js']}]});assert.equal(next.draft.revision,2);assert.deepEqual(next.draft.unassigned,['test/a.js','.env']);
});
test('UI commit needs one deliberate confirmation but no review list',async()=>{
  const f=fixture();const request={action:'commit',planId:'p1',revision:1};
  await assert.rejects(f.service.run(agent,request,{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
  const result=await f.service.run(agent,{...request,confirmed:true},{caller:'ui'});assert.ok(result.commits.length);assert.equal(f.saved.state,'committed');
});

test('stashChanges requires confirmation',async()=>{
  const f=fixture();
  await assert.rejects(f.service.run(agent,{action:'stashChanges'},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
  const result=await f.service.run(agent,{action:'stashChanges',confirmed:true},{caller:'ui'});
  assert.equal(result.stashed,true);
  assert.ok(f.calls.some(c=>Array.isArray(c)&&c[0]==='stash'));
});

test('discardChanges requires confirmation and exact paths',async()=>{
  const f=fixture();
  await assert.rejects(f.service.run(agent,{action:'discardChanges',paths:['src/a.js']},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
  const result=await f.service.run(agent,{action:'discardChanges',paths:['src/a.js'],confirmed:true},{caller:'ui'});
  assert.deepEqual(result.discarded,['src/a.js']);
  const call=f.calls.find(c=>Array.isArray(c)&&c[0]==='discard');assert.deepEqual(call[1].paths,['src/a.js']);
});

test('undo and amend act on the exact HEAD and require confirmation',async()=>{
  const f=fixture();
  await assert.rejects(f.service.run(agent,{action:'undoCommit',expectedHead:f.snapshot.head},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
  await f.service.run(agent,{action:'undoCommit',expectedHead:f.snapshot.head,confirmed:true},{caller:'ui'});
  const undo=f.calls.find(c=>Array.isArray(c)&&c[0]==='undo');assert.equal(undo[1].expectedHead,f.snapshot.head);
  await f.service.run(agent,{action:'amendCommit',summary:'Better title',description:'Body',expectedHead:f.snapshot.head,confirmed:true},{caller:'ui'});
  const amend=f.calls.find(c=>Array.isArray(c)&&c[0]==='amend');assert.equal(amend[1].summary,'Better title');assert.equal(amend[1].body,'Body');
  assert.ok(f.calls.some(c=>Array.isArray(c)&&c[0]==='authorize'&&c[1]==='undoCommit'));
});
test('commit uses persisted groups, not arbitrary replacement groups in request',async()=>{
  const f=fixture();await f.service.run(agent,{action:'commit',planId:'p1',revision:1,groups:[{title:'Injected',paths:['.env']}]});const commit=f.calls.find(c=>Array.isArray(c)&&c[0]==='commit');assert.equal(commit[1].groups[0].title,'Fix a');assert.ok(f.calls.some(c=>Array.isArray(c)&&c[0]==='authorize'&&c[1]==='commit'));
});
test('authorization refusal prevents commits and draft writes',async()=>{
  const f=fixture({authorize:async()=>{throw Object.assign(new Error('Denied'),{code:'NOT_APPROVED'});}});await assert.rejects(f.service.run(agent,{action:'commit',planId:'p1',revision:1}),{code:'NOT_APPROVED'});assert.equal(f.calls.some(c=>Array.isArray(c)&&c[0]==='commit'),false);assert.equal(f.calls.includes('write'),false);
});
test('unrelated changes do not invalidate a proposal, HEAD changes and receipts do',async()=>{
  const f=fixture();
  f.snapshot.fingerprint='different';
  await f.service.run(agent,{action:'commit',planId:'p1',revision:1});
  const commit=f.calls.find(c=>Array.isArray(c)&&c[0]==='commit');
  assert.equal(commit[1].expectedHead,f.draft.head);
  assert.deepEqual(commit[1].pathHashes,{'src/a.js':'h1','test/a.js':'h2'});
  f.saved={...f.draft,state:'committed'};
  await assert.rejects(f.service.run(agent,{action:'commit',planId:'p1',revision:1}),{code:'STALE_PLAN'});
  f.saved={...f.draft,head:'b'.repeat(40)};
  await assert.rejects(f.service.run(agent,{action:'commit',planId:'p1',revision:1}),{code:'STALE_PLAN'});
});
test('commitFiles lists a commit\'s changed files without mutating state',async()=>{
  const f=fixture();
  f.engine.commitFiles=async({commit})=>({commit,files:[{path:'src/a.js',status:'M'}]});
  const result=await f.service.run(agent,{action:'commitFiles',commit:f.snapshot.head});
  assert.deepEqual(result.files,[{path:'src/a.js',status:'M'}]);
  await assert.rejects(f.service.run(agent,{action:'commitFiles'}),{code:'INVALID_INPUT'});
  assert.equal(f.calls.some(c=>Array.isArray(c)&&c[0]==='commit'),false);
});

test('commitSelected commits only the checked files with a required summary',async()=>{
  const f=fixture();
  await assert.rejects(f.service.run(agent,{action:'commitSelected',summary:'Fix',paths:['src/a.js']},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
  await assert.rejects(f.service.run(agent,{action:'commitSelected',summary:'',paths:['src/a.js'],confirmed:true},{caller:'ui'}),{code:'INVALID_INPUT'});
  await assert.rejects(f.service.run(agent,{action:'commitSelected',summary:'Fix',paths:['src/a.js','src/a.js'],confirmed:true},{caller:'ui'}),{code:'INVALID_INPUT'});
  const result=await f.service.run(agent,{action:'commitSelected',summary:'Fix a',description:'Body',paths:['src/a.js','test/a.js'],confirmed:true},{caller:'ui'});
  const commit=f.calls.find(c=>Array.isArray(c)&&c[0]==='commit');
  assert.deepEqual(commit[1].groups,[{title:'Fix a',body:'Body',paths:['src/a.js','test/a.js']}]);
  assert.ok(result.commits.length);
  assert.ok(f.calls.some(c=>Array.isArray(c)&&c[0]==='authorize'&&c[1]==='commitSelected'));
});

test('push and checkout are separate confirmed operations',async()=>{
  const f=fixture();await assert.rejects(f.service.run(agent,{action:'push',expectedHead:f.snapshot.head},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});await f.service.run(agent,{action:'push',expectedHead:f.snapshot.head,confirmed:true},{caller:'ui'});assert.equal(f.calls.some(c=>Array.isArray(c)&&c[0]==='commit'),false);
  await assert.rejects(f.service.run(agent,{action:'checkout',branch:'other',expectedHead:f.snapshot.head},{caller:'ui'}),{code:'CONFIRM_REQUIRED'});
});
test('receipt write failure reports commits already created rather than throwing a retryable failure',async()=>{
  const f=fixture();f.store.write=async()=>{throw new Error('disk failed');};const result=await f.service.run(agent,{action:'commit',planId:'p1',revision:1});assert.match(result.warning,/were created/);assert.ok(result.head);
});
test('edited groups keep cited sources but cannot duplicate ids or assign unsafe files',()=>{
  const f=fixture();assert.throws(()=>validateEditedGroups([{id:'g1',title:'One',paths:['src/a.js']},{id:'g1',title:'Two',paths:['test/a.js']}],f.snapshot,f.draft),{code:'INVALID_PLAN'});assert.throws(()=>validateEditedGroups([{title:'Injected\nMessage',paths:['src/a.js']}],f.snapshot,f.draft),{code:'INVALID_PLAN'});
});
test('model-facing diffs exclude sensitive files and require an explicit historical path',async()=>{
  const f=fixture();
  await assert.rejects(f.service.run(agent,{action:'diff',path:'.env'}),{code:'EXCLUDED_DIFF'});
  await assert.rejects(f.service.run(agent,{action:'diff',commit:f.snapshot.head}),{code:'EXCLUDED_DIFF'});
  await f.service.run(agent,{action:'diff',commit:f.snapshot.head},{caller:'ui'});
  f.snapshot.files.push({path:'.gnupg/private.txt',sensitive:true});
  await assert.rejects(f.service.run(agent,{action:'save',planId:'p1',revision:1,groups:[{title:'No',paths:['.gnupg/private.txt']}]}),{code:'INVALID_PLAN'});
});
test('new tool has a bounded schema and explicit effect constraints',()=>{
  const before=0,after=Math.ceil(JSON.stringify(TOOL_SCHEMA).length/4);assert.ok(after<1000);assert.match(TOOL_SCHEMA.description,/separate approval/);assert.equal(TOOL_SCHEMA.parameters.additionalProperties,false);assert.ok(after>before);
});
