importScripts('capture.js','bridge.js');
const HOST='com.lmemm.browser';
const store={get:()=>chrome.storage.local.get(['destination','lastSave']),set:async value=>{
  await chrome.storage.local.set(value);
  const {destination}=await chrome.storage.local.get('destination');
  await chrome.action.setTitle({title:destination?'Save to LMemM · '+destination.name:'Save to LMemM — choose a project first'});
  await chrome.action.setBadgeText({text:destination?destination.name.slice(0,4):''});
  await chrome.action.setBadgeBackgroundColor({color:'#2b61ef'});
}};
async function transport(method,params){
  const request_id=crypto.randomUUID();
  let response;
  try{response=await chrome.runtime.sendNativeMessage(HOST,{version:1,request_id,method,params});}
  catch(e){throw Error('Open LMemM and connect this browser in Memory Settings. '+e.message);}
  if(response?.request_id!==request_id||!response.ok)throw Error(response?.error?.message||'Save not confirmed. Check LMemM.');
  return response.result;
}
const saver=LMemMBrowser.createSaver({store,transport,id:()=>crypto.randomUUID(),capture:async(tab,selectionOnly)=>{
  const result=await chrome.scripting.executeScript({target:{tabId:tab.id},func:LMemMCapture.capturePage,args:[selectionOnly]});
  if(!result[0]?.result)throw Error('Unable to read supported visible text.');
  const payload=result[0].result;LMemMCapture.safeUrl(payload.url);return payload;
}});
const confirmations=new Map();
async function openControls(tabId,mode='choose'){
  await chrome.windows.create({url:chrome.runtime.getURL('popup.html')+'?tab='+encodeURIComponent(tabId||'')+'&mode='+mode,type:'popup',width:400,height:440});
}
function showToast(message,nonce){
  document.getElementById('lmemm-save-confirmation')?.remove();
  const host=document.createElement('div');host.id='lmemm-save-confirmation';
  Object.assign(host.style,{position:'fixed',right:'20px',bottom:'20px',zIndex:'2147483647'});
  const shadow=host.attachShadow({mode:'closed'});const box=document.createElement('div');
  Object.assign(box.style,{background:'#202124',color:'#fff',padding:'16px',borderRadius:'12px',font:'14px system-ui',boxShadow:'0 4px 24px #0006'});
  const label=document.createElement('div');label.textContent=message;box.append(label);
  for(const [title,action] of [['Undo','undo'],['Change project','change']]){
    const b=document.createElement('button');b.textContent=title;
    Object.assign(b.style,{margin:'10px 8px 0 0',padding:'6px 10px',cursor:'pointer'});
    b.addEventListener('click',async e=>{if(!e.isTrusted)return;b.disabled=true;const result=await chrome.runtime.sendMessage({action,nonce});if(result?.ok){label.textContent=action==='undo'?'Save removed.':'Choose the destination in LMemM’s extension window.';}else label.textContent=result?.error||'Action could not be confirmed.';});box.append(b);
  }
  const close=document.createElement('button');close.textContent='Dismiss';close.onclick=()=>host.remove();box.append(close);
  shadow.append(box);document.documentElement.append(host);setTimeout(()=>host.remove(),15000);
}
async function saveTab(tab,selectionOnly=false){
  try{
    const result=await saver.save(tab,selectionOnly);
    if(result.needsProject){await openControls(tab.id);return;}
    const nonce=crypto.randomUUID();confirmations.set(tab.id,{nonce,source_id:result.source_id});
    await chrome.action.setBadgeText({tabId:tab.id,text:'✓'});
    await chrome.action.setTitle({tabId:tab.id,title:'Saved to '+result.name+' · right-click LMemM for Undo or Change project'});
    try{await chrome.scripting.executeScript({target:{tabId:tab.id},func:showToast,args:['Saved to '+result.name,nonce]});}catch{ /* receipt remains available in extension options */ }
  }catch(e){await chrome.storage.session.set({lastError:e.message});await chrome.action.setBadgeText({tabId:tab?.id,text:'!'});await openControls(tab?.id,'error');}
}
chrome.runtime.onInstalled.addListener(()=>{
  chrome.contextMenus.removeAll(()=>{
    chrome.contextMenus.create({id:'save',title:'Save selection to LMemM',contexts:['selection']});
    chrome.contextMenus.create({id:'controls',title:'Undo / change project…',contexts:['action']});
  });
});
chrome.action.onClicked.addListener(tab=>saveTab(tab));
chrome.contextMenus.onClicked.addListener((info,tab)=>info.menuItemId==='save'?saveTab(tab,true):openControls(tab?.id,'controls'));
chrome.commands.onCommand.addListener(async name=>{if(name==='save_selection'){const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});await saveTab(tab,true);}});
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  const ownPage=sender.id===chrome.runtime.id&&sender.url?.split('?')[0]===chrome.runtime.getURL('popup.html');
  const confirmation=sender.tab&&confirmations.get(sender.tab.id);
  const trustedToast=sender.id===chrome.runtime.id&&confirmation&&message.nonce===confirmation.nonce;
  if(!ownPage&&!trustedToast){respond({ok:false,error:'Not permitted'});return;}
  (async()=>{
    if(trustedToast){
      const {lastSave}=await store.get();if(lastSave?.source_id!==confirmation.source_id)throw Error('Use extension controls for the latest save.');
      if(message.action==='undo'){await saver.undo();confirmations.delete(sender.tab.id);return {};}
      if(message.action==='change'){await openControls(sender.tab.id,'controls');return {};}
      throw Error('Not permitted');
    }
    if(message.action==='state')return {...await store.get(),projects:await saver.projects(),...await chrome.storage.session.get('lastError')};
    if(message.action==='choose')return saver.chooseProject(message.project_id);
    if(message.action==='undo')return saver.undo();
    if(message.action==='move')return saver.move(message.project_id);
    if(message.action==='save'){const tab=await chrome.tabs.get(message.tab_id);await saveTab(tab);return {};}
    throw Error('Not permitted');
  })().then(result=>respond({ok:true,result}),e=>respond({ok:false,error:e.message}));return true;
});
