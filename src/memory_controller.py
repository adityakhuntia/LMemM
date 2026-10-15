"""Main-thread adapter between pure Memory navigation and asynchronous IPC."""
import time
from memory_model import new_memory_state,memory_reduce,memory_view,period_args

def codex_binary():
    """The `codex` program, found the way a person's shell would (an app launched from the Dock has a short PATH)."""
    import os,shutil
    if os.environ.get('LMEMM_NO_CODEX'):return None                  # tests must never touch a real Codex
    home=os.path.expanduser('~')
    extra=['/opt/homebrew/bin','/usr/local/bin',home+'/.local/bin',home+'/.npm-global/bin',home+'/.bun/bin']
    found=shutil.which('codex',path=os.pathsep.join([os.environ.get('PATH','')]+extra))
    if found:return found
    for app in ('/Applications/ChatGPT.app','/Applications/Codex.app',home+'/Applications/ChatGPT.app',home+'/Applications/Codex.app'):          # the desktop app carries its own copy
        for inside in ('Contents/Resources/codex-cli/bin/codex','Contents/Resources/codex','Contents/Resources/bin/codex','Contents/MacOS/codex','Contents/Resources/app/bin/codex'):
            path=os.path.join(app,inside)
            if os.path.isfile(path) and os.access(path,os.X_OK):return path
    return None

def codex_args(config_path):
    """The program and arguments that add LMemM's memory to Codex."""
    import sys
    from pathlib import Path
    adapter=Path(__file__).resolve().parent.parent/'scripts'/'project_memory_mcp.py'
    return ['mcp','add','lmemm_memory','--',sys.executable,str(adapter),'--config',str(config_path)]

def codex_command(config_path):
    """The same thing as one line to paste in Terminal: the fallback when LMemM cannot add itself."""
    import shlex
    return ' '.join(['codex']+[shlex.quote(a) if a!='--' else a for a in codex_args(config_path)])

class MemoryController:
    def __init__(self,client,items,save):
        self.client=client;self.items=items;self.save=save;self.state=new_memory_state()
        self.bindings=[];self.status={};self.pending={};self.serial=0;self.last_poll=0;self.ui_project=None
        self.agents={};self.codex=None;self.ax_trusted=True;self.busy=None;self.notice=None;self.notice_at=0;self.notice_version=0;self.seen_notice=0;self.vscode_restart=False
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
    def set_notice(self,text,error=False,kind=None):
        self.notice=(text,error,kind) if text else None;self.notice_version+=1;self.notice_at=time.monotonic()
    def install_extension(self):
        # Built and installed by the app itself: it touches no memory data, and the service
        # hides error details from the app, which would hide why an install failed.
        import threading
        from pathlib import Path
        self.set_notice('Installing…',False,'install_extension')
        directory=Path(self.client().directory).parent
        def work():
            try:
                from semantic_memory.model_setup import install_extension,vscode_running
                install_extension(directory);self.vscode_restart=vscode_running();self.set_notice(None)
            except ValueError as error:self.set_notice(str(error),True,'install_extension')
            except Exception:self.set_notice('Could not install the VS Code extension.',True,'install_extension')
        threading.Thread(target=work,daemon=True).start()
    def connect_extension(self):
        # One press: copy the grant path (the manual fallback), quit a running VS Code so a freshly started one loads the
        # current extension (a running one may hold an old copy), then open vscode://… which VS Code asks the person to allow.
        import subprocess,threading,urllib.parse
        from pathlib import Path
        if self.status.get('state')=='Paused':
            self.set_notice('Memory is paused. Resume it in the Folder row above, then press Connect.',True,'connect_extension');return
        self.set_notice('Connecting…',False,'connect_extension')
        grant=str(Path(self.client().directory)/'bridge'/'grant.json')
        def work():
            try:
                from semantic_memory.model_setup import quit_vscode,vscode_running
                subprocess.run(['pbcopy'],input=grant.encode(),timeout=5)
                if vscode_running() and not quit_vscode():
                    raise ValueError('VS Code is still open. Save or close what it asks about, then press Connect again.')
                self.vscode_restart=False
                subprocess.run(['open','vscode://lmemm.lmemm-source/connect?grant='+urllib.parse.quote(grant)],timeout=10,check=True)
                self.set_notice('Opened VS Code. Choose Allow there to finish.',False,'connect_extension')
            except ValueError as error:self.set_notice(str(error),True,'connect_extension')
            except Exception:self.set_notice('Could not open VS Code. The path is copied: in VS Code run “LMemM: Connect Project Memory” and paste it.',True,'connect_extension')
        threading.Thread(target=work,daemon=True).start()
    @staticmethod
    def _accessibility():
        try:
            import permissions
            return bool(permissions.accessibility_trusted())
        except Exception:return True                 # unknown is not "off": never block on a guess
    def _touch(self):self.notice_version+=1
    def add_to_codex(self,config_path):
        # Runs Codex's own `mcp add`: it edits Codex's settings, so it only runs after the person pressed
        # "Allow and add to Codex". If it cannot, the card shows the same line to paste instead.
        import subprocess,threading
        self.codex={'state':'adding'};self._touch()
        def work():
            try:
                binary=codex_binary()
                if not binary:raise FileNotFoundError('Codex was not found on this Mac')
                subprocess.run([binary,'mcp','remove','lmemm_memory'],capture_output=True,timeout=30)      # an older grant's entry
                done=subprocess.run([binary]+codex_args(config_path),capture_output=True,text=True,timeout=30)
                if done.returncode!=0:raise RuntimeError((done.stderr or done.stdout or 'Codex refused').strip().splitlines()[-1][:160])
                self.codex={'state':'added'}
            except FileNotFoundError:self.codex={'state':'failed','message':'Codex was not found on this Mac.'}
            except Exception as error:self.codex={'state':'failed','message':str(error) or 'Codex did not accept it.'}
            self._touch()
        threading.Thread(target=work,daemon=True).start()
    def remove_from_codex(self):
        import subprocess,threading
        def work():
            try:
                binary=codex_binary()
                if binary:subprocess.run([binary,'mcp','remove','lmemm_memory'],capture_output=True,timeout=30)
            except Exception:pass
        threading.Thread(target=work,daemon=True).start()
    def view(self):
        view=memory_view(self.state,self.binding,self.status if self.binding else {'state':'Disabled'},self.state['result'])
        view['notice']=self.notice;view['accessibility']=self.ax_trusted;view['codex_connected']=bool(self.binding and self.agent)
        if self.codex and (view.get('preview') or {}).get('connection'):view['preview']['connection']['codex']=self.codex
        if self.busy:view['busy']=self.busy
        try:
            from semantic_memory.model_setup import extension_installed
            view['extension_installed']=extension_installed()
        except Exception:view['extension_installed']=False
        return view
    def action(self,action,payload=None):
        payload=payload or {}
        if action=='enroll':self.busy='Enabling Memory…';self.send('enroll',{'ui_project_id':self.ui_project,'root':payload['root']},'enroll');return
        if action=='install_extension':self.install_extension();return
        if action=='reconnect_extension':self.connect_extension();return
        if action=='install_model':self.set_notice('Starting…',False,'install_model')
        if action in {'pause','resume','install_model','recover_native_notes'}:self.send(action,{},action);return
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
        if action=='close_preview':self.state['preview']=None;return
        if action=='connect_agent':
            if not self.binding:raise ValueError('Enable Memory first')
            self.send('connect_agent',dict(client_id='Codex',project_ids=[self.binding['project_id']],app_ids=['com.microsoft.VSCode'],disclosure_approved=payload.get('approved') is True),'agent');return
        if action=='revoke_agent':
            for grant_id,connection in list(self.agents.items()):
                if self.binding and self.binding['project_id'] in connection['project_ids'] and connection.get('client_id','Codex')=='Codex':
                    self.send('revoke_agent',{'grant_id':grant_id},'revoke_agent');self.agents.pop(grant_id,None);self.remove_from_codex();self.codex=None
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
        trusted=self._accessibility()
        if trusted!=self.ax_trusted:self.ax_trusted=trusted;changed=True        # the person just switched it on in System Settings
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
            elif event.get('error'):
                if kind=='install_model':self.set_notice('Could not start the model install. Refresh Memory and try again.',True,kind)
                else:self.state['error']=event['error']
            elif kind=='bindings':
                self.bindings=event['result']
                if not self.binding:self.state=memory_reduce(self.state,'revoke',{})
            elif kind=='status':
                previous=(self.status.get('service_epoch'),self.status.get('policy_revision'),self.status.get('index_generation'))
                self.status=event['result']
                if self.notice and self.notice[2]=='connect_extension' and self.status.get('source_connected'):self.set_notice(None)
                if self.notice and self.notice[2]=='install_model' and (self.status.get('model_install') or self.status.get('model_state')=='available'):self.set_notice(None)
                current=(self.status.get('service_epoch'),self.status.get('policy_revision'),self.status.get('index_generation'))
                if current!=previous:
                    self.state=memory_reduce(self.state,'generation',{'generation':current})
                    if self.binding and self.state['tab']=='Memory':self.action('submit',{})
            elif kind=='agents':self.agents={a['grant_id']:a for a in event['result']}
            elif kind=='agent':
                connection={k:v for k,v in event['result'].items() if k!='capability'}
                self.agents[connection['grant_id']]=connection
                if self.binding and self.binding['project_id'] in connection['project_ids']:self.state['preview']={'connection':dict(connection,command=codex_command(connection['config_path']))};self.add_to_codex(connection['config_path'])
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
        if self.notice and self.notice[2]=='connect_extension' and not self.notice[1] and self.notice[0].startswith('Opened VS Code') and time.monotonic()-self.notice_at>25:
            why=self.status.get('focus_blocker')              # the service says which check failed
            self.set_notice('Still waiting for VS Code to be verified. '+(why+' ' if why else '')+'Fix that, then press Connect again.',True,'connect_extension')
        if self.seen_notice!=self.notice_version:self.seen_notice=self.notice_version;changed=True
        if self.ui_project and time.monotonic()-self.last_poll>2:
            self.last_poll=time.monotonic();self.send('bindings',{},'bindings');self.send('status',{},'status');self.send('agent_connections',{},'agents')
        return changed
