const test=require('node:test');const assert=require('node:assert/strict');
const {createSaver}=require('./bridge.js');
function fixture(destination={project_id:'a',name:'Alpha'}) {
  const state={destination};const calls=[];let captures=0;
  const saver=createSaver({store:{get:async()=>state,set:async value=>Object.assign(state,value)},
    transport:async(method,params)=>{calls.push({method,params});if(method==='list_projects')return {projects:[{project_id:'a',name:'Alpha'},{project_id:'b',name:'Beta'}]};return {source_id:'source',project_id:params.project_id||'a'};},
    capture:async()=>{captures++;return {text:'A useful paragraph',title:'Research',url:'https://example.org',kind:'browser_selection',truncated:false};},id:()=> 'request-one'});
  return {saver,state,calls,captures:()=>captures};
}
test('first use asks destination without capturing or storing page text',async()=>{
  const f=fixture(null);assert.equal((await f.saver.save({id:1,url:'https://example.org'})).needsProject,true);
  assert.equal(f.captures(),0);assert.deepEqual(f.state,{destination:null});
});
test('one action saves to remembered project and stores only receipt metadata',async()=>{
  const f=fixture();const result=await f.saver.save({id:1,url:'https://example.org'});
  assert.equal(result.name,'Alpha');assert.equal(f.calls.at(-1).params.project_id,'a');
  assert.equal(f.calls.at(-1).params.payload.request_id,'request-one');assert.equal(f.captures(),1);
  assert.equal(JSON.stringify(f.state).includes('useful paragraph'),false);
});
test('deleted destination requires selection instead of guessing',async()=>{
  const f=fixture({project_id:'gone',name:'Old'});assert.equal((await f.saver.save({id:1,url:'https://example.org'})).needsProject,true);assert.equal(f.captures(),0);
});
test('private and restricted tabs never capture',async()=>{
  const f=fixture();for(const tab of [{id:1,url:'chrome://settings'},{id:1,url:'https://example.org',incognito:true}])await assert.rejects(f.saver.save(tab));
  assert.equal(f.captures(),0);
});
test('undo affects exact receipt and move updates remembered project after success',async()=>{
  const f=fixture();await f.saver.save({id:1,url:'https://example.org'});
  await f.saver.move('source','b');assert.equal(f.state.destination.project_id,'b');assert.equal(f.calls.at(-1).params.source_id,'source');
  await f.saver.undo('source');assert.equal(f.calls.at(-1).method,'undo');assert.equal(f.state.lastSave,null);
});
test('offline failure creates no receipt or hidden queue',async()=>{
  const state={destination:{project_id:'a',name:'Alpha'}};
  const saver=createSaver({store:{get:async()=>state,set:async v=>Object.assign(state,v)},transport:async()=>{throw Error('offline');},capture:async()=>{throw Error('must not capture');},id:()=> 'one'});
  await assert.rejects(saver.save({id:1,url:'https://example.org'}));assert.equal(state.lastSave,undefined);
});
test('queued Undo pins the original source while another save completes',async()=>{
  const state={destination:{project_id:'a',name:'Alpha'}};let number=0;const removed=[];
  const saver=createSaver({store:{get:async()=>state,set:async v=>Object.assign(state,v)},id:()=>String(++number),
    capture:async()=>({text:'Evidence',title:'Research',url:'https://example.org',kind:'browser_selection'}),
    transport:async(method,params)=>{if(method==='list_projects')return {projects:[{project_id:'a',name:'Alpha'}]};if(method==='undo'){removed.push(params.source_id);return {};}return {source_id:'source-'+params.payload.request_id};}});
  const first=await saver.save({id:1,url:'https://example.org'});
  const next=saver.save({id:2,url:'https://example.org'});
  const undo=saver.undo(first.source_id);
  await Promise.all([next,undo]);assert.deepEqual(removed,['source-1']);assert.equal(state.lastSave.source_id,'source-2');
});
