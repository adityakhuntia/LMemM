"""Service capabilities cannot broaden an agent's project or source authority."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from semantic_memory.service import MemoryService
from memory_helpers import AT,APP,memory_source
from semantic_memory.chunks import index_source


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)/'memory';self.root=Path(self.tmp.name)/'repo';self.root.mkdir()
        self.service=MemoryService(self.directory,focus_provider=lambda:None,clock=lambda:1790812800);self.addCleanup(self.service.close)

    def owner(self,method,**params):return self.service.serve_request(self.service.owner_capability,method,params)

    def enroll(self):return self.owner('enroll',ui_project_id='a',root=str(self.root))

    def test_enrollment_and_read_requests_share_backend_and_exact_citation(self):
        binding=self.enroll();pid=binding['project_id']
        self.service.store.ingest(memory_source('a',str(self.root.resolve()),'TODO: Verify rollback.',origin_type='user_note'),self.service.policy)
        index_source(self.service.store,'a')
        packet=self.owner('get_project_context',project_id=pid,start='2026-10-01T00:00:00+00:00',end='2026-10-11T00:00:00+00:00')
        self.assertEqual(packet['open_tasks'][0]['statement'],'TODO: Verify rollback.')
        result=self.owner('search_project_memory',project_id=pid,query='rollback',start='2026-10-01T00:00:00+00:00',end='2026-10-11T00:00:00+00:00')
        cid=result['primary'][0]['citation_id']
        detail=self.owner('resolve_citation',project_id=pid,citation_id=cid)
        self.assertEqual(detail['text'],'TODO: Verify rollback.')

    def test_agent_capability_cannot_write_or_read_other_projects(self):
        b=self.enroll()
        connection=self.owner('connect_agent',client_id='test-agent',project_ids=[b['project_id']],app_ids=[APP],disclosure_approved=True)
        cap=connection['capability']
        with self.assertRaisesRegex(ValueError,'unavailable'):self.service.serve_request(cap,'enroll',{})
        with self.assertRaisesRegex(ValueError,'unavailable'):self.service.serve_request(cap,'get_project_context',{'project_id':'missing'})
        self.owner('revoke_agent',grant_id=connection['grant_id'])
        with self.assertRaisesRegex(ValueError,'unavailable'):self.service.serve_request(cap,'get_project_context',{'project_id':b['project_id']})
        with self.assertRaises(ValueError):self.owner('connect_agent',client_id='x',project_ids=[b['project_id']],app_ids=[APP],disclosure_approved=False)

    def test_pause_updates_intake_and_keyword_only_status(self):
        self.enroll();self.service.tick()
        original=self.service.bridge
        session=original.session;token=original.token;initial_revision=original.revision
        self.owner('pause')
        self.service.tick()
        self.assertFalse(self.service.bridge.active)
        self.assertIs(self.service.bridge,original)
        self.assertGreater(original.revision,initial_revision)
        self.assertEqual(self.owner('status')['state'],'Paused')
        self.owner('resume');self.service.tick()
        self.assertTrue(self.service.bridge.active)
        self.assertEqual((self.service.bridge.session,self.service.bridge.token),(session,token))

    def test_exclusive_writer_lock_and_private_files(self):
        with self.assertRaises((ValueError,BlockingIOError)):MemoryService(self.directory,focus_provider=lambda:None)
        self.assertEqual(self.directory.stat().st_mode&0o777,0o700)
        self.assertEqual((self.directory/'capabilities.json').stat().st_mode&0o777,0o600)

    def test_method_arguments_are_strict_and_errors_do_not_echo_evidence(self):
        b=self.enroll()
        with self.assertRaises(ValueError):self.owner('get_project_context',project_id=b['project_id'],sql='select *')
        with self.assertRaisesRegex(ValueError,'unavailable'):self.service.serve_request('wrong','status',{})

    def test_restart_restores_enabled_state_but_keeps_manual_pause(self):
        self.enroll();self.service.close()
        self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        self.assertEqual(self.owner('status')['state'],'Ready')
        self.owner('pause');self.service.close()
        self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        self.assertEqual(self.owner('status')['state'],'Paused')

    def test_resume_is_blocked_until_system_unlock(self):
        self.service.system_flags={'locked'}
        self.owner('pause',reason='System locked')
        with self.assertRaises(ValueError):self.owner('resume')

    def test_capture_rechecks_pause_and_binding_at_commit(self):
        self.enroll();self.service.tick()
        from types import SimpleNamespace
        from semantic_memory.live_bridge import write_private_json
        focus=SimpleNamespace(window='w',title='editor')
        self.service.focus_provider=lambda:focus
        bridge=self.service.bridge
        for action in ('pause','revoke'):
            self.owner('resume');self.enroll();self.service.tick();bridge=self.service.bridge
            write_private_json(bridge.directory/'events'/'test.json',{'client':'test','kind':'excerpt','seq':1})
            def accept(*_):
                if action=='pause':self.owner('pause')
                else:self.owner('revoke_project',project_id=self.enroll()['project_id'])
                return memory_source(action,str(self.root.resolve()),'Must not retain this')
            with patch.object(bridge,'accept',side_effect=accept):self.service.tick()
            self.assertEqual(self.service.store.count('sources'),0)
            self.assertEqual(self.service.store.connection.execute('SELECT count(*) FROM memory_chunks').fetchone()[0],0)
            self.assertEqual(self.service.store.connection.execute('SELECT count(*) FROM index_jobs').fetchone()[0],0)
            self.assertFalse((bridge.directory/'acks'/'test.json').exists())

    def test_repeated_agent_revoke_does_not_exhaust_connections(self):
        b=self.enroll()
        for _ in range(10):
            connection=self.owner('connect_agent',client_id='Codex',project_ids=[b['project_id']],app_ids=[APP],disclosure_approved=True)
            self.assertEqual(self.owner('agent_connections')[0]['grant_id'],connection['grant_id'])
            self.owner('revoke_agent',grant_id=connection['grant_id'])
            self.assertFalse(Path(connection['config_path']).exists())

    def test_project_limit_is_checked_before_mutation_and_restart_is_usable(self):
        for i in range(64):
            root=self.root/str(i);root.mkdir();self.owner('enroll',ui_project_id='p'+str(i),root=str(root))
        extra=self.root/'extra';extra.mkdir()
        with self.assertRaises(ValueError):self.owner('enroll',ui_project_id='extra',root=str(extra))
        self.assertEqual(len(self.owner('bindings')),64)
        self.service.close();self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close);self.assertEqual(self.owner('status')['state'],'Ready')

    def test_search_defaults_to_two_days_and_reports_effective_bounds(self):
        from datetime import datetime,timedelta,timezone
        b=self.enroll();now=datetime.now(timezone.utc)
        for sid,days in [('recent',0),('older',7)]:
            self.service.store.ingest(memory_source(sid,str(self.root.resolve()),'rollback '+sid,at=(now-timedelta(days=days)).isoformat()),self.service.policy)
            index_source(self.service.store,sid)
        result=self.owner('search_project_memory',project_id=b['project_id'],query='rollback')
        self.assertEqual([h['text'] for h in result['primary']],['rollback recent'])
        self.assertLessEqual(abs((datetime.fromisoformat(result['end'])-datetime.fromisoformat(result['start'])).total_seconds()-172800),1)
        all_time=self.owner('search_project_memory',project_id=b['project_id'],query='rollback',start='1970-01-01T00:00:00Z')
        self.assertEqual(len(all_time['primary']),2)

    def test_legacy_excess_enrollment_is_repaired_on_startup(self):
        from semantic_memory.project_scope import bind_project
        for i in range(65):
            root=self.root/str(i);root.mkdir();bind_project(self.service.store,'p'+str(i),str(root),'2026-09-30T00:00:00Z')
        self.service.close();self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        self.assertEqual(sum(b['active'] for b in self.owner('bindings')),64)
        self.assertEqual(self.owner('status')['state'],'Ready')

    def test_active_agent_limit_and_persisted_inventory(self):
        b=self.enroll();connections=[]
        for i in range(8):connections.append(self.owner('connect_agent',client_id='agent'+str(i),project_ids=[b['project_id']],app_ids=[APP],disclosure_approved=True))
        with self.assertRaises(ValueError):self.owner('connect_agent',client_id='extra',project_ids=[b['project_id']],app_ids=[APP],disclosure_approved=True)
        self.service.close();self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        inventory=self.owner('agent_connections');self.assertEqual(len(inventory),8)
        self.assertNotIn('capability',repr(inventory))
        for connection in inventory:self.owner('revoke_agent',grant_id=connection['grant_id'])
        self.assertEqual(self.owner('agent_connections'),[])

    def test_restart_recovers_interrupted_model_generation_creation(self):
        import dataclasses
        from test_memory_embeddings import local_manifest
        from semantic_memory.embedding_runtime import load_backend
        weights=Path(self.tmp.name)/'weights';weights.mkdir();manifest=local_manifest(weights)
        self.service.close();self.service=MemoryService(self.directory,backend_factory=load_backend,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        with patch('semantic_memory.service.begin_generation',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):self.service.configure_model(dataclasses.asdict(manifest))
        self.service.close();self.service=MemoryService(self.directory,backend_factory=load_backend,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        generation=self.service.store.connection.execute("SELECT * FROM index_generations WHERE state IN ('active','building')").fetchone()
        self.assertIsNotNone(generation)
        import json
        self.assertEqual(json.loads(generation['manifest']),dataclasses.asdict(manifest))

    def test_failed_owned_runtime_start_disables_embedding_backend(self):
        import dataclasses
        from types import SimpleNamespace
        from semantic_memory.live_bridge import write_private_json
        from test_memory_embeddings import local_manifest
        manifest=local_manifest(Path(self.tmp.name)/'runtime-weights')
        self.service.close()
        write_private_json(self.directory/'model.json',dataclasses.asdict(manifest))
        backend=SimpleNamespace(cancel=lambda:None)
        with patch('semantic_memory.embedding_runtime.load_backend',return_value=backend), \
             patch('semantic_memory.model_setup.OwnedEmbeddingRuntime.ensure',side_effect=ValueError('Port occupied')):
            self.service=MemoryService(self.directory,focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        self.assertIsNone(self.service.backend)
        self.assertEqual(self.service.status()['model_state'],'missing')
        with patch.object(self.service.runtime,'ensure',side_effect=ValueError('Port occupied')):
            with self.assertRaises(ValueError):self.service.resume()
        self.assertIsNone(self.service.backend)

    def test_model_upgrade_recovers_on_both_sides_of_generation_commit(self):
        import dataclasses,json,numpy as np
        from types import SimpleNamespace
        from semantic_memory.api_contracts import ModelManifest
        from semantic_memory.vector_index import activate_generation,begin_generation
        from semantic_memory.index_worker import IndexWorker,schedule_source
        def factory(manifest):
            return SimpleNamespace(manifest=manifest,cancel=lambda:None,embed=lambda texts,query:np.tile([1.]+[0.]*(manifest.dimension-1),(len(texts),1)).astype(np.float32))
        for boundary in ('before','after'):
            with self.subTest(boundary=boundary):
                self.service.close();self.service=MemoryService(self.directory,backend_factory=factory,focus_provider=lambda:None)
                self.addCleanup(self.service.close);self.enroll()
                a=ModelManifest('synthetic','a'*64,3,512,1,'fake','/synthetic')
                self.service.configure_model(dataclasses.asdict(a))
                worker=IndexWorker(self.service.store,self.service.backend)
                while worker.run_one():pass
                gid=self.service.store.connection.execute("SELECT id FROM index_generations WHERE state='building'").fetchone()
                if gid:activate_generation(self.service.store,gid[0])
                b=dataclasses.replace(a,digest='b'*64,dimension=2)
                def interrupted(*args):
                    if boundary=='after':begin_generation(*args)
                    raise OSError('crash boundary')
                with patch('semantic_memory.service.begin_generation',side_effect=interrupted):
                    with self.assertRaises(OSError):self.service.configure_model(dataclasses.asdict(b))
                self.service.close();self.service=MemoryService(self.directory,backend_factory=factory,focus_provider=lambda:None)
                self.addCleanup(self.service.close)
                self.service.store.ingest(memory_source(boundary,str(self.root.resolve()),'SQLite local evidence'),self.service.policy)
                schedule_source(self.service.store,boundary)
                worker=IndexWorker(self.service.store,self.service.backend)
                while worker.run_one():pass
                row=self.service.store.connection.execute("SELECT * FROM index_generations WHERE state='building'").fetchone()
                self.assertEqual(json.loads(row['manifest'])['dimension'],2)
                activate_generation(self.service.store,row['id'])
                self.assertFalse(self.service.store.connection.execute("SELECT 1 FROM index_jobs WHERE state!='done'").fetchone())

    def handshake_fixture(self):
        from semantic_memory.live_focus import Focus
        from semantic_memory.live_bridge import write_private_json
        self.enroll();self.service.tick();bridge=self.service.bridge;client='a'*32
        challenge=Focus(10,20,(0,0,800,600),title='LMemM '+client)
        self.service.focus_provider=lambda:challenge
        event=bridge.directory/'events'/(client+'.json')
        write_private_json(event,dict(token=bridge.token,session=bridge.session,client=client,seq=1,at=self.service.clock(),kind='connect',revision=bridge.revision,focused=True,window=None))
        return bridge,client,challenge

    def test_replayed_connect_cannot_revoke_verified_window_after_challenge_closes(self):
        from dataclasses import replace
        bridge,client,challenge=self.handshake_fixture();self.service.tick()
        ack=bridge.directory/'acks'/(client+'.json');self.assertTrue(ack.exists())
        self.service.focus_provider=lambda:replace(challenge,title='capture-test.md')
        self.service.tick()
        self.assertTrue(ack.exists());self.assertIn(client,bridge.clients)

    def test_resumed_bridge_snapshot_is_retained_and_acknowledged(self):
        from semantic_memory.live_bridge import write_private_json,read_private_json
        bridge,client,focus=self.handshake_fixture();self.service.tick()
        document=self.root/'capture.md';document.write_text('THREE')
        self.owner('pause');self.service.tick()
        self.owner('resume');self.service.tick()
        write_private_json(bridge.directory/'events'/(client+'.json'),dict(
            token=bridge.token,session=bridge.session,client=client,seq=2,
            at=self.service.clock(),kind='snapshot',revision=bridge.revision,
            focused=True,window=focus.window,workspace=self.root.resolve().as_uri(),
            document=document.resolve().as_uri(),version=2,spans=[{'text':'THREE'}]))
        self.service.tick()
        self.assertEqual(self.service.store.count('sources'),1)
        self.assertTrue(read_private_json(bridge.directory/'acks'/(client+'.json'))['accepted'])

    def test_challenge_closing_after_ack_keeps_same_native_window_verified(self):
        from dataclasses import replace
        bridge,client,challenge=self.handshake_fixture()
        calls=iter([challenge,challenge,replace(challenge,title='capture-test.md')])
        self.service.focus_provider=lambda:next(calls)
        self.service.tick()
        self.assertTrue((bridge.directory/'acks'/(client+'.json')).exists())

    def test_switching_native_window_during_handshake_rejects_registration(self):
        from dataclasses import replace
        bridge,client,challenge=self.handshake_fixture()
        calls=iter([challenge,challenge,replace(challenge,window=21)])
        self.service.focus_provider=lambda:next(calls)
        self.service.tick()
        self.assertFalse((bridge.directory/'acks'/(client+'.json')).exists())
        self.assertNotIn(client,bridge.clients)
