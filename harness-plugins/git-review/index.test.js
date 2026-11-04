import test from 'node:test';
import assert from 'node:assert/strict';
import {apply} from './index.js';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);
test('registered UI command and agent tool share real read-only repository service',async()=>{
  const root=await mkdtemp(path.join(tmpdir(),'dsh-git-review-host-'));
  try {
    await exec('git',['-c','init.defaultBranch=main','init',root]);
    await writeFile(path.join(root,'hello.txt'),'Hello\n');
    let command,tool,service;const disposers=[];
    const session={requestHeader:()=>({config:{provider:'mock',model:'mock'}})};
    const services={sessions:{get:()=>session},workingDirectory:{get:()=>root},sandboxPolicy:{resolve:()=>({mode:'workspace-write',workspaceRoot:root})},tools:{register:def=>{tool=def;return()=>{};}},commands:{register:def=>{command=def;return()=>{};}}};
    const ctx={...services,get:name=>services[name],provide(name,value){if(name==='gitReview')service=value;return()=>{};},effect(callback){const dispose=callback();if(typeof dispose==='function')disposers.push(dispose);return dispose;},inject(_deps,callback){callback(ctx);}};
    apply(ctx);
    assert.equal(command.name,'git-review');assert.equal(tool.name,'git_review');assert.ok(service);
    const agent={id:'test'};
    const ui=await command.handler({agent,rawInput:JSON.stringify({action:'status'})});
    assert.equal(ui.kind,'success',ui.text);const uiStatus=JSON.parse(ui.text);
    const toolStatus=await tool.execute({action:'status'},{agent});
    assert.equal(uiStatus.snapshot.fingerprint,toolStatus.snapshot.fingerprint);
    assert.deepEqual(uiStatus.snapshot.files,toolStatus.snapshot.files);
    const denied=await command.handler({agent,rawInput:'not-json'});assert.equal(denied.kind,'error');
    await assert.rejects(tool.execute({action:'diff',path:'.env'},{agent}),{code:'EXCLUDED_DIFF'});
    services.sandboxPolicy.resolve=()=>({mode:'read-only',workspaceRoot:root});
    await assert.rejects(tool.execute({action:'organize'},{agent}),{code:'READ_ONLY'});
    service.dispose();for(const dispose of disposers.reverse())dispose();
  } finally {
    const resolved=path.resolve(root);
    assert.equal(path.dirname(resolved),path.resolve(tmpdir()));assert.ok(path.basename(resolved).startsWith('dsh-git-review-host-'));
    await rm(resolved,{recursive:true,force:true});
  }
});
