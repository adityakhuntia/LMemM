"""Native evidence pane using the existing Figtree drawing kit."""

def evidence_rows(result):
    rows=[]
    for key,title in [('primary','Search results'),('related','Related evidence'),('decisions','Decisions'),('open_tasks','Open tasks'),('recent_evidence','Recent evidence')]:
        for row in result.get(key,[]):
            rows.append(dict(section=title,text=row.get('text',row.get('statement','')),at=row.get('at',''),
                citation_id=row.get('citation_id') or next(iter(row.get('citations',[])),None),reason=row.get('reason'),locator=row.get('locator','')))
    return rows

def source_presentation(source):
    return dict(text=source['text'],locator=source['locator'],at=source['at'],open_enabled=source.get('can_open_file',False),
                open_explanation='This is the retained snapshot. Open file shows the file as it exists today.')

class MemoryPane:
    def __init__(self,on_action):
        from AppKit import NSTextField,NSMakeRect
        from widget import _Fields,_Flipped
        self.project=None
        self.action=on_action;self.host=_Flipped.alloc().initWithFrame_(NSMakeRect(0,0,800,600))
        self.query_typing=_Fields.alloc().initWithChange_submit_cancel_(lambda text:self.action('query',{'text':text}),lambda text:self.action('submit',{}),lambda:self.action('query',{'text':''}))
        self.query=NSTextField.alloc().initWithFrame_(NSMakeRect(0,0,100,30));self.query.setDelegate_(self.query_typing)
        self.query.setPlaceholderString_('Search retained evidence · Return to search');self.query.setAccessibilityLabel_('Search project memory')
        self.note_typing=_Fields.alloc().initWithChange_submit_cancel_(lambda text:None,self._save_note,lambda:self.note.setStringValue_(''))
        self.note=NSTextField.alloc().initWithFrame_(NSMakeRect(0,0,100,30));self.note.setDelegate_(self.note_typing)
        self.note.setPlaceholderString_('Add a project note · Return to save');self.note.setAccessibilityLabel_('New intentional project note')
        self.host.addSubview_(self.query);self.host.addSubview_(self.note)
    def _save_note(self,text):
        if text.strip():self.action('note',{'text':text});self.note.setStringValue_('')
    def render(self,view,width=800,x=32,w=None):
        from AppKit import NSMakeRect
        import setup_kit as kit
        w=w or width-64;host=self.host
        for sub in list(host.subviews()):
            if sub is not self.query and sub is not self.note:sub.removeFromSuperview()
        y=16
        def text(value,size=13,weight=400,color=None):
            nonlocal y
            y+=kit.put_text(host,str(value),x,y,w,size,weight,color or kit.ink())+10
        def button(label,action,payload=None):
            nonlocal y
            kit.button(host,label,x,y,min(w,360),32,lambda:self.action(action,payload or {}),kind='outline',size=13,weight=500);y+=42
        text(view['state'],14,600)
        text(view['message'],13,400,kit.mute())
        if view.get('error'):text(view['error'],13,500)
        binding=view.get('binding')
        project=binding.get('project_id') if binding else None
        if project!=self.project:
            self.project=project;self.note.setStringValue_('')
        if str(self.query.stringValue())!=view['query']:self.query.setStringValue_(view['query'])
        self.query.setHidden_(not bool(binding));self.note.setHidden_(not bool(binding))
        if not binding:
            text('Choose one workspace folder. Only new permitted VS Code excerpts and intentional project notes are retained. No repository scan or history import.')
            button('Enable Memory · choose workspace…','choose_root')
        else:
            text(binding['workspace_root'],12,400,kit.mute())
            self.query.setFrame_(NSMakeRect(x,y,w,32));y+=44
            for i,period in enumerate(view['periods']):
                kit.button(host,period,x+i*(w/3+2),y,w/3-6,30,lambda p=period:self.action('time_filter',{'period':p}),kind='quiet' if period!=view['period'] else 'outline',size=12,weight=500)
            y+=44
            if view['loading']:text('Loading permitted evidence…',13,400,kit.mute())
            if view['empty']:text(view['empty'],14,500)
            previous=None
            for row in ([] if view.get('source') else evidence_rows(view['result'])):
                if row['section']!=previous:text(row['section'],15,700);previous=row['section']
                text(row['text'],14,500)
                if row['reason']:text(row['reason'],12,400,kit.mute())
                text(row['at']+'  '+row['locator'],11,400,kit.mute())
                if row['citation_id']:button('View retained source','source',{'citation_id':row['citation_id']})
            source=view.get('source')
            if source:
                p=source_presentation(source);text('Retained source',16,700);text(p['locator'],12);text(p['at'],12)
                text(p['text'],14);text(p['open_explanation'],12,400,kit.mute())
                if p['open_enabled']:button('Open current file…','open_file',{'citation_id':source['citation_id']})
                button('Close source','close_source')
            if view.get('preview'):
                import json
                text('Proposed context for Codex · no access granted' if view['preview'].get('proposed') else 'Exact context preview for Codex',16,700)
                text(json.dumps(view['preview'],ensure_ascii=False,indent=2),12)
                button('Copy context preview','copy_preview')
            text('Project notes',15,700)
            text('Use “TODO:” for an explicit task, or “We decided … because …” to record a decision and its reason.',12,400,kit.mute())
            self.note.setFrame_(NSMakeRect(x,y,w,32));y+=52
            button('Refresh evidence','refresh')
            if view['state']=='Needs attention':button('Recover saved notes','recover_native_notes')
            button('Resume Memory' if view['state']=='Paused' else 'Pause Memory','resume' if view['state']=='Paused' else 'pause')
            text('Semantic recall · local MiniLM model, approximately 46 MB. Stored in LMemM’s embedding-models folder. Installation is explicit; no cloud fallback.',12,400,kit.mute())
            button('Install local model…','confirm_model')
            button('Install VS Code source extension…','install_extension')
            button('Reconnect source sharing…','reconnect_extension')
            button('Preview context for Codex','preview')
            button('Connect Codex…','confirm_agent')
            button('Revoke Codex access','revoke_agent')
            button('Disconnect project Memory…','confirm_disconnect')
        self.host.setFrame_(NSMakeRect(0,0,width,max(y+24,500)))
        return y+24
