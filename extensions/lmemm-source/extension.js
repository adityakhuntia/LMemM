'use strict';
const vscode=require('vscode');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {visibleSnapshot,readPrivate,writePrivate,bounded}=require('./bridge');
let connection=null,paused=false,timer=null,status,challenge;
function state(editor){
 const folder=editor&&vscode.workspace.getWorkspaceFolder(editor.document.uri);
 return {focused:vscode.window.state.focused,trusted:vscode.workspace.isTrusted,
         workspace:folder&&folder.uri.scheme==='file'?folder.uri.fsPath:null};
}
function clear(){
 if(connection){try{fs.unlinkSync(connection.event);}catch{}}
}
function stop(){if(connection){confirmNote(connection);failNote(connection,'Disconnected.');try{publish('disconnect');}catch{clear();}} if(challenge){challenge.dispose();challenge=null;}connection=null;clearInterval(timer);timer=null;if(status)status.hide(); }
function failNote(c,message){
 if(c.note){c.note=null;clear();vscode.window.showErrorMessage('LMemM: note not confirmed. '+message);}
}
function confirmNote(c){
 if(!c.note)return;
 try{const ack=readPrivate(path.join(c.directory,'acks',c.client+'.json'));
  if(ack.session===c.session&&ack.window===c.window&&ack.accepted&&ack.note_id===c.note.note_id){c.note=null;c.last=null;vscode.window.showInformationMessage('LMemM: project note saved locally.');}
 }catch{}
}
function publish(kind,extra={}){
 if(!connection)return;
 const c=connection;
 const grant=readPrivate(path.join(c.directory,'grant.json'));
 if(grant.token!==c.token||grant.session!==c.session||!grant.active||grant.revision!==c.revision){c.last=null;c.pending=null;clear();status.text='LMemM: paused by pilot';return false;}
 writePrivate(c.event,{token:c.token,session:c.session,client:c.client,seq:++c.seq,at:Date.now()/1000,kind,revision:c.revision,focused:!paused&&vscode.window.state.focused,window:c.window,...extra});return true;
}
function poll(){
 if(!connection)return;
 try{
  const c=connection;
  const grant=readPrivate(path.join(c.directory,'grant.json'));
  confirmNote(c);
  if(c.note&&grant.revision!==c.note.revision)failNote(c,'Permissions or focus changed; submit again.');
  if(grant.revision!==c.revision){c.revision=grant.revision;c.last=null;c.pending=null;}
  if(!grant.active){failNote(c,'Pilot is paused.');c.last=null;c.pending=null;clear();status.text='LMemM: paused by pilot';return;}
  if(paused||!vscode.window.state.focused){failNote(c,'Source sharing paused or window lost focus.');c.last=null;publish('heartbeat');status.text='LMemM: source sharing paused';return;}
  if(c.window){
   try{const ack=readPrivate(path.join(c.directory,'acks',c.client+'.json'));if(ack.session!==c.session||ack.window!==c.window)throw Error('Registration lost');}
   catch{failNote(c,'Native registration was lost.');c.window=null;c.last=null;c.pending=null;challenge=vscode.window.createWebviewPanel('lmemmHandshake','LMemM '+c.client,vscode.ViewColumn.Active,{enableScripts:false});challenge.webview.html='<p>LMemM is re-verifying this native window.</p>';}
  }
  if(!c.window){
   try{const ack=readPrivate(path.join(c.directory,'acks',c.client+'.json'));if(ack.session===c.session&&Number.isInteger(ack.window)){c.window=ack.window;if(challenge){challenge.dispose();challenge=null;}return;}}catch{}
   if(!c.window){publish('connect');status.text='LMemM: waiting for native focus';return;}
  }
  try{const ack=readPrivate(path.join(c.directory,'acks',c.client+'.json'));if(c.pending&&ack.session===c.session&&ack.accepted&&ack.seq===c.pending.seq){c.last=c.pending.digest;c.pending=null;}}catch{}
  const editor=vscode.window.activeTextEditor;
  const snapshot=visibleSnapshot(editor,c.roots,state(editor));
  if(!snapshot){failNote(c,'Current source is excluded or unavailable.');c.last=null;publish('heartbeat');status.text='LMemM: current source excluded';return;}
  if(c.note){
   if(Date.now()/1000-c.note.note_at>2||snapshot.document!==c.note.document||snapshot.version!==c.note.version){failNote(c,'Delivery timed out or document changed; submit again.');}
   else{publish('note',c.note);status.text='LMemM: awaiting note confirmation';return;}
  }
  const digest=JSON.stringify(snapshot);
  let success;
  if(c.last===digest)success=publish('heartbeat');else{success=publish('snapshot',snapshot);if(success)c.pending={seq:c.seq,digest};}
  if(success)status.text='LMemM: experimental visible-source sharing';
 }catch(error){if(connection)failNote(connection,'Bridge unavailable; submit again.');clear();status.text='LMemM: bridge unavailable';}
}
function activate(context){
 status=vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right);context.subscriptions.push(status);
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.connect',async()=>{
  const grantPath=await vscode.window.showInputBox({prompt:'Path to the running pilot grant.json. Only approved visible local files are shared.'});
  if(!grantPath)return;
  try{
   stop();const directory=path.dirname(grantPath);const s=fs.lstatSync(directory);
   if(!s.isDirectory()||s.isSymbolicLink()||s.uid!==process.getuid()||(s.mode&0o777)!==0o700)throw Error('Bridge directory must be private');
   for(const name of ['events','acks']){const d=fs.lstatSync(path.join(directory,name));if(!d.isDirectory()||d.isSymbolicLink()||(d.mode&0o777)!==0o700||d.uid!==process.getuid())throw Error('Private bridge directory required');}
   const grant=readPrivate(grantPath);if(!grant.active||!Array.isArray(grant.roots))throw Error('Inactive pilot');
   const client=crypto.randomBytes(16).toString('hex');connection={...grant,directory,client,seq:0,window:null,last:null,event:path.join(directory,'events',client+'.json')};paused=false;
   challenge=vscode.window.createWebviewPanel('lmemmHandshake','LMemM '+client,vscode.ViewColumn.Active,{enableScripts:false});
   challenge.webview.html='<p>LMemM is verifying this native window. This tab closes once verified.</p>';
   status.show();poll();timer=setInterval(poll,1000);
  }catch(e){vscode.window.showErrorMessage('LMemM: '+e.message);stop();}
 }));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.pause',()=>{paused=true;if(connection){confirmNote(connection);failNote(connection,'Source sharing paused.');}clear();poll();}));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.stop',stop));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.note',async()=>{
  if(!connection||paused)return;
  const c=connection,editor=vscode.window.activeTextEditor;
  const before=visibleSnapshot(editor,c.roots,state(editor));if(!before)return;
  const text=await vscode.window.showInputBox({prompt:'Intentional project note. This text will be retained locally with this file as its source.'});
  if(!text||connection!==c||paused)return;
  // Let the input box dismiss before sampling the post-submit authorization.
  await new Promise(resolve=>setTimeout(resolve,500));
  if(connection!==c||paused)return;
  const after=visibleSnapshot(vscode.window.activeTextEditor,c.roots,state(vscode.window.activeTextEditor));
  if(!after||after.document!==before.document||after.version!==before.version){vscode.window.showErrorMessage('LMemM: note not saved; active document changed.');return;}
  try{
   const grant=readPrivate(path.join(c.directory,'grant.json'));
   if(!grant.active||grant.session!==c.session||grant.token!==c.token)throw Error('Pilot paused or session changed');
   c.revision=grant.revision;c.last=null;c.pending=null;
   c.note={workspace:after.workspace,document:after.document,version:after.version,spans:[bounded(text,4096)],note_id:crypto.randomBytes(16).toString('hex'),note_at:Date.now()/1000,revision:c.revision};
   poll();
  }catch(error){failNote(c,error.message);vscode.window.showErrorMessage('LMemM: note not saved. '+error.message);}
 }));
 context.subscriptions.push(vscode.window.onDidChangeWindowState(()=>{if(!vscode.window.state.focused)clear();poll();}));
 context.subscriptions.push({dispose:stop});
}
module.exports={activate,deactivate:stop};
