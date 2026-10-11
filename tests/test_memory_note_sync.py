"""Native JSON remains authoritative across note edits, crashes and replay."""
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import config
import store as native_store
import notes
import memory_notes
from semantic_memory.service import MemoryService


class NoteSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths=config.use_paths(self.tmp.name);self.paths.__enter__();self.addCleanup(self.paths.__exit__,None,None,None)
        self.root=Path(self.tmp.name)/'repo';self.root.mkdir()
        self.service=MemoryService(config.paths().semantic_dir,focus_provider=lambda:None,clock=lambda:1790812800)
        self.addCleanup(self.service.close)
        self.binding=self.service.enroll('ui-a',str(self.root));self.items={}

    def packet(self):
        return self.service.serve_request(self.service.owner_capability,'get_project_context',{'project_id':self.binding['project_id'],'start':'2026-10-01T00:00:00+00:00','end':'2026-11-01T00:00:00+00:00'})

    def save_note(self,text='TODO: Test rollback.'):
        note=memory_notes.add_project_note(self.items,self.binding,text,'2026-10-10T10:00:00+00:00')
        native_store.save_memory(self.items);self.service.tick()
        return note

    def test_save_done_reopen_and_delete_reconcile_without_stale_tasks(self):
        note=self.save_note();self.assertEqual(len(self.packet()['open_tasks']),1)
        self.assertEqual(self.service.store.count('sources'),1)
        native_store.save_memory(self.items);self.service.tick()
        self.assertEqual(self.service.store.count('sources'),1)
        notes.set_done(self.items,[notes.note_id(note)],True,'2026-10-10T11:00:00+00:00')
        native_store.save_memory(self.items)
        self.assertEqual(self.packet()['open_tasks'],[])  # Fence is effective before tick.
        self.service.tick();self.assertEqual(self.packet()['open_tasks'],[])
        notes.set_done(self.items,[notes.note_id(note)],False)
        native_store.save_memory(self.items);self.service.tick()
        self.assertEqual(len(self.packet()['open_tasks']),1)
        self.items.clear();native_store.save_memory(self.items);self.service.tick()
        self.assertEqual(self.packet()['open_tasks'],[])
        self.assertEqual(self.service.store.count('sources'),0)

    def test_ambiguous_and_pre_enrollment_notes_are_excluded(self):
        self.save_note()
        item=next(iter(self.items.values()))
        item['notes'].extend([{'at':'2026-10-10T11:00:00','text':'TODO: Guess my project.'},
            {'at':'2026-09-20T11:00:00','text':'TODO: Old note.','memory_project_id':'ui-a','memory_created_at':'2026-09-20T11:00:00+00:00'}])
        snapshots=memory_notes.project_snapshot(self.items,self.binding,self.binding['enrolled_at'])
        self.assertEqual([s.text for s in snapshots],['TODO: Test rollback.'])

    def test_failed_json_write_keeps_claims_hidden_until_restart_reconciliation(self):
        note=self.save_note();notes.set_done(self.items,[notes.note_id(note)],True)
        with patch.object(native_store,'write_json',side_effect=OSError('simulated disk error')):
            with self.assertRaises(OSError):native_store.save_memory(self.items)
        self.assertEqual(self.packet()['open_tasks'],[])
        self.assertTrue((Path(config.paths().semantic_dir)/'native-notes.pending.json').exists())
        # Simulate crash/restart: current persisted JSON still contains the open note.
        self.service.close()
        self.service=MemoryService(config.paths().semantic_dir,focus_provider=lambda:None,clock=lambda:1790812800)
        self.addCleanup(self.service.close)
        self.service.recover_native_notes()
        self.assertEqual(len(self.packet()['open_tasks']),1)

    def test_changed_text_that_is_no_longer_todo_removes_task(self):
        note=self.save_note();note['text']='Rollback test results are attached.'
        native_store.save_memory(self.items);self.service.tick()
        self.assertEqual(self.packet()['open_tasks'],[])
        result=self.service.serve_request(self.service.owner_capability,'search_project_memory',{'project_id':self.binding['project_id'],'query':'Rollback'})
        self.assertEqual(result['primary'][0]['text'],'Rollback test results are attached.')

    def test_pending_save_is_not_consumed_while_native_writer_holds_lock(self):
        self.save_note()
        with memory_notes.native_sync_lock(config.paths().semantic_dir):
            self.assertFalse(self.service.native_notes.sync_pending())
