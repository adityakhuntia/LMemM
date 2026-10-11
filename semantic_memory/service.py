"""Single owning process for project intake, local indexing and authorized reads."""
import dataclasses
import fcntl
import inspect
import json
import os
import secrets
import threading
import time
from datetime import datetime,timezone
from pathlib import Path
from .api_contracts import MemoryStatus,ModelManifest,Query
from .contracts import AccessPolicy,SourceScope
from .live_bridge import Bridge,read_private_json,write_private_json
from .live_focus import focused_context
from .project_scope import bind_project
from .grants import enroll_grant,authorize,revoke_grant,revoke_project,revision,bump_revision
from .store import SemanticStore
from .chunks import index_source
from .index_worker import IndexWorker,schedule_source,paused
from .vector_index import begin_generation,activate_generation,active_generation
from .search import search_project,resolve_source
from .context_service import get_context,serialize_authorized
from .retention import enforce_budget,memory_usage

APP='com.microsoft.VSCode'
READ_METHODS=frozenset({'search_project_memory','get_project_context','resolve_citation'})


def timestamp(now):return datetime.fromtimestamp(now,timezone.utc).isoformat()


class MemoryService:
    def __init__(self,data_dir,owner_grant=None,backend_factory=None,focus_provider=None,clock=time.time):
        directory=Path(data_dir)
        if directory.is_symlink():raise ValueError('Private memory directory required')
        directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        if directory.stat().st_mode&0o777!=0o700 or directory.stat().st_uid!=os.getuid():raise ValueError('Private memory directory required')
        self.directory=directory.resolve();self.clock=clock
        self.lock_fd=os.open(self.directory/'pilot.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:os.close(self.lock_fd);raise
        self.closed=False;self.bridge=None;self.roots_dirty=True;self.backend=None;self.model_manifest=None
        self.model_thread=None;self.model_error=None;self.last_retention=clock();self.last_focus=None;self.system_flags=set()
        self.focus_provider=focus_provider or (lambda:focused_context(excluded_pids={os.getpid(),os.getppid()}))
        from .embedding_runtime import load_backend
        self.backend_factory=backend_factory or load_backend
        from .model_setup import OwnedEmbeddingRuntime
        self.runtime=OwnedEmbeddingRuntime(self.directory.parent/'embedding-models') if backend_factory is None else None
        self.setup_thread=None
        self.service_epoch=secrets.token_hex(16)
        try:
            self.store=SemanticStore(self.directory/'memory.sqlite')
            with self.store.transaction() as c:
                c.execute("DELETE FROM meta WHERE key='memory_paused' AND value='Stopped'")
            self.store.connection.execute('PRAGMA temp_store=MEMORY')
            # Reserve rollback/VACUUM/bridge overhead inside the total 250 MiB.
            page=self.store.connection.execute('PRAGMA page_size').fetchone()[0]
            self.store.connection.execute('PRAGMA max_page_count='+str((250*1024*1024-1024*1024)//(3*page)))
            path=self.directory/'capabilities.json'
            if path.exists():self.capabilities=read_private_json(path)
            else:
                self.capabilities={'owner':owner_grant or secrets.token_hex(32),'agents':{}}
                write_private_json(path,self.capabilities)
            self.owner_capability=self.capabilities['owner'];self.owner_grant_id=None
            # Recover databases written by versions that inserted binding 65
            # before checking the grant limit. Excess bindings stay visible but
            # disabled; recovery never broadens intake permission.
            with self.store.lock:
                overflow=self.store.connection.execute('SELECT project_id FROM project_bindings WHERE active=1 ORDER BY ui_project_id LIMIT -1 OFFSET 64').fetchall()
                for row in overflow:revoke_project(self.store,row[0])
            self._refresh_owner()
            from .note_sync import NativeNoteMirror
            self.native_notes=NativeNoteMirror(self)
            self.native_notes.publish_bindings()
            self.native_notes.sync_fences()
            model_path=self.directory/'model.json'
            if model_path.exists():
                try:
                    self.model_manifest=ModelManifest(**read_private_json(model_path))
                    self.backend=self.backend_factory(self.model_manifest)
                    if self.runtime:self.runtime.ensure()
                    self._ensure_model_generation(self.model_manifest)
                except (OSError,ValueError):self.model_error='Local model unavailable'
        except BaseException:
            if hasattr(self,'store'):self.store.close()
            os.close(self.lock_fd);raise

    @property
    def policy(self):
        row=self.store.connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
        return AccessPolicy(int(row[0]) if row else 1,frozenset({APP}),frozenset())

    def _refresh_owner(self):
        pids={r[0] for r in self.store.connection.execute('SELECT project_id FROM project_bindings WHERE active=1')}
        if pids:self.owner_grant_id=enroll_grant(self.store,'native-owner',pids,SourceScope(frozenset({APP}))).id

    def _role(self,capability):
        if not isinstance(capability,str) or len(capability)>256:raise ValueError('unavailable')
        if secrets.compare_digest(capability,self.owner_capability):return 'owner',self.owner_grant_id
        agent=self.capabilities['agents'].get(capability)
        if agent:return 'agent',agent['grant_id']
        raise ValueError('unavailable')

    def serve_request(self,capability,method,params):
        if self.closed or not isinstance(params,dict):raise ValueError('unavailable')
        role,grant_id=self._role(capability)
        if method in READ_METHODS:
            self.native_notes.sync_fences()
            allowed={'search_project_memory':{'project_id','query','start','end','limit'},'get_project_context':{'project_id','start','end'},'resolve_citation':{'project_id','citation_id'}}[method]
            if set(params)-allowed or 'project_id' not in params:raise ValueError('Invalid memory arguments')
            ctx=authorize(self.store,grant_id,params['project_id'])
            if method=='search_project_memory':
                from .context_service import time_bounds
                start,end=time_bounds(params.get('start'),params.get('end'))
                q=Query(params['project_id'],params.get('query',''),start,end,params.get('limit',10))
                result=search_project(self.store,self.backend,ctx,q)
            elif method=='get_project_context':result=get_context(self.store,ctx,params['project_id'],params.get('start'),params.get('end'))
            else:
                with self.store.lock:
                    detail=resolve_source(self.store,ctx,params['project_id'],params.get('citation_id'))
                    if detail is None:raise ValueError('unavailable')
                    self.native_notes.sync_fences()
                    detail=resolve_source(self.store,ctx,params['project_id'],params.get('citation_id'))
                    if detail is None:raise ValueError('unavailable')
                    return dataclasses.asdict(detail)
            self.native_notes.sync_fences()
            return json.loads(serialize_authorized(self.store,ctx,result))
        if role!='owner':raise ValueError('unavailable')
        handlers={'enroll':self.enroll,'bindings':self.bindings,'status':self.status,'pause':self.pause,'resume':self.resume,
                  'configure_model':self.configure_model,'connect_agent':self.connect_agent,'agent_connections':self.agent_connections,'revoke_agent':self.revoke_agent,'revoke_project':self.revoke_project,'begin_note_mutation':self.begin_note_mutation,'reconcile_notes':self.reconcile_notes,'recover_native_notes':self.recover_native_notes,'install_model':self.install_model,'install_extension':self.install_extension,'preview_agent_context':self.preview_agent_context}
        handler=handlers.get(method)
        if not handler:raise ValueError('unavailable')
        try:inspect.signature(handler).bind(**params)
        except TypeError as error:raise ValueError('Invalid memory arguments') from error
        return handler(**params)

    def enroll(self,ui_project_id,root):
        # Intake enrollment is an explicit native action, never an agent call.
        path=Path(root)
        if not path.is_dir():raise ValueError('Choose a local workspace folder')
        from memory_notes import native_sync_lock
        from .project_scope import set_binding_active,resolve_binding
        # Lock order is always native writer lock, then store lock.
        with native_sync_lock(self.directory),self.store.lock:
            prior=resolve_binding(self.store,ui_project_id)
            if (prior is None or not prior.active) and self.store.connection.execute('SELECT count(*) FROM project_bindings WHERE active=1').fetchone()[0]>=64:
                raise ValueError('At most 64 projects can have Memory enabled')
            binding=bind_project(self.store,ui_project_id,str(path),timestamp(self.clock()))
            if not binding.active:
                set_binding_active(self.store,ui_project_id,True);binding=resolve_binding(self.store,ui_project_id)
                try:self.native_notes.queue_reconciliation(binding.project_id)
                except (OSError,ValueError):
                    set_binding_active(self.store,ui_project_id,False);raise
            self._refresh_owner();self.roots_dirty=True;self.native_notes.publish_bindings()
        return dataclasses.asdict(binding)

    def bindings(self):
        with self.store.lock:return [dict(row) for row in self.store.connection.execute('SELECT * FROM project_bindings ORDER BY ui_project_id')]

    def connect_agent(self,client_id,project_ids,app_ids,disclosure_approved=False):
        with self.store.lock:return self._connect_agent(client_id,project_ids,app_ids,disclosure_approved)

    def _connect_agent(self,client_id,project_ids,app_ids,disclosure_approved):
        self._prune_agents()
        if disclosure_approved is not True or set(app_ids)!={APP}:raise ValueError('Explicit agent disclosure approval required')
        if len(self.capabilities['agents'])>=8:raise ValueError('At most eight active agent connections are supported; revoke one first')
        grant=enroll_grant(self.store,client_id,project_ids,SourceScope(frozenset(app_ids)))
        token=secrets.token_hex(32);self.capabilities['agents'][token]={'grant_id':grant.id}
        write_private_json(self.directory/'capabilities.json',self.capabilities)
        clients=self.directory/'clients';clients.mkdir(mode=0o700,exist_ok=True)
        config_path=clients/(grant.id+'.json')
        write_private_json(config_path,{'service_file':str(self.directory/'service.json'),'capability':token,'project_ids':sorted(grant.project_ids)})
        return {'capability':token,'grant_id':grant.id,'project_ids':sorted(grant.project_ids),'config_path':str(config_path)}

    def _prune_agents(self):
        stale=[token for token,value in self.capabilities['agents'].items() if not self.store.connection.execute('SELECT 1 FROM memory_grants WHERE id=? AND revoked=0',(value['grant_id'],)).fetchone()]
        for token in stale:
            value=self.capabilities['agents'].pop(token)
            (self.directory/'clients'/(value['grant_id']+'.json')).unlink(missing_ok=True)
        if stale:write_private_json(self.directory/'capabilities.json',self.capabilities)

    def agent_connections(self):
        # Owner-only inventory contains no bearer capabilities.
        with self.store.lock:
            self._prune_agents();connections=[]
            for value in self.capabilities['agents'].values():
                row=self.store.connection.execute('SELECT * FROM memory_grants WHERE id=?',(value['grant_id'],)).fetchone()
                connections.append({'grant_id':row['id'],'client_id':row['client_id'],'project_ids':json.loads(row['project_ids']),'config_path':str(self.directory/'clients'/(row['id']+'.json'))})
            return connections

    def preview_agent_context(self,project_id,client_id,start=None,end=None,grant_id=None):
        self.native_notes.sync_fences()
        if grant_id:
            from .grants import current_grant
            ctx=authorize(self.store,grant_id,project_id)
            if current_grant(self.store,ctx,project_id).client_id!=client_id:raise ValueError('unavailable')
        else:ctx=authorize(self.store,self.owner_grant_id,project_id)
        packet=get_context(self.store,ctx,project_id,start,end)
        self.native_notes.sync_fences()
        return {'proposed':grant_id is None,'client_id':client_id,'project_ids':[project_id],
                'policy_revision':ctx.policy_revision,'packet':json.loads(serialize_authorized(self.store,ctx,packet))}

    def revoke_agent(self,grant_id):
        with self.store.lock:
            result={'revision':revoke_grant(self.store,grant_id)};self._prune_agents();return result

    def revoke_project(self,project_id):
        result={'revision':revoke_project(self.store,project_id)};self.roots_dirty=True;self._refresh_owner();self.native_notes.publish_bindings();return result

    def begin_note_mutation(self,project_id,mutation_id):
        self.native_notes.fence(project_id,mutation_id)
        return {'state':'Processing'}

    def reconcile_notes(self,project_id,snapshots,mutation_id):
        return dataclasses.asdict(self.native_notes.reconcile(project_id,snapshots,mutation_id))

    def recover_native_notes(self):
        return {'reconciled':self.native_notes.sync_pending(recover=True)}

    def install_model(self):
        if not self.runtime:raise ValueError('Local runtime unavailable')
        if self.setup_thread and self.setup_thread.is_alive():return {'state':'Processing'}
        self.model_error='Installing local model'
        def install():
            try:
                manifest=self.runtime.install()
                if not self.closed:self.configure_model(dataclasses.asdict(manifest))
            except Exception:self.model_error='Local model installation failed; check Ollama and retry'
        self.setup_thread=threading.Thread(target=install,daemon=True);self.setup_thread.start()
        return {'state':'Processing'}

    def install_extension(self):
        from .model_setup import install_extension
        return install_extension(self.directory.parent)

    def configure_model(self,manifest):
        manifest=ModelManifest(**manifest)
        backend=self.backend_factory(manifest)  # Validates installed assets, never downloads.
        if self.runtime:self.runtime.ensure()
        if self.model_thread and self.model_thread.is_alive():raise ValueError('Indexing is busy; pause before changing model')
        with self.store.lock:
            # Persist the desired manifest first; startup reconciles any interrupted
            # generation transaction against this durable configuration intent.
            write_private_json(self.directory/'model.json',dataclasses.asdict(manifest))
            self.model_manifest=manifest;self.backend=backend;self.model_error=None
            try:self._ensure_model_generation(manifest)
            except (OSError,ValueError):
                self.backend=None;self.model_error='Local index configuration interrupted; restart Memory to recover';raise
        return {'state':'Processing','model_id':manifest.model_id}

    def _ensure_model_generation(self,manifest):
        with self.store.lock:
            row=self.store.connection.execute("SELECT manifest FROM index_generations WHERE state IN ('building','active') ORDER BY CASE state WHEN 'building' THEN 0 ELSE 1 END LIMIT 1").fetchone()
            if row is None or json.loads(row['manifest'])!=dataclasses.asdict(manifest):begin_generation(self.store,manifest)

    def pause(self,reason='Paused by user'):
        with self.store.transaction() as c:
            c.execute("INSERT OR REPLACE INTO meta VALUES('memory_paused',?)",(reason,))
            bump_revision(c)
        if self.backend:self.backend.cancel()
        self.roots_dirty=True
        return {'state':'Paused'}

    def resume(self):
        if self.system_flags:raise ValueError('Resume after unlocking or waking the Mac')
        if self.model_thread and self.model_thread.is_alive():raise ValueError('Wait for cancelled indexing to finish')
        if self.model_manifest:self.backend=self.backend_factory(self.model_manifest)
        with self.store.transaction() as c:
            c.execute("DELETE FROM meta WHERE key='memory_paused'")
            c.execute("UPDATE index_jobs SET state='queued',error=NULL WHERE state IN ('running','failed')")
            bump_revision(c)
        self.roots_dirty=True
        return {'state':'Processing' if self.backend else 'Ready'}

    def status(self):
        with self.store.lock:
            c=self.store.connection
            pending=c.execute("SELECT count(*) FROM index_jobs WHERE state IN ('queued','running')").fetchone()[0]
            failed=c.execute("SELECT count(*) FROM index_jobs WHERE state='failed'").fetchone()[0]
            first=c.execute('SELECT min(at) FROM sources').fetchone()[0]
            enrolled=c.execute('SELECT min(enrolled_at) FROM project_bindings WHERE active=1').fetchone()[0]
            is_paused=paused(self.store)
            pending+=c.execute('SELECT count(*) FROM note_fences').fetchone()[0]
            reason='Paused by user' if is_paused else self.model_error
            state='Paused' if is_paused else 'Needs attention' if failed or self.model_error else 'Processing' if pending else 'Ready' if enrolled else 'Disabled'
            journal=self.directory/'native-notes.pending.json'
            if not is_paused and journal.exists() and read_private_json(journal).get('phase')=='preparing':
                state='Needs attention';reason='A note save was interrupted. Recover saved notes to reconcile Memory.'
            generation=active_generation(self.store)
            value=dataclasses.asdict(MemoryStatus(state,reason,generation['created_at'] if generation else None,enrolled,pending,failed,'available' if self.backend else 'missing',first,memory_usage(self.store)['total_bytes']))
            from .grants import revision
            value.update(service_epoch=self.service_epoch,policy_revision=revision(c),index_generation=generation['id'] if generation else None)
            return value

    def _sync_bridge(self):
        with self.store.lock:self._sync_bridge_locked()

    def _sync_bridge_locked(self):
        if self.bridge:
            self.bridge.active=False;self.bridge.publish_grant()
        roots=[Path(r[0]) for r in self.store.connection.execute('SELECT workspace_root FROM project_bindings WHERE active=1')]
        roots=[p for p in roots if p.is_dir()]
        if roots:
            self.bridge=Bridge(self.directory/'bridge',roots,self.clock)
            self.bridge.revision=self.policy.revision;self.bridge.active=not paused(self.store);self.bridge.open_session()
        else:self.bridge=None
        self.roots_dirty=False

    def _ingest_capture(self,envelope,capture_revision):
        with self.store.lock:
            if self.closed or paused(self.store) or revision(self.store.connection)!=capture_revision:raise ValueError('Capture no longer authorized')
            if not self.store.connection.execute('SELECT 1 FROM project_bindings WHERE workspace_root=? AND active=1',(envelope.workspace_locator,)).fetchone():raise ValueError('Capture no longer authorized')
            result=self.store.ingest(envelope,self.policy);schedule_source(self.store,result.source_id)
            return result

    def tick(self):
        if self.closed:return
        if threading.current_thread() is not threading.main_thread():raise RuntimeError('Native intake must run on the main thread')
        self.native_notes.sync_pending()
        if self.roots_dirty:self._sync_bridge()
        if self.bridge and not paused(self.store):
            focus=self.focus_provider()
            if focus!=self.last_focus:self.bridge.last.clear();self.last_focus=focus
            for path in sorted((self.bridge.directory/'events').glob('*.json'))[:8]:
                try:
                    message=read_private_json(path)
                    if path.stem!=message.get('client'):continue
                    before=self.focus_provider()
                    if focus!=before:continue
                    with self.store.lock:capture_revision=revision(self.store.connection)
                    envelope=self.bridge.accept(message,before)
                    after=self.focus_provider()
                    if message.get('kind')=='connect' and (before!=after or after is None or 'LMemM '+message['client'] not in after.title):
                        self.bridge.clients.pop(message['client'],None)
                        (self.bridge.directory/'acks'/(message['client']+'.json')).unlink(missing_ok=True);continue
                    if envelope and before==after:
                        self._ingest_capture(envelope,capture_revision)
                        write_private_json(self.bridge.directory/'acks'/(message['client']+'.json'),{'session':self.bridge.session,'window':after.window,'seq':message['seq'],'accepted':True,'note_id':message.get('note_id'),'revision':self.policy.revision})
                except (ValueError,OSError,RuntimeError):continue
            self.bridge.expire()
        if self.clock()-self.last_retention>=30:
            enforce_budget(self.store,timestamp(self.clock()));self.last_retention=self.clock()
        if self.backend and not paused(self.store) and (self.model_thread is None or not self.model_thread.is_alive()):
            with self.store.lock:
                pending=self.store.connection.execute("SELECT 1 FROM index_jobs WHERE state IN ('queued','running') LIMIT 1").fetchone()
                building=self.store.connection.execute("SELECT id FROM index_generations WHERE state='building'").fetchone()
            if pending:
                self.model_thread=threading.Thread(target=self._index_one,daemon=True);self.model_thread.start()
            elif building:
                try:activate_generation(self.store,building[0])
                except ValueError:pass

    def _index_one(self):
        try:IndexWorker(self.store,self.backend).run_one()
        except Exception:self.model_error='Local index unavailable'

    def close(self):
        if self.closed:return
        if not paused(self.store):self.pause('Stopped')
        elif self.backend:self.backend.cancel()
        if self.bridge:self.bridge.active=False;self.bridge.publish_grant()
        if self.model_thread:self.model_thread.join(35)
        if self.model_thread and self.model_thread.is_alive():raise RuntimeError('Index shutdown deadline exceeded')
        self.closed=True
        if self.runtime:self.runtime.close()
        self.store.close();os.close(self.lock_fd)
