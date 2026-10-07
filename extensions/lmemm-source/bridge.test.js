const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {visibleSnapshot, bounded} = require('./bridge');
test('UTF8 bound preserves characters',()=>{
  const result=bounded('😀'.repeat(2000),4096);
  assert.equal(Buffer.byteLength(result.text),4096); assert.equal(result.truncated,true);
});
test('only reads active visible approved trusted local file',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'lmemm-')); fs.writeFileSync(path.join(root,'a.js'),'hello');
 const canonical=fs.realpathSync(root); let reads=[];
 const editor={document:{uri:{scheme:'file',fsPath:path.join(canonical,'a.js')},version:1,getText(range){assert.ok(range); reads.push(range); return 'hello';}},visibleRanges:[{start:{line:0,character:0},end:{line:1,character:0}}]};
 const snapshot=visibleSnapshot(editor,[canonical],{focused:true,trusted:true,workspace:canonical});
 assert.equal(snapshot.spans[0].text,'hello'); assert.equal(reads.length,1);
 for(const state of [{focused:false,trusted:true,workspace:canonical},{focused:true,trusted:false,workspace:canonical},{focused:true,trusted:true,workspace:root+'/child'}]) assert.equal(visibleSnapshot(editor,[canonical],state),null);
 assert.equal(reads.length,1);
 editor.document.uri.scheme='vscode-remote'; assert.equal(visibleSnapshot(editor,[canonical],{focused:true,trusted:true,workspace:canonical}),null);
 fs.rmSync(root,{recursive:true});
});
test('exclusions and symlink escape',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'lmemm-')); const canonical=fs.realpathSync(root);
 fs.writeFileSync(path.join(root,'.env'),'secret'); fs.symlinkSync('/etc/hosts',path.join(root,'escape'));
 for(const name of ['.env','escape']){
  const e={document:{uri:{scheme:'file',fsPath:path.join(canonical,name)},getText(){throw Error('must not read');}},visibleRanges:[{}]};
  assert.equal(visibleSnapshot(e,[canonical],{focused:true,trusted:true,workspace:canonical}),null);
 }
 fs.rmSync(root,{recursive:true});
});
test('UTF8 truncation never substitutes replacement characters',()=>{
 assert.equal(bounded('a'.repeat(4093)+'😀',4096).text,'a'.repeat(4093));
});
test('excluded lexical symlink is denied',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'lmemm-')); const canonical=fs.realpathSync(root);
 fs.writeFileSync(path.join(root,'a.js'),'public');fs.symlinkSync(path.join(root,'a.js'),path.join(root,'.env'));
 let reads=0; const e={document:{uri:{scheme:'file',fsPath:path.join(canonical,'.env')},getText(){reads++;return 'secret';}},visibleRanges:[{}]};
 assert.equal(visibleSnapshot(e,[canonical],{focused:true,trusted:true,workspace:canonical}),null);assert.equal(reads,0);fs.rmSync(root,{recursive:true});
});
test('host pause clears digest and resume publishes fresh source with new revision',async()=>{
 const Module=require('node:module');const crypto=require('node:crypto');
 const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'lmemm-host-')));fs.writeFileSync(path.join(root,'a.js'),'hello');
 const directory=path.join(root,'bridge');fs.mkdirSync(directory,{mode:0o700});for(const name of ['events','acks'])fs.mkdirSync(path.join(directory,name),{mode:0o700});
 const grantPath=path.join(directory,'grant.json'),grant={token:crypto.randomBytes(32).toString('hex'),session:'test',roots:[root],active:true,revision:0};
 fs.writeFileSync(grantPath,JSON.stringify(grant),{mode:0o600});
 let text='hello',version=1,poll;const commands={};const status={show(){},hide(){},text:''};
 const editor={document:{uri:{scheme:'file',fsPath:path.join(root,'a.js')},get version(){return version;},getText(){return text;}},visibleRanges:[{start:{line:0},end:{line:1}}]};
 const fake={StatusBarAlignment:{Right:1},ViewColumn:{Active:1},commands:{registerCommand(name,cb){commands[name]=cb;return {dispose(){}};}},workspace:{isTrusted:true,getWorkspaceFolder(){return {uri:{scheme:'file',fsPath:root}};}},window:{state:{focused:true},activeTextEditor:editor,createStatusBarItem(){return status;},async showInputBox(){return grantPath;},showErrorMessage(msg){throw Error(msg);},onDidChangeWindowState(){return {dispose(){}};},createWebviewPanel(){return {webview:{},dispose(){}};}}};
 const originalLoad=Module._load,originalInterval=global.setInterval,originalClear=global.clearInterval;
 try{
  Module._load=function(name,...args){return name==='vscode'?fake:originalLoad.call(this,name,...args);};global.setInterval=cb=>{poll=cb;return 1;};global.clearInterval=()=>{};
  const extension=require(process.env.LMEMM_TEST_EXTENSION||'./extension');extension.activate({subscriptions:[]});await commands['lmemm.connect']();
  const event=path.join(directory,'events',fs.readdirSync(path.join(directory,'events'))[0]);let m=JSON.parse(fs.readFileSync(event));const ack=path.join(directory,'acks',m.client+'.json');
  fs.writeFileSync(ack,JSON.stringify({session:'test',window:10,seq:m.seq}),{mode:0o600});poll();if(JSON.parse(fs.readFileSync(event)).kind!=='snapshot')poll();
  m=JSON.parse(fs.readFileSync(event));assert.equal(m.kind,'snapshot');
  fs.writeFileSync(ack,JSON.stringify({session:'test',window:10,seq:m.seq,accepted:true}),{mode:0o600});poll();
  grant.active=false;grant.revision=1;fs.writeFileSync(grantPath,JSON.stringify(grant));text='fresh edit';version++;poll();
  assert.match(status.text,/paused/);assert.equal(fs.existsSync(event),false);
  grant.active=true;grant.revision=2;fs.writeFileSync(grantPath,JSON.stringify(grant));poll();m=JSON.parse(fs.readFileSync(event));
  assert.equal(m.kind,'snapshot');assert.equal(m.spans[0].text,'fresh edit');assert.equal(m.revision,2);fs.unlinkSync(ack);poll();m=JSON.parse(fs.readFileSync(event));assert.equal(m.kind,'connect');assert.equal(m.spans,undefined);extension.deactivate();
 }finally{Module._load=originalLoad;global.setInterval=originalInterval;global.clearInterval=originalClear;fs.rmSync(root,{recursive:true});}
});
