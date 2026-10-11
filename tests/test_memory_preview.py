import tempfile,unittest
from pathlib import Path
from semantic_memory.service import MemoryService
from semantic_memory.live_bridge import read_private_json
class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)/'repo';root.mkdir()
        self.service=MemoryService(Path(self.tmp.name)/'memory',focus_provider=lambda:None);self.addCleanup(self.service.close)
        self.binding=self.service.enroll('ui',str(root));self.pid=self.binding['project_id']
    def test_proposed_preview_does_not_issue_grant_and_exact_packet_matches(self):
        before=self.service.store.connection.execute('SELECT count(*) FROM memory_grants').fetchone()[0]
        preview=self.service.serve_request(self.service.owner_capability,'preview_agent_context',{'project_id':self.pid,'client_id':'Codex'})
        self.assertTrue(preview['proposed']);self.assertEqual(before,self.service.store.connection.execute('SELECT count(*) FROM memory_grants').fetchone()[0])
        agent=self.service.connect_agent('Codex',[self.pid],['com.microsoft.VSCode'],True)
        args={'project_id':self.pid,'start':preview['packet']['start'],'end':preview['packet']['end']}
        packet=self.service.serve_request(agent['capability'],'get_project_context',args)
        self.assertEqual(preview['packet'],packet)
        self.assertEqual(read_private_json(Path(agent['config_path']))['capability'],agent['capability'])
    def test_reenable_does_not_resurrect_agent(self):
        agent=self.service.connect_agent('Codex',[self.pid],['com.microsoft.VSCode'],True)
        self.service.revoke_project(self.pid)
        self.assertTrue(self.service.enroll('ui',self.binding['workspace_root'])['active'])
        with self.assertRaises(ValueError):self.service.serve_request(agent['capability'],'get_project_context',{'project_id':self.pid})
