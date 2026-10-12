"""Native evidence pane using the existing Figtree drawing kit."""
import time
from datetime import datetime,timezone

def friendly(at,now=None):
    """'2026-10-12T08:38:03+00:00' as 'Today, 08:38', 'Yesterday, 14:02' or '9 Oct, 10:00' in local time."""
    try:
        when=datetime.fromisoformat(str(at).replace('Z','+00:00'))
        if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
        when=when.astimezone();now=(now or datetime.now(timezone.utc)).astimezone()
    except (ValueError,TypeError):return str(at or '')
    days=(now.date()-when.date()).days;clock=when.strftime('%H:%M')
    if days==0:return 'Today, '+clock
    if days==1:return 'Yesterday, '+clock
    return '%d %s, %s'%(when.day,when.strftime('%b'),clock)

def short_name(locator,limit=26):
    """The file name of a source, cut in the middle when long."""
    name=str(locator or '').replace('\\','/').rstrip('/').rsplit('/',1)[-1]
    if len(name)<=limit:return name
    keep=(limit-1)//2;return name[:keep]+'…'+name[-keep:]

PERIOD_LABELS={'Last 2 days':'2 days','Last 7 days':'7 days','All retained':'All'}
STATE_LABELS={'Ready':'Remembering','Processing':'Processing','Paused':'Paused · nothing new is kept','Needs attention':'Needs attention'}
BLUE,VIOLET,ORANGE,TEAL,GREEN,RED,GRAY=(.20,.44,.96),(.54,.31,.88),(.91,.45,.16),(.06,.62,.54),(.18,.62,.36),(.90,.28,.30),(.50,.50,.55)
SECTIONS={'Search results':('Best matches',['magnifyingglass'],ORANGE),'Related evidence':('Related',['link'],TEAL),
          'Decisions':('Decisions',['flag.fill'],VIOLET),'Open tasks':('Open tasks',['checkmark.circle','checkmark.circle.fill'],BLUE),
          'Recent evidence':('Recent',['clock'],GRAY)}
CONFIRMS={'confirm_model':('Install meaning search?','Downloads about 46 MB (the MiniLM model) to LMemM’s own folder on this Mac. Needs Ollama installed. No notes or text are sent anywhere.','Install'),
          'confirm_agent':('Let Codex read this project’s memory?','Codex can search saved notes and sources and read the cited text. Using these tools sends that text to Codex and its provider. You can turn it off at any time.','Allow'),
          'confirm_disconnect':('Disconnect Memory for this project?','Stops capture and revokes agent access. Saved notes stay on this Mac but can’t be searched until you enable Memory again.','Disconnect')}
STATE_COLORS={'Ready':GREEN,'Processing':ORANGE,'Paused':GRAY,'Needs attention':RED}


def provenance(row):
    return 'Your note' if row.get('origin_type')=='user_note' else 'Observed content' if row.get('origin_type') else 'Supported by cited sources'

def evidence_rows(result):
    rows=[]
    for key,title in [('primary','Search results'),('related','Related evidence'),('decisions','Decisions'),('open_tasks','Open tasks'),('recent_evidence','Recent evidence')]:
        for row in result.get(key,[]):
            rows.append(dict(section=title,text=row.get('text',row.get('statement','')),at=row.get('at',''),
                citation_id=row.get('citation_id') or next(iter(row.get('citations',[])),None),reason=row.get('reason'),locator=row.get('locator',''),
                provenance=provenance(row),truncated=row.get('truncated',False)))
    return rows

def source_presentation(source):
    return dict(text=source['text'],locator=source['locator'],at=source['at'],open_enabled=source.get('can_open_file',False),
                provenance=provenance(source),truncated=source.get('truncated',False),
                open_explanation='This is the retained snapshot. Open file shows the file as it exists today.')

class MemoryPane:
    def __init__(self,on_action):
        from AppKit import NSTextField,NSMakeRect
        from widget import _Fields,_Flipped
        self.project=None;self.settings=False;self.confirm=None
        self.action=on_action;self.host=_Flipped.alloc().initWithFrame_(NSMakeRect(0,0,800,600))
        self.query_typing=_Fields.alloc().initWithChange_submit_cancel_(lambda text:self.action('query',{'text':text}),lambda text:self.action('submit',{}),lambda:self.action('query',{'text':''}))
        self.query=NSTextField.alloc().initWithFrame_(NSMakeRect(0,0,100,30));self.query.setDelegate_(self.query_typing)
        self.query.setPlaceholderString_('Ask your project…');self.query.setAccessibilityLabel_('Search project memory')
        self.note_typing=_Fields.alloc().initWithChange_submit_cancel_(lambda text:None,self._save_note,lambda:self.note.setStringValue_(''))
        self.note=NSTextField.alloc().initWithFrame_(NSMakeRect(0,0,100,30));self.note.setDelegate_(self.note_typing)
        self.note.setPlaceholderString_('Add a note… start with TODO: for a task, or “We decided … because …”');self.note.setAccessibilityLabel_('New intentional project note')
        self.host.addSubview_(self.query);self.host.addSubview_(self.note)
    def _save_note(self,text):
        if text.strip():self.action('note',{'text':text});self.note.setStringValue_('')
    def render(self,view,width=800,x=32,w=None):
        from AppKit import NSColor,NSMakeRect
        import setup_kit as kit
        w=w or width-64;host=self.host
        def rgb(c,alpha=1.0):return NSColor.colorWithRed_green_blue_alpha_(c[0],c[1],c[2],alpha)
        for sub in list(host.subviews()):
            if sub is not self.query and sub is not self.note:sub.removeFromSuperview()
        binding=view.get('binding');project=binding.get('project_id') if binding else None
        if project!=self.project:self.project=project;self.settings=False;self.confirm=None;self.note.setStringValue_('')
        if str(self.query.stringValue())!=view['query']:self.query.setStringValue_(view['query'])
        hide=not binding or self.settings
        self.query.setHidden_(hide);self.note.setHidden_(hide)
        y=8;self.bottom=None
        def panel(px,py,pw,ph,bar=None):
            box=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(px,py,pw,ph),lambda:None);box.fill=kit.faint(0.05);box.radius=10;host.addSubview_(box)
            if bar is not None:
                stripe=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(px,py+10,3,ph-20),lambda:None);stripe.fill=rgb(bar);stripe.radius=1.5;host.addSubview_(stripe)
        def label_row(symbols,color,text,at):
            kit.tile(host,symbols,rgb(color),x,at,22)
            kit.put_text(host,text.upper(),x+30,at+3,w-30,11,700,kit.mute(),wrap=False,height=16)
            return 30
        def card(text,meta,locator,citation,bar):
            nonlocal y
            inner=w-32;th=kit.text_height(text,15,500,inner);top=y
            panel(x,top,w,th+58,bar)
            kit.put_text(host,text,x+16,top+12,inner,15,500,height=th)
            my=top+th+20;kit.put_text(host,meta,x+16,my,kit.text_width(meta,11,400)+8,11,400,kit.mute(),wrap=False,height=16);cx=x+16+kit.text_width(meta,11,400)+14
            name=short_name(locator)
            if name:
                cw=kit.text_width(name,11,500)+26;chip=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(cx,my-2,cw,20),lambda:None);chip.fill=kit.faint(0.07);chip.radius=6;host.addSubview_(chip)
                glyph=kit.icon(kit.first_symbol(['doc.text','doc']),11,kit.mute(),(cx+7,my+1,12,13))
                if glyph is not None:host.addSubview_(glyph)
                kit.put_text(host,name,cx+22,my-2,cw-24,11,500,kit.mute(),wrap=False,height=20,middle=True)
            if citation:kit.button(host,'View source',x+w-104,my-4,92,24,lambda c=citation:self.action('source',{'citation_id':c}),kind='link',size=12,weight=600)
            y=top+th+58+10
        def para(text,size=13,weight=400,color=None,gap=10):
            nonlocal y
            y+=kit.put_text(host,str(text),x,y,w,size,weight,color or kit.mute())+gap
        mode=view['state']
        if not binding:
            y=40;cx=x+w/2
            kit.tile(host,['brain','sparkles'],rgb(ORANGE),cx-32,y,64);y+=84
            kit.put_text(host,'Give this project a memory',x,y,w,22,700,align=kit.CENTER,height=30);y+=38
            body='Choose one folder. LMemM keeps new text you view in VS Code and the notes you write here. It never scans the folder or imports history.'
            bw=min(w,420);y+=kit.put_text(host,body,cx-bw/2,y,bw,14,400,kit.mute(),align=kit.CENTER)+20
            kit.button(host,'Choose folder…',cx-90,y,180,40,lambda:self.action('choose_root'),kind='primary',size=15);y+=40
            if view.get('error'):y+=16;para(view['error'],13,500,rgb(RED))
        elif self.settings:self._settings(view,x,w,kit,rgb,panel)
        else:
            color=rgb(STATE_COLORS.get(mode,GREEN));label=STATE_LABELS.get(mode,mode)
            pw=kit.text_width(label,12,600)+34;chip=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(x,y,pw,26),lambda:None);chip.fill=rgb(STATE_COLORS.get(mode,GREEN),.14);chip.radius=13;host.addSubview_(chip)
            dot=kit.icon('circle.fill',7,color,(x+12,y+9,8,8))
            if dot is not None:host.addSubview_(dot)
            kit.put_text(host,label,x+24,y,pw-26,12,600,color,wrap=False,height=26,middle=True)
            bx=x+w
            if mode=='Needs attention':bx-=140;kit.button(host,'Recover notes',bx,y,132,26,lambda:self.action('recover_native_notes'),kind='link',size=12,weight=600)
            bx-=80;kit.button(host,'Refresh',bx,y,72,26,lambda:self.action('refresh'),kind='ghost',size=12,weight=600);y+=40
            if view.get('error'):para(view['error'],13,500,rgb(RED))
            if view.get('notice'):para(view['notice'][0],13,500,rgb(RED) if view['notice'][1] else kit.mute())
            glyph=kit.icon('magnifyingglass',16,rgb(ORANGE),(x+4,y+8,18,18))
            if glyph is not None:host.addSubview_(glyph)
            self.query.setFrame_(NSMakeRect(x+30,y,w-30,32));y+=46
            for i,period in enumerate(view['periods']):
                kit.button(host,PERIOD_LABELS.get(period,period),x+i*70,y,64,26,lambda p=period:self.action('time_filter',{'period':p}),kind='outline' if period==view['period'] else 'quiet',size=12,weight=600)
            y+=44
            if view['loading']:para('Loading permitted evidence…')
            if view['empty']:para(view['empty'],14,500)
            previous=None;source=view.get('source')
            for row in ([] if source else evidence_rows(view['result'])):
                if row['section']!=previous:
                    title,symbols,color_=SECTIONS.get(row['section'],(row['section'],['circle'],GRAY))
                    if previous is not None:y+=8
                    y+=label_row(symbols,color_,title,y);previous=row['section']
                meta=row['provenance']+(' · Truncated excerpt' if row['truncated'] else '')+(' · '+friendly(row['at']) if row['at'] else '')
                card(row['text'],meta,row['locator'],row['citation_id'],SECTIONS.get(row['section'],('',[],GRAY))[2])
            if source:
                p=source_presentation(source);y+=label_row(['doc.text'],ORANGE,'Retained source',y)
                inner=w-32;th=kit.text_height(p['text'],14,400,inner);top=y;panel(x,top,w,th+88,ORANGE)
                kit.put_text(host,p['text'],x+16,top+12,inner,14,400,height=th)
                kit.put_text(host,p['provenance']+(' · Truncated excerpt' if p['truncated'] else '')+' · '+friendly(p['at']),x+16,top+th+20,inner,11,400,kit.mute(),height=16)
                kit.put_text(host,short_name(p['locator'],60)+'   '+p['open_explanation'],x+16,top+th+40,inner,11,400,kit.mute(),height=34)
                y=top+th+98
                if p['open_enabled']:kit.button(host,'Open current file…',x,y,170,30,lambda c=source['citation_id']:self.action('open_file',{'citation_id':c}),kind='outline',size=13,weight=600)
                kit.button(host,'Close source',x+(180 if p['open_enabled'] else 0),y,120,30,lambda:self.action('close_source'),kind='quiet',size=13,weight=600);y+=46
            y+=14;y+=label_row(['note.text','doc.text'],ORANGE,'Add a note',y)
            self.note.setFrame_(NSMakeRect(x,y,w,32));y+=44
        if view.get('preview') and binding:self._preview(view,x,w,y,kit,panel)
        end=(self.bottom if self.bottom is not None else y)+40
        self.host.setFrame_(NSMakeRect(0,0,width,max(end,500)))
        return end
    def _preview(self,view,x,w,y,kit,panel):
        import json
        title='Proposed context for Codex · no access granted' if view['preview'].get('proposed') else 'Exact context preview for Codex'
        body=json.dumps(view['preview'],ensure_ascii=False,indent=2);th=kit.text_height(body,12,400,w-32)
        y+=12;y+=kit.put_text(self.host,title,x,y,w,14,700,height=20)+6
        panel(x,y,w,th+24);kit.put_text(self.host,body,x+16,y+12,w-32,12,400,height=th);y+=th+36
        kit.button(self.host,'Copy context preview',x,y,200,30,lambda:self.action('copy_preview'),kind='outline',size=13,weight=600);self.bottom=y+46
    def _settings(self,view,x,w,kit,rgb,panel):
        from AppKit import NSMakeRect
        host=self.host;y=8;notice=view.get('notice')
        kit.button(host,'‹  Memory',x,y,90,28,lambda:self.action('close_settings'),kind='link',size=14,weight=600);y+=40
        kit.put_text(host,'Memory settings',x,y,w,24,700,height=32);y+=48
        if self.confirm in CONFIRMS:
            title,detail,go=CONFIRMS[self.confirm];dh=kit.text_height(detail,13,400,w-32);top=y
            panel(x,top,w,dh+88,ORANGE)
            kit.put_text(host,title,x+16,top+14,w-32,15,700,wrap=False,height=20)
            kit.put_text(host,detail,x+16,top+38,w-32,13,400,kit.mute(),height=dh)
            kit.button(host,go,x+16,top+dh+50,110,30,lambda:self.action('confirm_yes'),kind='danger' if self.confirm=='confirm_disconnect' else 'primary',size=13,weight=600)
            kit.button(host,'Cancel',x+134,top+dh+50,90,30,lambda:self.action('confirm_no'),kind='quiet',size=13,weight=600);y=top+dh+88+14
        def row(symbols,color,title,sub,buttons,status=None,status_color=GREEN,sub_color=None,progress=False,fraction=None,seconds=0):
            nonlocal y
            widths=[kit.text_width(b[0],13,600)+30 for b in buttons];btn_w=sum(widths)+8*len(widths)
            sub_w=max(w-76-btn_w-(100 if status else 0),160);sh=kit.text_height(sub,12,400,sub_w);h=max(62,sh+46)+(14 if progress else 0)
            panel(x,y,w,h);kit.tile(host,symbols,rgb(color),x+16,y+(h-34)/2,34)
            kit.put_text(host,title,x+64,y+12,sub_w,14,600,wrap=False,height=18)
            kit.put_text(host,sub,x+64,y+32,sub_w,12,400,sub_color or kit.mute(),height=sh)
            if progress:                                       # a thin bar, filled from the left to the percentage
                bar_w=sub_w;by=y+h-20;track=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(x+64,by,bar_w,5),lambda:None);track.fill=kit.faint(0.10);track.radius=2.5;host.addSubview_(track)
                fw=bar_w*(fraction or 0)
                if fw>0:fill=kit._KitButton.alloc().initWithFrame_callback_(NSMakeRect(x+64,by,max(fw,5),5),lambda:None);fill.fill=rgb(color);fill.radius=2.5;host.addSubview_(fill)
            bx=x+w-14
            for item,bw in reversed(list(zip(buttons,widths))):
                label,action,kind=item[:3];on=item[3] if len(item)>3 else True
                bx-=bw;kit.button(host,label,bx,y+(h-30)/2-(7 if progress else 0),bw,30,lambda a=action:self.action(a),kind=kind,size=13,weight=600,enabled=on);bx-=8
            if status:kit.put_text(host,status,bx-96,y,92,12,600,rgb(status_color),align=kit.RIGHT,wrap=False,height=h,middle=True)
            y+=h+8
        def cap(text):
            nonlocal y
            y+=8;kit.put_text(host,text.upper(),x,y,w,11,700,kit.mute(),wrap=False,height=16);y+=24
        def note_for(kind,default):
            if notice and len(notice)>2 and notice[2]==kind:return notice[0],(rgb(RED) if notice[1] else None)
            return default,None
        mode=view['state'];root=(view.get('binding') or {}).get('workspace_root','')
        cap('Capture')
        row(['folder.fill','folder'],RED,'Folder',root,[('Resume' if mode=='Paused' else 'Pause','resume' if mode=='Paused' else 'pause','outline')],status=STATE_LABELS.get(mode,mode).split(' ·')[0],status_color=STATE_COLORS.get(mode,GREEN))
        installed=view.get('extension_installed');kind=notice[2] if notice and len(notice)>2 else None
        busy=bool(notice and kind in ('install_extension','connect_extension') and notice[0].endswith('…'))
        text,color=note_for('install_extension','Shares the text you view in the editor.')
        if kind=='connect_extension':text,color=notice[0],(rgb(RED) if notice[1] else None)
        if busy and kind=='install_extension':text='Installing in VS Code…'
        connected=view.get('status',{}).get('source_connected')
        if connected:
            row(['chevron.left.forwardslash.chevron.right','curlybraces'],BLUE,'VS Code','Sharing the text you view in the editor.',[],status='Connected')
        elif installed and not busy:
            row(['chevron.left.forwardslash.chevron.right','curlybraces'],BLUE,'VS Code',text,[('Connect','reconnect_extension','primary')],status='Installed',sub_color=color)
        else:
            row(['chevron.left.forwardslash.chevron.right','curlybraces'],BLUE,'VS Code',text,[('Working…' if busy else 'Install extension','install_extension','quiet' if busy else 'primary',not busy)],sub_color=color)
        status=view.get('status',{});ready=status.get('model_state')=='available';state=status.get('model_install')
        starting=bool(notice and len(notice)>2 and notice[2]=='install_model' and not notice[1])
        if state=='installing' or starting:
            percent=status.get('model_install_percent');secs=status.get('model_install_seconds') or 0
            text='Starting the download…' if state!='installing' else ('Downloading… %d%%'%percent if percent else 'Starting the download…')+' · %d:%02d'%(secs//60,secs%60)
            if secs>180:text+='. Taking longer than usual; check your connection.'
            row(['sparkles'],VIOLET,'Meaning search',text,[('Installing…','confirm_model','quiet',False)],progress=True,fraction=(percent or 0)/100,seconds=secs)
        elif state=='failed':
            row(['sparkles'],VIOLET,'Meaning search',status.get('model_install_message') or 'The install failed. Try again.',[('Try again','confirm_model','primary')],sub_color=rgb(RED))
        else:
            text,color=note_for('install_model','On. Finds notes by meaning, not just by words.' if ready else 'A 46 MB model that stays on this Mac. Needs Ollama installed first.')
            row(['sparkles'],VIOLET,'Meaning search',text,[] if ready else [('Install','confirm_model','primary')],status='On' if ready else None,sub_color=color)
        cap('Agents')
        row(['terminal.fill','terminal'],TEAL,'Codex','Can read this project’s notes and sources. You can turn it off at any time.',[('Preview','preview','outline'),('Revoke','revoke_agent','outline'),('Connect…','confirm_agent','primary')])
        cap('Danger zone')
        row(['bolt.slash.fill','xmark.circle'],RED,'Disconnect Memory','Stops capture and agent access. Saved notes stay on this Mac.',[('Disconnect…','confirm_disconnect','danger')])
        self.bottom=y
