"""Reconcile eligible native JSON notes behind durable project read fences."""
import dataclasses
import json
import os
from pathlib import Path
import secrets
from .api_contracts import ProjectBinding,NoteSnapshot,SyncResult,valid_id
from .contracts import SourceEnvelope,TextSpan,Correction
from .grants import bump_revision
from .live_bridge import read_private_json,write_private_json
from .policy import utc
from .retention import delete_memory_source
from .index_worker import schedule_source,paused
from .relationships import apply_correction


class NativeNoteMirror:
    def __init__(self,service):self.service=service;self.store=service.store;self.directory=service.directory

    def publish_bindings(self):
        from memory_notes import snapshot_hash
        bindings=self.service.bindings()
        for binding in bindings:
            binding['retained_count']=self.store.connection.execute('SELECT count(*) FROM sources WHERE project_id=?',(binding['project_id'],)).fetchone()[0]
        write_private_json(self.directory/'native-bindings.json',{'bindings':bindings})
        path=self.directory/'native-note-state.json'
        state=read_private_json(path) if path.exists() else {}
        for binding in bindings:state.setdefault(binding['project_id'],snapshot_hash(()))
        write_private_json(path,state)

    def fence(self,project_id,mutation_id):
        valid_id(mutation_id)
        with self.store.transaction() as c:
            if not c.execute('SELECT 1 FROM project_bindings WHERE project_id=? AND active=1',(project_id,)).fetchone():raise ValueError('unavailable')
            prior=c.execute('SELECT mutation_id FROM note_fences WHERE project_id=?',(project_id,)).fetchone()
            if not prior or prior[0]!=mutation_id:
                c.execute('INSERT OR REPLACE INTO note_fences VALUES(?,?)',(project_id,mutation_id));bump_revision(c)

    def sync_fences(self):
        # Observation and fencing share the same lock as journal consumption.
        # A reader must never reinstall a fence for an already consumed marker.
        with self.store.lock:return self._sync_fences_locked()

    def _sync_fences_locked(self):
        path=self.directory/'native-notes.pending.json'
        if not path.exists():return None
        marker=read_private_json(path)
        if marker.get('version')!=1 or marker.get('phase') not in {'preparing','committed'} or not isinstance(marker.get('projects'),list) or len(marker['projects'])>64:
            raise ValueError('Invalid native note journal')
        active={b['project_id'] for b in self.service.bindings() if b['active']}
        for pid in marker['projects']:
            if pid in active:self.fence(pid,marker['mutation_id'])
        return marker

    def _authority(self):
        path=self.directory.parent/'memory'/'memory.json'
        if not path.exists():return {}
        if path.is_symlink() or path.stat().st_size>16*1024*1024:raise ValueError('Native note authority unavailable')
        document=json.loads(path.read_text())
        if not isinstance(document.get('items'),list):raise ValueError('Native note authority unavailable')
        return {item['id']:item for item in document['items']}

    def reconcile(self,project_id,snapshots,mutation_id):
        with self.store.lock:return self._reconcile_locked(project_id,snapshots,mutation_id)

    def _reconcile_locked(self,project_id,snapshots,mutation_id):
        from memory_notes import project_snapshot
        self.fence(project_id,mutation_id)
        if paused(self.store):return SyncResult(0,len(snapshots),0)
        row=self.store.connection.execute('SELECT * FROM project_bindings WHERE project_id=? AND active=1',(project_id,)).fetchone()
        binding=ProjectBinding(row['ui_project_id'],row['project_id'],row['workspace_root'],row['enrolled_at'],True)
        actual=project_snapshot(self._authority(),binding,binding.enrolled_at)
        snapshots=tuple(s if isinstance(s,NoteSnapshot) else NoteSnapshot(**s) for s in snapshots)
        if snapshots!=actual:raise ValueError('Native notes must match their saved authority')
        current={s.note_id:s for s in snapshots};applied=0
        old=self.store.connection.execute('SELECT * FROM note_mirrors WHERE project_id=?',(project_id,)).fetchall()
        # Recover orphaned sources from a crash after ingest but before mirror linkage.
        orphans=self.store.connection.execute("SELECT id FROM sources WHERE project_id=? AND session_id='native-notes' AND id NOT IN (SELECT source_id FROM note_mirrors WHERE source_id IS NOT NULL)",(project_id,)).fetchall()
        for orphan in orphans:delete_memory_source(self.store,orphan[0])
        for mirror in old:
            snapshot=current.get(mirror['note_id'])
            if snapshot and mirror['deleted']==2 and snapshot.revision==mirror['revision']:continue
            if snapshot and snapshot.revision==mirror['revision'] and not mirror['deleted'] and mirror['source_id']:continue
            if mirror['source_id']:delete_memory_source(self.store,mirror['source_id'])
            with self.store.transaction() as c:
                c.execute('UPDATE note_mirrors SET source_id=NULL,deleted=1 WHERE note_id=?',(mirror['note_id'],))
        for snapshot in snapshots:
            if snapshot.origin!='native_note' or snapshot.project_id!=project_id or utc(snapshot.created_at)<binding.enrolled_at:raise ValueError('Invalid native note scope')
            mirror=self.store.connection.execute('SELECT * FROM note_mirrors WHERE note_id=?',(snapshot.note_id,)).fetchone()
            if mirror and mirror['project_id']!=project_id:raise ValueError('Native note identity belongs to another project')
            if mirror and mirror['deleted']==2 and mirror['revision']==snapshot.revision:continue
            if mirror and mirror['revision']==snapshot.revision and mirror['source_id'] and not mirror['deleted']:continue
            from .intentional_sources import save_intentional
            result=save_intentional(self.store,project_id,dict(request_id='note-sync-'+secrets.token_hex(16),
                kind='native_note',text=snapshot.text,title='Your note'),owner='native-note-mirror',at=snapshot.created_at)
            sid=result['source_id']
            with self.store.transaction() as c:
                c.execute('INSERT OR REPLACE INTO note_mirrors VALUES(?,?,?,?,0)',(snapshot.note_id,project_id,snapshot.revision,sid))
                claim_ids=[r[0] for r in c.execute("SELECT cl.id FROM claims cl JOIN support sp ON sp.entity_id=cl.id JOIN occurrences o ON o.id=sp.occurrence_id WHERE o.source_id=? AND cl.kind='task'",(sid,))]
                # Native done-state is the canonical current state of this note, not
                # an inference over historical corrections from a deleted revision.
                for cid in claim_ids:c.execute("DELETE FROM corrections WHERE subject_id=? AND action IN ('complete','reopen')",(cid,))
            if snapshot.done_at:
                for cid in claim_ids:apply_correction(self.store,Correction('complete',cid,None,snapshot.done_at))
            applied+=1
        return SyncResult(applied,0,0)

    def sync_pending(self,recover=False):
        from memory_notes import native_sync_lock
        with native_sync_lock(self.directory,blocking=False) as acquired:
            if not acquired:return False
            return self._sync_pending_locked(recover)

    def _sync_pending_locked(self,recover=False):
        with self.store.lock:return self._consume_pending(recover)

    def queue_reconciliation(self,project_id):
        """Called under the native writer lock and store lock on re-enrollment."""
        from memory_notes import project_snapshot,snapshot_hash
        path=self.directory/'native-notes.pending.json'
        projects=set(read_private_json(path)['projects']) if path.exists() else set()
        projects.add(project_id);items=self._authority();hashes={}
        for binding in self.service.bindings():
            if binding['active'] and binding['project_id'] in projects:
                hashes[binding['project_id']]=snapshot_hash(project_snapshot(items,binding,binding['enrolled_at']))
        marker={'version':1,'mutation_id':secrets.token_hex(16),'pid':os.getpid(),'projects':sorted(hashes),'phase':'committed','hashes':hashes}
        write_private_json(path,marker);self.sync_fences()

    def _consume_pending(self,recover=False):
        from memory_notes import project_snapshot,snapshot_hash
        marker=self.sync_fences()
        if marker is None or paused(self.store):return False
        # A live parent may still be writing JSON. Only recover a preparing marker
        # explicitly or after its original parent has been replaced.
        if marker['phase']=='preparing' and not recover and marker['pid']==os.getppid():return False
        items=self._authority();state_path=self.directory/'native-note-state.json'
        state=read_private_json(state_path) if state_path.exists() else {}
        for binding in self.service.bindings():
            pid=binding['project_id']
            if pid not in marker['projects'] or not binding['active']:continue
            snapshots=project_snapshot(items,binding,binding['enrolled_at'])
            if marker['phase']=='committed' and marker['hashes'].get(pid)!=snapshot_hash(snapshots):return False
            result=self.reconcile(pid,snapshots,marker['mutation_id'])
            if result.pending or paused(self.store):return False
            state[pid]=snapshot_hash(snapshots)
        # Check journal identity again; a newer native save keeps its own fence.
        path=self.directory/'native-notes.pending.json';latest=read_private_json(path)
        if latest['mutation_id']!=marker['mutation_id']:return False
        with self.store.transaction() as c:
            c.execute('DELETE FROM note_fences WHERE mutation_id=?',(marker['mutation_id'],));bump_revision(c)
        write_private_json(state_path,state);path.unlink()
        return True
