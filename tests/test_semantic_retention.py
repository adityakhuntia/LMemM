import unittest
from semantic_helpers import SemanticFixture, source, policy
from pathlib import Path
from semantic_memory.contracts import SourceScope
from semantic_memory.retention import delete_sources, delete_session, revoke_scope, enforce_budget

class RetentionTests(SemanticFixture, unittest.TestCase):
    def test_shared_text_and_replayed_deleted_source(self):
        self.db.ingest(source(),policy()); self.db.ingest(source('shared'),policy())
        delete_sources(self.db,{'s1'})
        self.assertEqual(self.db.count('blobs'),1)
        self.assertEqual(self.db.count('occurrences'),1)
        with self.assertRaises(ValueError):self.db.ingest(source(),policy())
        delete_sources(self.db,{'shared'})
        self.assertEqual(self.db.count('blobs'),0)
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM evidence_search').fetchone()[0],0)

    def test_delete_last_support_removes_claim(self):
        self.seed_decision()
        delete_session(self.db,'session')
        self.assertEqual(self.db.count('claims'),0)
        self.assertEqual(self.db.count('edges'),0)

    def test_revoke_blocks_stale_inference_and_scope(self):
        self.db.ingest(source(),policy())
        new=policy(2)
        revoke_scope(self.db,SourceScope(frozenset({'com.microsoft.VSCode'})),new)
        self.assertEqual(self.db.count('sources'),0)
        with self.assertRaises(ValueError):self.db.ingest(source('late'),policy())

    def test_retention_pinned_budget_pauses(self):
        self.db.ingest(source(),policy())
        with self.db.transaction() as c:c.execute('UPDATE sources SET pinned=1')
        status=enforce_budget(self.db,'2026-12-07T10:00:00+00:00',semantic_limit=100)
        self.assertEqual(status.paused_reason,'semantic_budget')
        self.assertEqual(self.db.count('sources'),1)
        with self.assertRaises(RuntimeError):self.db.ingest(source('budget_blocked'),policy())
        with self.db.transaction() as c:c.execute('UPDATE sources SET pinned=0')
        status=enforce_budget(self.db,'2026-12-07T10:00:00+00:00')
        self.assertEqual(self.db.count('sources'),0)
