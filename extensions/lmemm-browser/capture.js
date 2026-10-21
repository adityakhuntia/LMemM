(function(root){
  function safeUrl(value){const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error('Only ordinary HTTP(S) pages can be saved.');return u.href;}
  function boundText(text,max=131072){let size=0,out='';for(const c of String(text)){const n=new TextEncoder().encode(c).length;if(size+n>max)return {text:out,truncated:true};out+=c;size+=n;}return {text:out,truncated:false};}
  // This function is serialized into the isolated world; keep helpers local.
  function capturePage(selectionOnly=false){
    const focused=document.activeElement;
    if(focused?.closest('input,textarea,[contenteditable="true"],[role="textbox"]'))throw Error('Select ordinary page text; form fields are not captured.');
    const selection=window.getSelection();let text='',kind='browser_page';
    if(selection&&!selection.isCollapsed){
      const node=selection.anchorNode?.parentElement;
      if(node?.closest('input,textarea,[contenteditable="true"],[role="textbox"]'))throw Error('Form fields are not captured.');
      text=selection.toString();kind='browser_selection';
    }else if(selectionOnly){throw Error('Highlight the text you want to save first.');}
    else{
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      const pieces=[];let node,total=0;
      while((node=walker.nextNode())&&total<160000){
        const el=node.parentElement;if(!el||el.closest('script,style,noscript,input,textarea,select,[contenteditable],[role="textbox"],[hidden],[aria-hidden="true"]'))continue;
        const style=getComputedStyle(el);if(style.visibility==='hidden'||style.display==='none'||!el.getClientRects().length)continue;
        const value=node.textContent.trim();if(value){pieces.push(value);total+=value.length;}
      }
      text=pieces.join('\n');
    }
    let out='',size=0,truncated=false;
    for(const c of text){const n=new TextEncoder().encode(c).length;if(size+n>131072){truncated=true;break;}out+=c;size+=n;}
    if(!out.trim())throw Error('No supported visible text found on this page.');
    return {text:out,kind,title:document.title.slice(0,512),url:location.href,truncated};
  }
  const api={safeUrl,boundText,capturePage};root.LMemMCapture=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
