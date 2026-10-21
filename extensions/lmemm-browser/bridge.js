(function(root){
  function createSaver({store,transport,capture,id}){
    let queue=Promise.resolve();
    const serial=fn=>{const job=queue.then(fn);queue=job.catch(()=>{});return job;};
    async function projects(){return (await transport('list_projects',{})).projects;}
    return {
      projects,
      chooseProject:project_id=>serial(async()=>{const project=(await projects()).find(p=>p.project_id===project_id);if(!project)throw Error('Choose an enabled project in LMemM.');await store.set({destination:project});return project;}),
      save:(tab,selectionOnly=false)=>serial(async()=>{
        if(!tab||tab.incognito||!/^https?:\/\//.test(tab.url||''))throw Error('Private or unsupported page. Nothing captured.');
        const state=await store.get();const project=(await projects()).find(p=>p.project_id===state.destination?.project_id);
        if(!project)return {needsProject:true};
        const payload={...await capture(tab,selectionOnly),request_id:id()};
        const saved=await transport('save',{project_id:project.project_id,payload});
        const receipt={source_id:saved.source_id,project_id:project.project_id,name:project.name,tab_id:tab.id};
        await store.set({lastSave:receipt,destination:project});return receipt;
      }),
      undo:()=>serial(async()=>{const {lastSave}=await store.get();if(!lastSave)throw Error('No recent save to undo.');await transport('undo',{source_id:lastSave.source_id});await store.set({lastSave:null});return {undone:true};}),
      move:project_id=>serial(async()=>{const {lastSave}=await store.get();if(!lastSave)throw Error('No recent save to move.');const project=(await projects()).find(p=>p.project_id===project_id);if(!project)throw Error('Project unavailable.');await transport('move',{source_id:lastSave.source_id,project_id});await store.set({destination:project,lastSave:{...lastSave,...project}});return project;}),
    };
  }
  root.LMemMBrowser={createSaver};if(typeof module!=='undefined')module.exports={createSaver};
})(globalThis);
