'use strict';
const vscode=require('vscode');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {visibleSnapshot,readPrivate,writePrivate,bounded}=require('./bridge');
let connection=null,paused=false,timer=null,status;
function state(editor){
 const folder=editor&&vscode.workspace.getWorkspaceFolder(editor.document.uri);
 return {focused:vscode.window.state.focused,trusted:vscode.workspace.isTrusted,
         workspace:folder&&folder.uri.scheme==='file'?folder.uri.fsPath:null};
}
function clear(){
 if(connection){try{fs.unlinkSync(connection.event);}catch{}}
}
function stop(){ clear();connection=null;clearInterval(timer);timer=null;if(status)status.hide(); }
function publish(kind,extra={}){
 if(!connection)return;
 const c=connection;
 const grant=readPrivate(path.join(c.directory,'grant.json'));
 if(grant.token!==c.token||grant.session!==c.session||!grant.active){clear();status.text='LMemM: paused by pilot';return;}
 writePrivate(c.event,{token:c.token,session:c.session,client:c.client,seq:++c.seq,at:Date.now()/1000,kind,focused:!paused&&vscode.window.state.focused,window:c.window,...extra});
}
function poll(){
 if(!connection)return;
 try{
  const c=connection;
  if(paused||!vscode.window.state.focused){c.last=null;publish('heartbeat');status.text='LMemM: source sharing paused';return;}
  if(!c.window){
   try{const ack=readPrivate(path.join(c.directory,'acks',c.client+'.json'));if(ack.session===c.session&&Number.isInteger(ack.window))c.window=ack.window;}catch{}
   if(!c.window){publish('connect');status.text='LMemM: waiting for native focus';return;}
  }
  const editor=vscode.window.activeTextEditor;
  const snapshot=visibleSnapshot(editor,c.roots,state(editor));
  if(!snapshot){c.last=null;publish('heartbeat');status.text='LMemM: current source excluded';return;}
  const digest=JSON.stringify(snapshot);
  if(c.last===digest)publish('heartbeat');else{publish('snapshot',snapshot);c.last=digest;}
  status.text='LMemM: experimental visible-source sharing';
 }catch(error){clear();status.text='LMemM: bridge unavailable';}
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
   status.show();poll();timer=setInterval(poll,1000);
  }catch(e){vscode.window.showErrorMessage('LMemM: '+e.message);stop();}
 }));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.pause',()=>{paused=true;clear();poll();}));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.stop',stop));
 context.subscriptions.push(vscode.commands.registerCommand('lmemm.note',async()=>{
  if(!connection||paused)return;
  const c=connection,editor=vscode.window.activeTextEditor;
  const before=visibleSnapshot(editor,c.roots,state(editor));if(!before)return;
  const text=await vscode.window.showInputBox({prompt:'Intentional project note. This text will be retained locally with this file as its source.'});
  if(!text||connection!==c||paused)return;
  const after=visibleSnapshot(vscode.window.activeTextEditor,c.roots,state(vscode.window.activeTextEditor));
  if(!after||after.document!==before.document||after.version!==before.version)return;
  try{publish('note',{...after,spans:[bounded(text,4096)]});c.last=null;}catch{clear();}
 }));
 context.subscriptions.push(vscode.window.onDidChangeWindowState(()=>{if(!vscode.window.state.focused)clear();poll();}));
 context.subscriptions.push({dispose:stop});
}
module.exports={activate,deactivate:stop};
