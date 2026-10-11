"""Real SQLite upgrades preserve evidence and roll back interrupted DDL."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from semantic_memory.store import SCHEMA, SemanticStore
from semantic_memory.migrations import migrate
from memory_helpers import memory_source, APP
from semantic_memory.contracts import AccessPolicy


class MemoryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'memory.sqlite3'

    def v1(self):
        c = sqlite3.connect(self.path)
        c.executescript(SCHEMA); c.execute('PRAGMA user_version=1'); c.commit()
        return c

    def test_upgrade_preserves_v1_rows_and_readonly_access(self):
        c = self.v1()
        c.execute("INSERT INTO projects VALUES('p','/synthetic/repo')"); c.commit(); c.close()
        store = SemanticStore(self.path); self.addCleanup(store.close)
        self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(store.connection.execute('SELECT locator FROM projects WHERE id=?',('p',)).fetchone()[0], '/synthetic/repo')
        result = store.ingest(memory_source('s', '/synthetic/repo', 'Retained café.'), AccessPolicy(1,frozenset({APP}),frozenset()))
        before = store.evidence(result.occurrence_ids)
        ro = SemanticStore(self.path, readonly=True); self.addCleanup(ro.close)
        self.assertEqual(ro.evidence(result.occurrence_ids), before)
        with self.assertRaises(RuntimeError):
            with ro.transaction(): pass

    def test_interrupted_ddl_rolls_back_all_new_tables_and_version(self):
        c = self.v1()
        # Authorizer models disk/permission failure after earlier migration DDL.
        def auth(action, name, *args):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and name == 'memory_grants' else sqlite3.SQLITE_OK
        c.set_authorizer(auth)
        with self.assertRaises(sqlite3.DatabaseError): migrate(c)
        c.set_authorizer(None)
        self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 1)
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='project_bindings'").fetchone())
        migrate(c)
        self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 2)
        c.close()

    def test_future_and_partial_schemas_fail_closed(self):
        c=self.v1();c.execute('PRAGMA user_version=999');c.close()
        with self.assertRaises(ValueError): SemanticStore(self.path)
        self.path.unlink()
        c=sqlite3.connect(self.path);c.execute('CREATE TABLE meta(key TEXT)');c.execute('PRAGMA user_version=1');c.close()
        with self.assertRaises(ValueError): SemanticStore(self.path)
