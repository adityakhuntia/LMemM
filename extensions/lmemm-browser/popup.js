const $=id=>document.getElementById(id);const params=new URLSearchParams(location.search);
const tabId=Number(params.get('tab'));
let sourceId=params.get('source')||null;
async function send(action,extra={}){const response=await chrome.runtime.sendMessage({action,...extra});if(!response?.ok)throw Error(response?.error||'LMemM is unavailable.');return response.result;}
async function load(){
  try{
    const state=await send('state');$('project').replaceChildren();
    sourceId=sourceId||state.lastSave?.source_id;
    for(const p of state.projects){const option=document.createElement('option');option.value=p.project_id;option.textContent=p.name;$('project').append(option);}
    if(state.destination)$('project').value=state.destination.project_id;
    $('status').textContent=params.get('mode')==='error'?(state.lastError||'Save could not be confirmed.'):state.destination?'Saving to '+state.destination.name+'.':'Choose a project once. After that, saving takes one action.';
    $('save').disabled=!Number.isInteger(tabId)||!params.get('tab');$('undo').disabled=$('move').disabled=!sourceId;
  }catch(e){$('status').textContent=e.message+' Enable a project and connect Chrome in LMemM → Memory → Settings.';}
}
for(const action of ['choose','move','undo','save'])$(action).onclick=async()=>{
  try{await send(action,{project_id:$('project').value,tab_id:tabId,source_id:sourceId});$('status').textContent=action==='choose'?'Destination selected. Save the original page, or close this window and use the shortcut.':action==='undo'?'Selected save removed.':action==='move'?'Selected save moved.':'Save requested. Check the confirmation on the original page.';if(action==='undo'){$('undo').disabled=$('move').disabled=true;}}
  catch(e){$('status').textContent=e.message;}
};load();
