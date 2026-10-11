"""Service capabilities cannot broaden an agent's project or source authority."""
import tempfile
import unittest
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
        self.owner('pause')
        self.service.tick()
        self.assertFalse(self.service.bridge.active)
        self.assertEqual(self.owner('status')['state'],'Paused')
        self.owner('resume');self.service.tick()
        self.assertTrue(self.service.bridge.active)

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
