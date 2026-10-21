"""Native project front door, assembled only from retained evidence."""
from memory_view import friendly, provenance


class ResumePane:
    def __init__(self,on_action):
        from widget import _Flipped
        from AppKit import NSMakeRect
        self.action=on_action
        self.host=_Flipped.alloc().initWithFrame_(NSMakeRect(0,0,800,600))

    def render(self,view,width=800,x=32,w=None):
        from AppKit import NSMakeRect
        import setup_kit as kit
        w=w or width-64;y=16;host=self.host
        for sub in list(host.subviews()):sub.removeFromSuperview()
        def text(value,size=14,weight=400,muted=False):
            nonlocal y
            y+=kit.put_text(host,str(value),x,y,w,size,weight,kit.mute() if muted else None)+10
        def button(label,action,payload=None):
            nonlocal y
            kit.button(host,label,x,y,min(w,210),32,lambda:self.action(action,payload or {}),kind='outline',size=13)
            y+=42
        text('Pick up where you left off',22,700)
        text('Your saved activity, recorded decisions and next actions.',13,muted=True)
        if view.get('error'):text(view['error'],13,muted=True)
        if view.get('notice'):text(view['notice'][0],13,muted=True)
        if view.get('loading'):text('Loading saved project context…',13,muted=True)
        if view.get('state') in {'Paused','Needs attention'}:text(view.get('message',''),13,muted=True)
        toolbar=[('Copy context','copy_context'),('Add note or excerpt…','show_excerpt_form'),('Refresh','refresh')]
        for i,(label,action) in enumerate(toolbar):
            bw=min(180,(w-16)/3)
            kit.button(host,label,x+i*(bw+8),y,bw,32,lambda a=action:self.action(a,{}),kind='outline',size=13)
        y+=50
        source=view.get('source')
        if source:
            text('Retained source',17,700)
            text(source.get('title') or source['locator'],13,600)
            text(provenance(source)+' · '+friendly(source['at']),12,muted=True)
            # Keep UI responsive for long pages; retained evidence remains complete.
            text(source['text'][:12000]+('… (display shortened)' if len(source['text'])>12000 else ''),14)
            if source.get('url'):button('Open original URL…','open_original',{'citation_id':source['citation_id']})
            if source.get('can_open_file'):button('Open current file…','open_file',{'citation_id':source['citation_id']})
            if source.get('source_id'):
                for kind,label in [('task','Record as task'),('decision','Record as decision')]:
                    button(label,'record_claim',{'source_id':source['source_id'],'kind':kind,'start':0,'end':len(source['text'])})
            button('Close source','close_source')
        else:
            result=view.get('result') or {}
            if not any(result.get(k) for k in ('decisions','open_tasks','saved_activity')):
                text('Start with one useful note',17,700)
                text('Save a decision, a next action or a browser source. Your project context will appear here.',14,muted=True)
            for field,title in [('open_tasks','Next actions'),('decisions','Recorded decisions'),('saved_activity','Last saved activity')]:
                rows=result.get(field,[])
                if not rows:continue
                y+=14;text(title,17,700)
                for row in rows:
                    text(row.get('statement') or row.get('title') or row.get('text','')[:300],14,500)
                    if row.get('reason'):text('Reason: '+row['reason'],13,muted=True)
                    text(friendly(row.get('at'))+' · '+(provenance(row) if field=='saved_activity' else 'Supported by retained evidence'),12,muted=True)
                    ref=row.get('citation_id') or next(iter(row.get('citations',[])),None)
                    if ref:button('View source','source',{'citation_id':ref})
                    if field=='open_tasks':
                        native=row.get('native_note_id')
                        button('Mark done','complete_native_note' if native else 'set_task_state',
                               {'note_id':native,'done':True} if native else {'claim_id':row['id'],'done':True})
            if view.get('last_completed'):
                action,payload=view['last_completed'];button('Undo last completion',action,payload)
            related=result.get('related_sources',[])
            if related:
                y+=14;text('Connected sources',17,700)
                for row in related:
                    text(row['title'],14,500)
                    button('View referenced source','source',{'citation_id':row['citation_id']})
                    button('Remove connection','remove_relationship',{'edge_id':row['id']})
        self.host.setFrame_(NSMakeRect(0,0,width,max(500,y+32)))
        return y+32
