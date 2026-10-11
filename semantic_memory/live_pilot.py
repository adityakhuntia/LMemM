"""Explicit experimental live intake, bounded background inference, local recall."""
import dataclasses
import json
import os
import sqlite3
import threading
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .live_bridge import Bridge,read_private_json,write_private_json
from .live_focus import focused_context
from .contracts import AccessPolicy,SourceScope
from .store import SemanticStore
from .episodes import EpisodeBuilder
from .inference import InferenceWorker
from .retention import enforce_budget,delete_session
from .policy import identifier
from .retrieval import project_context

APP='com.microsoft.VSCode'

def timestamp(now):return datetime.fromtimestamp(now,timezone.utc).isoformat()

class Pilot:
 def __init__(self,directory,roots,extractor_factory=None,clock=time.time,focus_provider=focused_context,limit=250*1024*1024):
  if Path(directory).is_symlink():raise ValueError("Symlink pilot directory forbidden")
  self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
  if self.directory.stat().st_mode & 0o777 != 0o700:raise ValueError('Pilot directory must be private (0700)')
  self.clock=clock;self.focus_provider=focus_provider;self.limit=limit
  self.closed=False;self.paused=False;self.reason=None;self.factory=extractor_factory;self.worker=None;self.thread=None
  self.store=SemanticStore(self.directory/'memory.sqlite')
  # One-third database cap reserves rollback journal, VACUUM copy and bridge overhead.
  page=self.store.connection.execute('PRAGMA page_size').fetchone()[0]
  reserve=max(256*1024,min(1024*1024,limit//8));cap=(limit-reserve)//(3*page)
  count=self.store.connection.execute('PRAGMA page_count').fetchone()[0]
  if cap<count:
   self.store.close();raise ValueError('Budget too small for current database')
  self.store.connection.execute('PRAGMA max_page_count='+str(cap))
  self.store.connection.execute('PRAGMA temp_store=MEMORY')
  revision=self.store.connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
  self.revision=int(revision[0]) if revision else 0
  self.bridge=Bridge(self.directory/'bridge',roots,clock);self.bridge.revision=self.revision;self.bridge.open_session()
  self.episodes=EpisodeBuilder(self.store);self.last_retention=0;self.last_focus=self.focus_provider();self.reset_worker=False;self.retry_note_requested=False
  self.episodes.boundary('restart',timestamp(clock()))
  if self.factory:self.worker=InferenceWorker(self.store,self.factory())
  self.status()
 @property
 def policy(self):return AccessPolicy(self.revision,frozenset({APP}),frozenset())
 def schedule(self,ids):
  if self.worker:
   for eid in ids:self.worker.enqueue(eid)
 def recover_unscheduled(self,retry_notes=False):
  if self.paused or self.closed:return
  # Automatic recovery is restricted to transient native-focus cancellation.
  roots=tuple(str(r) for r in self.bridge.roots)
  placeholders=','.join('?' for _ in roots)
  with self.store.lock:
   rows=self.store.connection.execute("""SELECT e.id FROM episodes e
    WHERE coalesce((SELECT CAST(value AS INTEGER) FROM meta WHERE key='focus_retries:'||e.id),0)<2
    AND (e.status='unprocessed' AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.episode_id=e.id)
      OR EXISTS(SELECT 1 FROM jobs j WHERE j.episode_id=e.id AND j.status='cancelled'
        AND (j.error='native_focus_boundary' OR ?)))
    AND EXISTS(SELECT 1 FROM episode_evidence ee WHERE ee.episode_id=e.id)
    AND NOT EXISTS(SELECT 1 FROM episode_evidence ee
      JOIN occurrences o ON o.id=ee.occurrence_id JOIN sources s ON s.id=o.source_id
      LEFT JOIN projects p ON p.id=s.project_id
      WHERE ee.episode_id=e.id AND (s.app_id!=? OR p.locator IS NULL OR p.locator NOT IN ("""+placeholders+""")))
    ORDER BY EXISTS(SELECT 1 FROM episode_evidence ee JOIN occurrences o ON o.id=ee.occurrence_id
      JOIN sources s ON s.id=o.source_id WHERE ee.episode_id=e.id AND s.origin_type='user_note') DESC,
      e.ended DESC LIMIT 8""",(retry_notes,APP,*roots)).fetchall()
   if self.worker:
    for row in rows:self.worker.enqueue(row[0],retry_focus=True,retry_note=retry_notes)
 def ingest(self,envelope):
  if self.paused or self.closed:return None
  with self.store.lock:
   result=self.store.ingest(envelope,self.policy)
   self.schedule(self.episodes.accept(result.source_id))
   return result
 def _run(self):
  try:self.worker.run_one()
  except Exception as error:
   self.reason='Inference unavailable: '+type(error).__name__
   with self.store.transaction() as c:
    c.execute("UPDATE jobs SET status='unprocessed',error='runtime unavailable' WHERE status='running'")
    c.execute("UPDATE episodes SET status='unprocessed' WHERE status='running'")
 def tick(self):
  if self.closed:return
  try:
   focus=self.focus_provider()
   if focus!=self.last_focus:
    self.invalidate('native_focus_boundary')
    self.bridge.last.clear();self.last_focus=focus
   if not self.paused:
    for path in sorted((self.bridge.directory/'events').glob('*.json'))[:8]:
     try:m=read_private_json(path)
     except (OSError,ValueError):continue
     if path.stem!=m.get('client'):continue
     after=self.focus_provider()
     if focus!=after or m.get('kind')=='connect' and (not after or 'LMemM '+m.get('client','') not in after.title):continue
     envelope=self.bridge.accept(m,focus)
     verified=self.focus_provider()
     if m.get('kind')=='connect' and (focus!=verified or not verified or 'LMemM '+m['client'] not in verified.title):
      self.bridge.clients.pop(m['client'],None)
      (self.bridge.directory/'acks'/(m['client']+'.json')).unlink(missing_ok=True)
      continue
     if envelope and focus==verified:
      self.ingest(envelope)
      write_private_json(self.bridge.directory/'acks'/(m['client']+'.json'),dict(session=self.bridge.session,window=focus.window,seq=m['seq'],accepted=True,note_id=m.get('note_id'),revision=self.revision))
     elif envelope:self.bridge.last.pop(m.get('client'),None)
    if self.bridge.expire():self.invalidate('client_disconnected')
    with self.store.lock:self.schedule(self.episodes.flush(timestamp(self.clock())))
    if self.clock()-self.last_retention>=30:
     with self.store.lock:enforce_budget(self.store,timestamp(self.clock()),semantic_limit=self.limit)
     self.last_retention=self.clock()
    if self.reset_worker and (not self.thread or not self.thread.is_alive()):
     if self.factory:self.worker=InferenceWorker(self.store,self.factory())
     self.reset_worker=False
    if focus is not None and self.worker and (not self.thread or not self.thread.is_alive()):
     self.recover_unscheduled(retry_notes=self.retry_note_requested)
     self.retry_note_requested=False
     self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
  except (sqlite3.DatabaseError,RuntimeError) as error:
   self.pause('Storage unavailable: '+type(error).__name__)
  self.status()
 def retry_notes(self):
  if not self.paused and not self.closed:self.retry_note_requested=True
 def flush(self):
  with self.store.lock:self.schedule(self.episodes.boundary('explicit_flush',timestamp(self.clock())))
 def invalidate(self,reason):
  # Persistent barrier precedes cancellation callbacks and any bridge IO.
  with self.store.transaction() as c:
   self.revision+=1
   c.execute("INSERT OR REPLACE INTO meta VALUES('revision',?)",(str(self.revision),))
   c.execute("UPDATE jobs SET status='cancelled',error=? WHERE status IN ('queued','running')",(reason,))
  self.bridge.revision=self.revision;self.bridge.last.clear()
  self.bridge.publish_grant()
  self.episodes.boundary(reason,timestamp(self.clock()))
  self.reset_worker=True
  if self.worker:self.worker.extractor.cancel()
 def pause(self,reason='Paused by user'):
  self.retry_note_requested=False
  self.paused=True;self.reason=reason
  self.invalidate(reason)
  self.bridge.active=False;self.bridge.publish_grant()
  for p in (self.bridge.directory/'events').glob('*.json'):p.unlink(missing_ok=True)
  self.status()
 def resume(self):
  if self.thread and self.thread.is_alive():raise RuntimeError('Wait for cancelled inference to finish before resume')
  if self.factory:self.worker=InferenceWorker(self.store,self.factory())
  self.reset_worker=False
  self.bridge.active=True;self.bridge.publish_grant();self.paused=False;self.reason=None;self.status()
 def status(self):
  with self.store.lock:
   result=dict(pid=os.getpid(),session=self.bridge.session,revision=self.revision,paused=self.paused,reason=self.reason,
    model='experimental' if self.worker else 'evidence only',sources=self.store.count('sources'),
    projects=self.store.count('projects'),native_focus_verified=self.last_focus is not None,jobs=self.worker.status() if self.worker else {},closed=self.closed)
  write_private_json(self.directory/'status.json',result);return result
 def close(self):
  if self.closed:return
  self.flush();self.pause('Stopped');
  if self.thread:self.thread.join(timeout=35)
  if self.thread and self.thread.is_alive():raise RuntimeError('Inference shutdown deadline exceeded')
  self.closed=True;self.status();self.store.close()

def inspect_project(database,root,days=2):
 if not 0<days<=30:raise ValueError('Days must be within retained 30-day window')
 store=SemanticStore(database,readonly=True)
 try:
  now=datetime.now(timezone.utc);pid=identifier('project',str(Path(root).resolve(strict=True)))
  packet=project_context(store,pid,(now-timedelta(days=days)).isoformat(),now.isoformat(),SourceScope(frozenset({APP})))
  result=dataclasses.asdict(packet)
  # Raw snapshots show observed content, not proof of completed work.
  result['observed_sources']=list(result.pop('citations').values())
  for source in result['observed_sources']:
   row=store.connection.execute('SELECT locator FROM artifacts WHERE id=?',(source['artifact_id'],)).fetchone()
   source['locator']=row[0] if row else None
  result['tentative']=result.pop('unknowns')
  result['observed_claims']=result.pop('recent_changes')
  # Bound the complete structured result, preserving exact retained quote prefixes.
  while len(json.dumps(result,ensure_ascii=False).encode())>16384:
   sources=result['observed_sources']
   long=[s for s in sources if len(s['text'].encode())>512]
   if long:
    source=max(long,key=lambda s:len(s['text'].encode()))
    source['text']=source['text'].encode()[:512].decode('utf8',errors='ignore');source['truncated']=True
   else:
    lists=[result[k] for k in ('observed_claims','decisions','open_tasks','artifacts','conflicts','tentative','observed_sources') if result[k]]
    if not lists:break
    max(lists,key=len).pop();result['coverage']['omitted_entries']+=1
   result['coverage']['truncated']=True
  return result
 finally:store.close()
