"""UI project organization must preserve semantic roots and require explicit disconnect."""
import tempfile
import unittest
from pathlib import Path
import config,projects
from semantic_memory.service import MemoryService


class MemoryProjectActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths=config.use_paths(self.tmp.name);self.paths.__enter__();self.addCleanup(self.paths.__exit__,None,None,None)
        self.reg=projects.empty();self.items={}
        self.a=projects.create(self.reg,'Alpha');self.b=projects.create(self.reg,'Beta')
        self.root=Path(self.tmp.name)/'repo';self.root.mkdir()
        self.service=MemoryService(config.paths().semantic_dir,focus_provider=lambda:None);self.addCleanup(self.service.close)
        self.binding=self.service.enroll(self.a,str(self.root))

    def test_merge_and_delete_are_blocked_until_explicit_disconnect(self):
        with self.assertRaisesRegex(ValueError,'Memory'):projects.merge(self.reg,self.items,self.a,self.b)
        with self.assertRaisesRegex(ValueError,'Memory'):projects.delete(self.reg,self.items,self.a)
        self.service.revoke_project(self.binding['project_id'])
        projects.delete(self.reg,self.items,self.a)
        self.assertFalse(projects.exists(self.reg,self.a))

    def test_rename_move_and_archive_preserve_binding(self):
        projects.rename(self.reg,self.a,'Renamed',self.items)
        projects.move(self.reg,self.a,self.b)
        projects.archive(self.reg,self.a)
        self.assertEqual(self.service.bindings()[0]['project_id'],self.binding['project_id'])
        self.assertTrue(self.service.bindings()[0]['active'])
