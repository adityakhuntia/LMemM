'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const crypto=require('node:crypto');
const excluded=new Set(['node_modules','vendor','dist','build','__pycache__','credentials','secrets']);
function bounded(text,limit){
 let bytes=Buffer.from(text); const truncated=bytes.length>limit;
 if(truncated){ bytes=bytes.subarray(0,limit); while(bytes.length && Buffer.from(bytes.toString('utf8')).length>limit) bytes=bytes.subarray(0,bytes.length-1); }
 return {text:bytes.toString('utf8'),truncated};
}
function visibleSnapshot(editor,roots,state){
 try{
  if(!state.focused || !state.trusted || !editor || editor.document.uri.scheme!=='file') return null;
  const root=fs.realpathSync(state.workspace); if(!roots.includes(root)) return null;
  const doc=fs.realpathSync(editor.document.uri.fsPath); const relative=path.relative(root,doc);
  if(!relative || relative.startsWith('..'+path.sep) || relative==='..' || path.isAbsolute(relative)) return null;
  if(relative.split(path.sep).some(p=>p.startsWith('.')||excluded.has(p.toLowerCase())) || /\.(pem|key|p12|pfx)$/i.test(doc)) return null;
  const spans=editor.visibleRanges.slice(0,4).map(range=>bounded(editor.document.getText(range),4096));
  if(!spans.length) return null;
  return {workspace:pathToFileURL(root).href,document:pathToFileURL(doc).href,version:editor.document.version,spans};
 }catch{return null;}
}
function readPrivate(file){
 const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
 try{const s=fs.fstatSync(fd); if(!s.isFile() || s.uid!==process.getuid() || (s.mode&0o777)!==0o600 || s.nlink!==1 || s.size>32768) throw Error('Non-private or oversize bridge file');
 const buffer=Buffer.alloc(32769);const n=fs.readSync(fd,buffer,0,buffer.length,0); if(n>32768)throw Error('Oversize bridge file');return JSON.parse(buffer.subarray(0,n).toString());}finally{fs.closeSync(fd);}
}
function writePrivate(file,value){
 const temp=file+'.'+crypto.randomBytes(8).toString('hex')+'.tmp';
 try{fs.writeFileSync(temp,JSON.stringify(value),{mode:0o600,flag:'wx'});fs.renameSync(temp,file);}finally{try{fs.unlinkSync(temp);}catch{}}
}
module.exports={bounded,visibleSnapshot,readPrivate,writePrivate};
