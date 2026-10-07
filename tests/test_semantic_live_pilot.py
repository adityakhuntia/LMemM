import json
import sqlite3
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from semantic_memory.live_pilot import Pilot, inspect_project
from semantic_memory.live_focus import Focus
from semantic_memory.live_bridge import write_private_json
from semantic_memory.store import SemanticStore

class PilotTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name).resolve()
  self.roots=[self.base/'one',self.base/'two']
  for r in self.roots:r.mkdir();(r/'a.py').write_text('hello')
  self.now=datetime.now(timezone.utc).timestamp(); self.focus=Focus(1,10,(0,0,800,600),title='LMemM '+'a'*32);self.seq=0
  self.p=Pilot(self.base/'pilot',self.roots,clock=lambda:self.now,focus_provider=lambda:self.focus)
 def tearDown(self):self.p.close();self.tmp.cleanup()
 def send(self,kind,root=0):
  self.seq+=1
  m=dict(revision=self.p.bridge.revision,token=self.p.bridge.token,session=self.p.bridge.session,client='a'*32,seq=self.seq,at=self.now,kind=kind,focused=True,window=10,workspace=self.roots[root].as_uri(),document=(self.roots[root]/'a.py').as_uri(),spans=[dict(text='hello',truncated=False)])
  write_private_json(self.p.bridge.directory/'events'/('a'*32+'.json'),m)
  self.p.tick()
 def test_two_projects_dedup_and_readonly_recall(self):
  self.send('connect');self.send('snapshot');self.send('snapshot');self.send('snapshot',1)
  self.assertEqual(self.p.store.count('sources'),2)
  self.p.flush()
  result=inspect_project(self.p.store.path,self.roots[0],days=2)
  self.assertEqual(result['coverage']['evidence_count'],1)
  self.assertEqual(result['observed_sources'][0]['text'],'hello')
  self.assertIn('tentative',result)
 def test_pause_resume_and_restart_identity(self):
  self.send('connect');self.send('snapshot');self.p.pause();self.send('snapshot',1)
  self.assertEqual(self.p.store.count('sources'),1)
  self.p.resume();self.send('snapshot',1);self.assertEqual(self.p.store.count('sources'),2)
  path=self.p.store.path;self.p.close()
  self.p=Pilot(self.base/'pilot',self.roots,clock=lambda:self.now,focus_provider=lambda:self.focus)
  self.assertEqual(self.p.store.count('projects'),2)
 def test_native_context_changed_drops_source(self):
  self.send('connect')
  calls=iter([self.focus,None]);self.p.focus_provider=lambda:next(calls,None)
  self.send('snapshot');self.assertEqual(self.p.store.count('sources'),0)
 def test_quota_caps_all_sql_writers(self):
  self.p.close();self.p=Pilot(self.base/'small',self.roots,clock=lambda:self.now,focus_provider=lambda:self.focus,limit=1024*1024)
  with self.assertRaises(sqlite3.DatabaseError):
   with self.p.store.transaction() as c:c.execute("INSERT INTO meta VALUES('huge',?)",('x'*1024*1024,))
  self.assertLess(self.p.store.path.stat().st_size,1024*1024)
 def test_readonly_does_not_create_database(self):
  missing=self.base/'missing.db'
  with self.assertRaises(sqlite3.OperationalError):SemanticStore(missing,readonly=True)
  self.assertFalse(missing.exists())

class WorkerLifecycleTests(unittest.TestCase):
 def test_pause_blocks_inflight_commit_and_resume_uses_new_extractor(self):
  import threading
  started=threading.Event();release=threading.Event();instances=[]
  class Extractor:
   def __init__(self):self.cancelled=False;instances.append(self)
   def cancel(self):self.cancelled=True;release.set()
   def extract(self,request):
    started.set();release.wait(2)
    e=request.evidence[0]
    return json.dumps({'candidates':[dict(type='observation',subject_id=e['artifact_id'],evidence_ids=[e['id']],statement=e['text'],extraction_status='observed')]})
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();(root/'a.py').write_text('hello')
   p=Pilot(root/'data',[root],extractor_factory=Extractor,focus_provider=lambda:Focus(1,10,(0,0,800,600)))
   p.last_focus=Focus(1,10,(0,0,800,600))
   from semantic_memory.contracts import SourceEnvelope,TextSpan
   p.ingest(SourceEnvelope('s',datetime.now(timezone.utc).isoformat(),p.bridge.session,'com.microsoft.VSCode',str(root/'a.py'),str(root),True,'trusted_artifact_snapshot',(TextSpan('0','hello'),),p.revision))
   p.flush();p.tick();self.assertTrue(started.wait(2));p.pause();p.thread.join(2)
   self.assertEqual(p.store.count('claims'),0);p.resume();self.assertEqual(len(instances),2);self.assertFalse(instances[-1].cancelled);p.close()

class DirectoryTests(unittest.TestCase):
 def test_symlink_data_directory_denied(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);root=base/'root';root.mkdir();target=base/'private';target.mkdir(mode=0o700);link=base/'link';link.symlink_to(target)
   with self.assertRaises(ValueError):Pilot(link,[root])

class ReviewLifecycleTests(unittest.TestCase):
 def run_denied(self,mode):
  import threading
  started=threading.Event();release=threading.Event();done=threading.Event();focus=Focus(1,10,(0,0,800,600))
  class Extractor:
   def extract(self,request):
    started.set();release.wait(2);e=request.evidence[0]
    return json.dumps({'candidates':[dict(type='observation',subject_id=e['artifact_id'],evidence_ids=[e['id']],statement=e['text'],extraction_status='observed')]})
   def cancel(self):
    release.set()
    if mode=='pause':done.wait(1)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();(root/'a.py').write_text('hello')
   p=Pilot(root/'data',[root],extractor_factory=Extractor,focus_provider=lambda:focus)
   p.last_focus=focus
   from semantic_memory.contracts import SourceEnvelope,TextSpan
   p.ingest(SourceEnvelope('s',datetime.now(timezone.utc).isoformat(),p.bridge.session,'com.microsoft.VSCode',str(root/'a.py'),str(root),True,'trusted_artifact_snapshot',(TextSpan('0','hello'),),p.revision))
   p.flush();p.tick();self.assertTrue(started.wait(2))
   if mode=='pause':
    waiter=threading.Thread(target=lambda:(p.thread.join(2),done.set()));waiter.start();p.pause();waiter.join(2)
   else:
    p.focus_provider=lambda:None;p.tick();release.set()
   p.thread.join(2)
   self.assertEqual(p.store.count('claims'),0)
   p.close()
 def test_focus_denial_blocks_worker_commit(self):self.run_denied('focus')
 def test_pause_barrier_precedes_external_cancel(self):self.run_denied('pause')

class RecentRecallTests(unittest.TestCase):
 def test_latest_quotes_and_coverage_omission(self):
  from semantic_memory.contracts import SourceEnvelope,TextSpan
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();(root/'a.py').write_text('hello');p=Pilot(root/'data',[root],focus_provider=lambda:None)
   try:
    for i in range(5):
     p.ingest(SourceEnvelope('s'+str(i),datetime.now(timezone.utc).isoformat(),p.bridge.session,'com.microsoft.VSCode',str(root/'a.py'),str(root),True,'trusted_artifact_snapshot',(TextSpan('0','version '+str(i)),),p.revision))
    result=inspect_project(p.store.path,root)
    self.assertEqual([s['text'] for s in result['observed_sources']],['version 4','version 3','version 2'])
    self.assertGreaterEqual(result['coverage']['omitted_entries'],2)
    self.assertEqual(result['observed_sources'][0]['locator'],str(root/'a.py'))
   finally:p.close()

class CliDirectoryTests(unittest.TestCase):
 def test_cli_rejects_symlink_before_resolution(self):
  import subprocess,sys
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);target=base/'private';target.mkdir(mode=0o700);write_private_json(target/'status.json',{})
   link=base/'link';link.symlink_to(target)
   result=subprocess.run([sys.executable,'scripts/live_project_memory.py','--data-dir',str(link),'status'],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0)

class RegistrationRaceTests(unittest.TestCase):
 setUp=PilotTests.setUp
 tearDown=PilotTests.tearDown
 send=PilotTests.send
 def test_connect_focus_changes_before_ack_commit(self):
  other=Focus(1,20,(0,0,800,600))
  sequence=iter([self.focus,self.focus,other])
  self.p.focus_provider=lambda:next(sequence,other)
  self.send('connect')
  self.assertFalse(self.p.bridge.clients)

class GrantRevisionTests(unittest.TestCase):
 setUp=PilotTests.setUp
 tearDown=PilotTests.tearDown
 def test_focus_boundary_publishes_current_grant_revision(self):
  self.p.focus_provider=lambda:None
  self.p.tick()
  grant=json.loads((self.p.bridge.directory/'grant.json').read_text())
  self.assertGreater(self.p.revision,0)
  self.assertEqual(grant['revision'],self.p.revision)

class BoundarySchedulingTests(unittest.TestCase):
 def test_orphaned_note_recovers_only_with_focus_and_approved_root(self):
  from semantic_memory.contracts import SourceEnvelope,TextSpan
  class Extractor:
   def cancel(self):pass
   def extract(self,request):return json.dumps({'candidates':[]})
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();focus=Focus(1,10,(0,0,800,600))
   p=Pilot(root/'data',[root],extractor_factory=Extractor,focus_provider=lambda:focus)
   try:
    p.ingest(SourceEnvelope('note',datetime.now(timezone.utc).isoformat(),p.bridge.session,'com.microsoft.VSCode',str(root/'a.py'),str(root),True,'user_note',(TextSpan('0','TODO: test restart'),),p.revision))
    p.focus_provider=lambda:None;p.tick()
    self.assertEqual(p.store.connection.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
    p.focus_provider=lambda:focus;p.tick()
    if p.thread:p.thread.join(2)
    self.assertEqual(p.store.connection.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
    self.assertEqual(p.worker.status(),{'processed':1})
   finally:p.close()
 def test_recovery_excludes_unapproved_roots_and_does_not_retry_cancelled(self):
  from semantic_memory.contracts import SourceEnvelope,TextSpan
  from semantic_memory.inference import InferenceWorker
  class Extractor:
   def cancel(self):pass
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp).resolve();one=base/'one';two=base/'two';one.mkdir();two.mkdir()
   p=Pilot(base/'data',[one,two],focus_provider=lambda:None)
   try:
    for i,root in enumerate((one,two)):
     p.ingest(SourceEnvelope(str(i),datetime.now(timezone.utc).isoformat(),p.bridge.session,'com.microsoft.VSCode',str(root/'a.py'),str(root),True,'user_note',(TextSpan('0','TODO: test'),),p.revision))
    p.flush();p.bridge.roots=(one,);p.worker=InferenceWorker(p.store,Extractor())
    p.recover_unscheduled()
    self.assertEqual(p.worker.status(),{'queued':1})
    with p.store.transaction() as c:c.execute("UPDATE jobs SET status='cancelled'")
    p.recover_unscheduled();self.assertEqual(p.worker.status(),{'cancelled':1})
   finally:p.close()
