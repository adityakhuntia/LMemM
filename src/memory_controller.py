"""Main-thread adapter between pure Memory navigation and asynchronous IPC."""
import time
from memory_model import new_memory_state,memory_reduce,memory_view,period_args

class MemoryController:
    def __init__(self,client,items,save):
        self.client=client;self.items=items;self.save=save;self.state=new_memory_state()
        self.bindings=[];self.status={};self.pending={};self.serial=0;self.last_poll=0;self.ui_project=None
        self.agents={};self.busy=None
    @property
    def agent(self):
        return next((a for a in self.agents.values() if self.binding and self.binding['project_id'] in a['project_ids'] and a.get('client_id','Codex')=='Codex'),None)
    @property
    def binding(self):
        return next((b for b in self.bindings if b['ui_project_id']==self.ui_project and b['active']),None)
    def send(self,method,params,kind,token=None):
        self.serial+=1;rid='memory-ui-'+str(self.serial)
        self.pending[rid]=(kind,token);self.client().request(method,params,rid)
    def select(self,ui_project):
        changed=self.ui_project!=ui_project;self.ui_project=ui_project
        self.state=memory_reduce(self.state,'select_project',{'project_id':ui_project})
        if changed and self.binding and self.state['tab']=='Memory':self.action('submit',{})
    def view(self):
        value=memory_view(self.state,self.binding,self.status if self.binding else {'state':'Disabled'},self.state['result'])
        if self.busy:value['busy']=self.busy
        return value
    def action(self,action,payload=None):
        payload=payload or {}
        if action=='enroll':self.busy='Enabling Memory…';self.send('enroll',{'ui_project_id':self.ui_project,'root':payload['root']},'enroll');return
        if action in {'pause','resume','install_model','install_extension','recover_native_notes'}:self.send(action,{},action);return
        if action=='refresh':
            retry=getattr(self.client(),'retry',None)
            if retry:retry()
            self.last_poll=0;self.action('submit',{});return
        if action=='note':
            if not self.binding:raise ValueError('Enable Memory first')
            from memory_notes import add_project_note
            add_project_note(self.items(),self.binding,payload['text']);self.save();self.status={'state':'Processing'};return
        if action=='disconnect':
            if self.binding:self.send('revoke_project',{'project_id':self.binding['project_id']},'disconnect')
            self.state=memory_reduce(self.state,'revoke',{});return
        if action=='open_file':
            if self.binding:self.send('resolve_citation',{'project_id':self.binding['project_id'],'citation_id':payload['citation_id']},'open',{'project_id':self.ui_project})
            return
        if action=='close_source':self.state['source']=None;return
        if action=='connect_agent':
            if not self.binding:raise ValueError('Enable Memory first')
            self.send('connect_agent',dict(client_id='Codex',project_ids=[self.binding['project_id']],app_ids=['com.microsoft.VSCode'],disclosure_approved=payload.get('approved') is True),'agent');return
        if action=='revoke_agent':
            for grant_id,connection in list(self.agents.items()):
                if self.binding and self.binding['project_id'] in connection['project_ids'] and connection.get('client_id','Codex')=='Codex':
                    self.send('revoke_agent',{'grant_id':grant_id},'revoke_agent');self.agents.pop(grant_id,None)
            return
        self.state=memory_reduce(self.state,action,payload)
        if action=='tab' and payload['tab']=='Memory':self.last_poll=0;self.action('submit',{})
        elif action=='time_filter':self.action('submit',{})
        elif action in {'submit','source','preview'} and self.binding:
            params={'project_id':self.binding['project_id']}
            if action=='source':method='resolve_citation';params['citation_id']=payload['citation_id']
            else:
                params.update(period_args(self.state['period']))
                method='get_project_context'
                if action=='submit' and self.state['query'].strip():method='search_project_memory';params['query']=self.state['query'].strip()
                if action=='preview':
                    method='preview_agent_context';params['client_id']='Codex'
                    if self.agent:params['grant_id']=self.agent['grant_id']
            self.send(method,params,'read',self.state['request'])
    def poll(self,events=None):
        changed=False
        for event in self.client().poll() if events is None else events:
            if event.get('type')=='ready':
                self.busy=None;self.last_poll=0;self.agents={};self.pending={};self.state=memory_reduce(self.state,'cancel',{});changed=True;continue
            if event.get('type')=='error':
                self.busy=None
                self.state=memory_reduce(self.state,'cancel',{});self.state['error']=event['error'];changed=True;continue
            entry=self.pending.pop(event.get('id'),None)
            if not entry:continue
            kind,token=entry;changed=True
            if kind=='enroll':self.busy=None
            if kind=='read':self.state=memory_reduce(self.state,'response',dict(request=token,result=event.get('result'),error=event.get('error')))
            elif event.get('error'):self.state['error']=event['error']
            elif kind=='bindings':
                self.bindings=event['result']
                if not self.binding:self.state=memory_reduce(self.state,'revoke',{})
            elif kind=='status':
                previous=(self.status.get('service_epoch'),self.status.get('policy_revision'),self.status.get('index_generation'))
                self.status=event['result']
                current=(self.status.get('service_epoch'),self.status.get('policy_revision'),self.status.get('index_generation'))
                if current!=previous:
                    self.state=memory_reduce(self.state,'generation',{'generation':current})
                    if self.binding and self.state['tab']=='Memory':self.action('submit',{})
            elif kind=='agents':self.agents={a['grant_id']:a for a in event['result']}
            elif kind=='agent':
                connection={k:v for k,v in event['result'].items() if k!='capability'}
                self.agents[connection['grant_id']]=connection
                if self.binding and self.binding['project_id'] in connection['project_ids']:self.state['preview']={'connection':connection}
            elif kind=='open':
                detail=event['result']
                if self.binding and token['project_id']==self.ui_project and detail.get('can_open_file'):
                    from pathlib import Path
                    path=Path(detail['locator']).resolve();root=Path(self.binding['workspace_root']).resolve()
                    if path.is_file() and path.is_relative_to(root):
                        from AppKit import NSWorkspace
                        from Foundation import NSURL
                        NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(str(path)))
            else:
                self.last_poll=0
                if kind=='enroll':self.bindings=[b for b in self.bindings if b['ui_project_id']!=event['result']['ui_project_id']]+[event['result']]
                if kind in {'enroll','recover_native_notes','resume'}:self.action('submit',{})
        if self.ui_project and time.monotonic()-self.last_poll>2:
            self.last_poll=time.monotonic();self.send('bindings',{},'bindings');self.send('status',{},'status');self.send('agent_connections',{},'agents')
        return changed
