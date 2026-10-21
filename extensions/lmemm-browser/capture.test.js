const test=require('node:test');const assert=require('node:assert/strict');
const {boundText,safeUrl}=require('./capture.js');
test('UTF8 bounds preserve code points and disclose truncation',()=>{
 const r=boundText('😀'.repeat(40000));assert.ok(new TextEncoder().encode(r.text).length<=131072);assert.equal(r.truncated,true);assert.ok(!r.text.includes('\uFFFD'));
});
test('URL validation refuses executable and authenticated schemes',()=>{
 for(const url of ['file:///tmp/a','javascript:alert(1)','https://user:secret@example.org'])assert.throws(()=>safeUrl(url));
 assert.equal(safeUrl('https://example.org/research'),'https://example.org/research');
});
