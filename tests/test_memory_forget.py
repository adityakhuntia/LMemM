"""Explicit forgetting clears retained evidence without guessing from missing files."""
import tempfile
import unittest
from pathlib import Path
import config
import store as native_store
import memory_notes
from semantic_memory.service import MemoryService


class MemoryForgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths=config.use_paths(self.tmp.name);self.paths.__enter__();self.addCleanup(self.paths.__exit__,None,None,None)
        self.service=MemoryService(config.paths().semantic_dir,focus_provider=lambda:None,clock=lambda:1790812800)
        self.addCleanup(self.service.close)
        self.binding=self.service.enroll('alpha');self.pid=self.binding['project_id']

    def test_disconnect_does_not_allow_project_delete_until_retained_memory_is_purged(self):
        self.service.save_excerpt(self.pid,dict(request_id='one',kind='pasted_excerpt',title='Research',text='Retained project evidence.'))
        self.service.revoke_project(self.pid)
        with self.assertRaises(ValueError):memory_notes.check_project_action('delete',{'alpha'},self.service.directory)
        self.service.delete_project_memory(self.pid)
        self.assertEqual(self.service.store.count('sources'),0)
        self.assertEqual(self.service.bindings(),[])
        memory_notes.check_project_action('delete',{'alpha'},self.service.directory)

    def test_forgotten_note_does_not_reappear_on_unrelated_note_reconciliation(self):
        items={}
        memory_notes.add_project_note(items,self.binding,'TODO: Forgotten task.','2026-10-10T10:00:00Z')
        native_store.save_memory(items);self.service.tick()
        sid=self.service.store.connection.execute('SELECT id FROM sources').fetchone()[0]
        self.service.delete_saved_source(sid)
        memory_notes.add_project_note(items,self.binding,'Another saved note.','2026-10-10T11:00:00Z')
        native_store.save_memory(items);self.service.tick()
        text=[r[0] for r in self.service.store.connection.execute('SELECT text FROM blobs')]
        self.assertNotIn('TODO: Forgotten task.',text)
        self.assertIn('Another saved note.',text)
