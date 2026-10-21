const $=id=>document.getElementById(id);const params=new URLSearchParams(location.search);
const tabId=Number(params.get('tab'));
async function send(action,extra={}){const response=await chrome.runtime.sendMessage({action,...extra});if(!response?.ok)throw Error(response?.error||'LMemM is unavailable.');return response.result;}
async function load(){
  try{
    const state=await send('state');$('project').replaceChildren();
    for(const p of state.projects){const option=document.createElement('option');option.value=p.project_id;option.textContent=p.name;$('project').append(option);}
    if(state.destination)$('project').value=state.destination.project_id;
    $('status').textContent=params.get('mode')==='error'?(state.lastError||'Save could not be confirmed.'):state.destination?'Saving to '+state.destination.name+'.':'Choose a project once. After that, saving takes one action.';
    $('save').disabled=!Number.isInteger(tabId)||!params.get('tab');$('undo').disabled=$('move').disabled=!state.lastSave;
  }catch(e){$('status').textContent=e.message+' Enable a project and connect Chrome in LMemM → Memory → Settings.';}
}
for(const action of ['choose','move','undo','save'])$(action).onclick=async()=>{
  try{await send(action,{project_id:$('project').value,tab_id:tabId});$('status').textContent=action==='choose'?'Destination selected. Save the original page, or close this window and use the shortcut.':action==='undo'?'Last save removed.':action==='move'?'Last save moved.':'Save requested. Check the confirmation on the original page.';}
  catch(e){$('status').textContent=e.message;}
};load();
