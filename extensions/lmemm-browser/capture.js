(function(root){
  function safeUrl(value){const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error('Only ordinary HTTP(S) pages can be saved.');return u.href;}
  function boundText(text,max=131072){let size=0,out='';for(const c of String(text)){const n=new TextEncoder().encode(c).length;if(size+n>max)return {text:out,truncated:true};out+=c;size+=n;}return {text:out,truncated:false};}
  // This function is serialized into the isolated world; keep helpers local.
  function capturePage(selectionOnly=false){
    const focused=document.activeElement;
    const excluded='script,style,noscript,input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[hidden],[aria-hidden="true"]';
    if(focused?.closest(excluded))throw Error('Select ordinary page text; form fields are not captured.');
    function permitted(node){
      const el=node.parentElement;if(!el||el.closest(excluded)||el.isContentEditable||!el.getClientRects().length)return false;
      for(let p=el;p;p=p.parentElement){const s=getComputedStyle(p);if(s.visibility==='hidden'||s.display==='none'||s.opacity==='0')return false;}
      return true;
    }
    const selection=window.getSelection();let text='',kind='browser_page',cut=false;
    let visited=0,total=0,previousBlock=null;const started=performance.now();const pieces=[];
    function collect(node,range){
      if(++visited>50000||performance.now()-started>500||total>=160000){cut=true;return false;}
      if(range&&!range.intersectsNode(node)||!permitted(node))return true;
      const start=range&&node===range.startContainer?range.startOffset:0;
      const end=range&&node===range.endContainer?range.endOffset:node.textContent.length;
      const value=node.textContent.slice(start,end);if(value){
        const block=node.parentElement.closest('p,div,li,pre,blockquote,h1,h2,h3,section,article');
        if(range&&pieces.length&&block!==previousBlock)pieces.push('\n');
        pieces.push(value);total+=value.length;previousBlock=block;
      }
      return true;
    }
    if(selection&&!selection.isCollapsed){
      kind='browser_selection';
      for(let i=0;i<selection.rangeCount&&!cut;i++){
        const range=selection.getRangeAt(i);const ancestor=range.commonAncestorContainer;
        if(ancestor.nodeType===Node.TEXT_NODE){collect(ancestor,range);continue;}
        const walker=document.createTreeWalker(ancestor,NodeFilter.SHOW_TEXT);let node;
        while((node=walker.nextNode()))if(!collect(node,range))break;
      }
    }else if(selectionOnly){throw Error('Highlight the text you want to save first.');}
    else{
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      let node;while((node=walker.nextNode()))if(!collect(node,null))break;
    }
    text=pieces.join(kind==='browser_selection'?'':'\n');let out='',size=0,truncated=cut;
    for(const c of text){const n=new TextEncoder().encode(c).length;if(size+n>131072){truncated=true;break;}out+=c;size+=n;}
    if(!out.trim())throw Error('No supported visible text found on this page.');
    return {text:out,kind,title:document.title.slice(0,512),url:location.href,truncated};
  }
  const api={safeUrl,boundText,capturePage};root.LMemMCapture=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
