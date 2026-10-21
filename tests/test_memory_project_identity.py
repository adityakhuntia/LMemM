"""Project ownership survives optional folder attachment and schema upgrades."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from semantic_memory.store import SemanticStore, SCHEMA
from semantic_memory.migrations import V2_SQL, VERSION, migrate
from semantic_memory.project_scope import bind_project, resolve_binding
from semantic_memory.contracts import AccessPolicy
from memory_helpers import AT, APP, memory_source


class ProjectIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'memory.sqlite3'

    def store(self):
        store = SemanticStore(self.path)
        self.addCleanup(store.close)
        return store

    def test_folder_free_projects_are_distinct_and_reenrollment_is_stable(self):
        store = self.store()
        a = bind_project(store, 'alpha', None, AT)
        b = bind_project(store, 'beta', None, AT)
        self.assertNotEqual(a.project_id, b.project_id)
        self.assertIsNone(a.workspace_root)
        self.assertEqual(bind_project(store, 'alpha', None, AT), a)

    def test_attach_folder_preserves_project_identity_and_captured_ownership(self):
        store = self.store()
        a = bind_project(store, 'alpha', None, AT)
        root = str(Path(self.tmp.name) / 'repo')
        attached = bind_project(store, 'alpha', root, AT)
        self.assertEqual(attached.project_id, a.project_id)
        self.assertEqual(bind_project(store, 'alpha', None, AT), attached)
        result = store.ingest(memory_source('capture', root, 'Retained database note.'),
                              AccessPolicy(1, frozenset({APP}), frozenset()))
        self.assertEqual(result.project_id, a.project_id)
        with self.assertRaises(ValueError): bind_project(store, 'beta', root, AT)
        with self.assertRaises(ValueError): bind_project(store, 'alpha', root + '-other', AT)

    def v2(self):
        c = sqlite3.connect(self.path)
        c.executescript(SCHEMA)
        for sql in V2_SQL: c.execute(sql)
        c.execute("INSERT INTO meta VALUES('memory_revision','1')")
        c.execute("INSERT INTO projects VALUES('old-project','/synthetic/repo')")
        c.execute("INSERT INTO project_bindings VALUES('ui','old-project','/synthetic/repo',?,1)", (AT,))
        c.execute("INSERT INTO sources VALUES('source','digest',?,'session',?,NULL,NULL,'old-project','user_note',1,0)", (AT, APP))
        c.execute("INSERT INTO blobs VALUES('blob','TODO: Test recovery.','hash')")
        c.execute("INSERT INTO occurrences VALUES('citation','source','blob','note',0)")
        c.execute("INSERT INTO claims VALUES('task',NULL,'old-project','task','TODO: Test recovery.','supported','open',?,NULL)", (AT,))
        c.execute('PRAGMA user_version=2')
        c.commit()
        return c

    def test_upgrade_preserves_evidence_and_creates_private_recoverable_backup(self):
        self.v2().close()
        store = self.store()
        self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], VERSION)
        self.assertEqual(resolve_binding(store, 'ui').project_id, 'old-project')
        self.assertEqual(store.evidence(['citation'])[0]['text'], 'TODO: Test recovery.')
        self.assertEqual(store.connection.execute("SELECT task_state FROM claims WHERE id='task'").fetchone()[0], 'open')
        backup = self.path.with_name(self.path.name + '.pre-v' + str(VERSION))
        self.assertEqual(os.stat(backup).st_mode & 0o777, 0o600)
        with sqlite3.connect(backup) as c:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(c.execute('SELECT id FROM occurrences').fetchone()[0], 'citation')

    def test_interrupted_upgrade_leaves_v2_schema_and_rows_intact(self):
        c = self.v2()
        self.addCleanup(c.close)
        def auth(action, name, *args):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DROP_TABLE and name == 'project_bindings' else sqlite3.SQLITE_OK
        c.set_authorizer(auth)
        with self.assertRaises(sqlite3.DatabaseError): migrate(c)
        c.set_authorizer(None)
        self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(c.execute('SELECT project_id FROM project_bindings').fetchone()[0], 'old-project')
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='project_bindings_v3'").fetchone())
        migrate(c)
        self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], VERSION)

    def test_service_enrollment_without_folder_does_not_start_editor_bridge(self):
        from semantic_memory.service import MemoryService
        service = MemoryService(Path(self.tmp.name) / 'semantic', focus_provider=lambda: None)
        self.addCleanup(service.close)
        binding = service.serve_request(service.owner_capability, 'enroll', {'ui_project_id': 'research'})
        self.assertIsNone(binding['workspace_root'])
        service.tick()
        self.assertIsNone(service.bridge)
        self.assertEqual(service.bindings()[0]['project_id'], binding['project_id'])
