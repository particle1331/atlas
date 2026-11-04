import path from 'node:path';
import { realpath } from 'node:fs/promises';
import { GitReviewService, TOOL_SCHEMA } from './review-service.js';

export const name = 'git-review';
export const inject = ['commands','sessions','workingDirectory'];

export function apply(ctx) {
  const own = (agent,key) => (agent?.ctx ? ctx.get('agentPresets')?.serviceFor(agent,key) : undefined) || ctx.get(key);
  const service = new GitReviewService({
    services(agent) {
      const session=ctx.sessions.get(agent.id);
      if(!session) throw new Error('The receiving session is no longer available.');
      return {cwd:ctx.workingDirectory.get(session),llm:own(agent,'llm'),sessionQuery:own(agent,'sessionQuery'),selection:session.requestHeader()?.config || own(agent,'agentDefaultModel')?.currentSelection()};
    },
    async authorize({agent,request,caller,root,snapshot,signal}) {
      if(caller==='ui') return; // Direct UI commands carry their own deliberate confirmation.
      const session=ctx.sessions.get(agent.id);
      const policy=own(agent,'sandboxPolicy')?.resolve({session});
      if(!policy || policy.mode==='read-only') throw Object.assign(new Error('Git Review cannot change proposals or Git state in read-only mode.'),{code:'READ_ONLY'});
      const boundary=await realpath(policy.workspaceRoot);
      const relative=path.relative(boundary,root);
      if(policy.mode!=='danger-full-access' && (relative==='..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative))) throw Object.assign(new Error('The repository root is outside this session workspace. Open a session at the repository root.'),{code:'OUTSIDE_WORKSPACE'});
      if(['commit','push','checkout'].includes(request.action)) {
        const approval=own(agent,'approval');
        if(!approval) throw new Error('Explicit approval is unavailable; use the Git Review panel.');
        let detail='';
        if(request.action==='commit') {
          const draft=await service.store.read(root);
          if(!draft || draft.id!==request.planId || draft.revision!==request.revision) throw new Error('Proposal revision no longer matches. Refresh first.');
          detail=`Create ${draft.groups.length} commits, in order:\n${draft.groups.map(g=>`• ${g.title} (${g.paths.length} files)`).join('\n')}\nNo push.`;
        } else if(request.action==='push') detail=`Push ${snapshot.branch} at ${snapshot.head} to ${snapshot.upstream || '(no configured upstream)'} (${snapshot.pushTarget?.displayUrl||'unavailable'}). No force push.`;
        else detail=`Switch from ${snapshot.branch} to ${request.branch}; only allowed with a clean working tree.`;
        const outcome=await approval.request({agent,toolName:'git_review',reason:`${root}\n${detail}`,signal});
        if(outcome!=='allowed-once') throw Object.assign(new Error(`Git operation was not approved (${outcome}).`),{code:'NOT_APPROVED'});
      }
    }
  });
  ctx.provide('gitReview',service);
  ctx.effect(()=>()=>service.dispose());
  ctx.effect(()=>ctx.commands.register({
    name:'git-review',description:'Review changes and organize related commits (Git Review panel).',input:{hint:'Git Review operation JSON'},recordInput:false,
    async handler({agent,rawInput,signal}) {
      try {
        if(rawInput.length>2*1024*1024) throw new Error('Git Review request is too large.');
        const result=await service.run(agent,JSON.parse(rawInput),{caller:'ui',signal});
        return {kind:'success',text:JSON.stringify(result)};
      } catch(error) {return {kind:'error',text:JSON.stringify({error:error.message,code:error.code||'GIT_REVIEW_FAILED',...(error.recovery?{recovery:error.recovery}:{})})};}
    }
  }));
  ctx.inject(['tools'],toolCtx=>{
    toolCtx.effect(()=>toolCtx.tools.register({
      ...TOOL_SCHEMA,
      output:{schema:{type:'object',additionalProperties:true},render(_args,value){return [{type:'text',text:JSON.stringify(value)}];}},
      timeoutMs:240000,
      isConcurrencySafe:args=>['status','diff','history','branches'].includes(args?.action),
      async execute(request,exec) {
        if(!exec.agent) throw new Error('Git Review requires a receiving session.');
        return service.run(exec.agent,request,{caller:'tool',signal:exec.signal});
      }
    }));
  });
}
