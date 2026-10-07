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
 const editor={document:{uri:{scheme:'file',fsPath:path.join(root,'a.js')},version:1,getText(range){assert.ok(range); reads.push(range); return 'hello';}},visibleRanges:[{start:{line:0,character:0},end:{line:1,character:0}}]};
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
  const e={document:{uri:{scheme:'file',fsPath:path.join(root,name)},getText(){throw Error('must not read');}},visibleRanges:[{}]};
  assert.equal(visibleSnapshot(e,[canonical],{focused:true,trusted:true,workspace:canonical}),null);
 }
 fs.rmSync(root,{recursive:true});
});
