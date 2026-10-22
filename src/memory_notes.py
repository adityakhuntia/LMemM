"""Explicit project-note snapshots and a durable cross-store read fence.

The normal JSON remains authoritative. A private pending marker is durable before
JSON mutation; the service checks it before reads and again before returning data.
No socket acknowledgement or model work blocks the native event loop.
"""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import secrets
from datetime import datetime,timezone
import notes
from semantic_memory.api_contracts import NoteSnapshot
from semantic_memory.policy import utc
from semantic_memory.live_bridge import read_private_json,write_private_json


def _field(binding,key):return binding[key] if isinstance(binding,dict) else getattr(binding,key)


def project_snapshot(items,binding,enrolled_at):
    ui=_field(binding,'ui_project_id');pid=_field(binding,'project_id');result=[]
    for item in items.values():
        for note in item.get('notes',[]):
            if note.get('memory_project_id')!=ui:continue
            created=note.get('memory_created_at')
            if not created:continue  # Legacy/ambiguous notes are never historical imports.
            created=utc(created)
            if created<utc(enrolled_at):continue
            note_id=note.get('memory_id') or 'native-'+hashlib.sha256((item['id']+'|'+note['at']+'|'+note['text']).encode()).hexdigest()
            done=item.get('notes_done',{}).get(notes.note_id(note))
            if done:
                dt=datetime.fromisoformat(done)
                done=dt.astimezone(timezone.utc).isoformat()
            data={'note_id':note_id,'project_id':pid,'text':note['text'],'created_at':created,'done_at':done,'deleted':False,'origin':'native_note'}
            revision=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
            result.append(NoteSnapshot(revision=revision,**data))
    return tuple(sorted(result,key=lambda n:n.note_id))


def snapshot_hash(snapshots):
    return hashlib.sha256(json.dumps([dataclasses.asdict(s) for s in snapshots],sort_keys=True).encode()).hexdigest()


def native_bindings(directory):
    path=Path(directory)/'native-bindings.json'
    if not path.exists():return []
    return read_private_json(path)['bindings']


def prepare_native_sync(items,directory):
    directory=Path(directory);bindings=native_bindings(directory)
    if not bindings:return None
    state_path=directory/'native-note-state.json'
    old=read_private_json(state_path) if state_path.exists() else {}
    pending_path=directory/'native-notes.pending.json'
    pending_projects=set(read_private_json(pending_path).get('projects',[])) if pending_path.exists() else set()
    hashes={}
    for binding in bindings:
        if not binding['active']:continue
        digest=snapshot_hash(project_snapshot(items,binding,binding['enrolled_at']))
        if old.get(binding['project_id'])!=digest or binding['project_id'] in pending_projects:hashes[binding['project_id']]=digest
    if not hashes:return None
    marker={'version':1,'mutation_id':secrets.token_hex(16),'pid':os.getpid(),'projects':sorted(hashes),'phase':'preparing','hashes':hashes}
    write_private_json(directory/'native-notes.pending.json',marker)
    return marker


def commit_native_sync(directory,marker):
    if marker is None:return
    path=Path(directory)/'native-notes.pending.json'
    current=read_private_json(path)
    if current['mutation_id']!=marker['mutation_id']:raise ValueError('Concurrent note mutation')
    write_private_json(path,{**marker,'phase':'committed'})


def add_project_note(items,binding,text,at=None):
    if not _field(binding,'active'):raise ValueError('Enable Memory for this project first')
    if not isinstance(text,str) or not text.strip() or len(text.encode())>4096:raise ValueError('Write a project note up to 4 KiB')
    at=utc(at or datetime.now(timezone.utc).isoformat())
    if at<_field(binding,'enrolled_at'):raise ValueError('Note predates project enrollment')
    ui=_field(binding,'ui_project_id');iid='memory-notes-'+ui
    local_at=datetime.fromisoformat(at).astimezone().replace(tzinfo=None).isoformat(timespec='seconds')
    item=items.setdefault(iid,{'id':iid,'app':'LMemM','kind':'project_notes','doing':'Project notes','title':'Project notes',
        'project_id':ui,'project':'Project notes','seconds':0,'visits':1,'first_seen':local_at,'last_seen':local_at,'notes':[],
        'activity':{},'refs':[],'state':{}})
    note={'at':local_at,'text':text,'memory_id':'native-'+secrets.token_hex(16),'memory_project_id':ui,'memory_created_at':at}
    item['notes'].append(note);item['last_seen']=local_at
    return note


def check_project_action(action,ui_project_ids,directory):
    bindings=native_bindings(directory)
    if action=='delete' and any(b['ui_project_id'] in ui_project_ids and b.get('retained_count',1)>0 for b in bindings):
        raise ValueError('Delete retained memory in this project’s Memory Settings before deleting the project.')
    active={b['ui_project_id'] for b in bindings if b['active']}
    if active.intersection(ui_project_ids):
        if action=='merge':raise ValueError('Projects linked to Memory cannot be merged. Disconnect Memory first.')
        if action=='delete':raise ValueError('Disconnect Memory for this project before deleting it; agent access will be revoked.')


from contextlib import contextmanager
import fcntl

@contextmanager
def native_sync_lock(directory, blocking=True):
    directory=Path(directory)
    if not directory.exists():
        yield True
        return
    fd=os.open(directory/'native-notes.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    acquired=False
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|(0 if blocking else fcntl.LOCK_NB))
            acquired=True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
