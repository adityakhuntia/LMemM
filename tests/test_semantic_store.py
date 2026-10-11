import dataclasses
import tempfile
import unittest
from pathlib import Path

from semantic_memory.contracts import AccessPolicy, SourceEnvelope, TextSpan
from semantic_memory.store import SemanticStore


from semantic_helpers import source, policy, SemanticFixture


class StoreTests(SemanticFixture, unittest.TestCase):
    def test_duplicate_source_is_idempotent(self):
        first = self.db.ingest(source(), policy())
        again = self.db.ingest(source(), policy())
        self.assertTrue(first.inserted)
        self.assertFalse(again.inserted)
        self.assertEqual(first.occurrence_ids, again.occurrence_ids)
        self.assertEqual(self.db.count('occurrences'), 1)

    def test_conflicting_source_replay_rejected(self):
        self.db.ingest(source(), policy())
        with self.assertRaises(ValueError):
            self.db.ingest(source(spans=(TextSpan('span1', 'Changed content.', False),)), policy())

    def test_denied_private_unknown_browser_rejected(self):
        for s in (source(app_id='excluded'), source(private_context=True),
                  source(policy_revision=0), source(app_id='com.apple.Safari',
                  artifact_locator='https://docs.example.org/a', workspace_locator=None,
                  browser_context_known=False), source(app_id='com.apple.Safari',
                  artifact_locator='https://evil.org/a', workspace_locator=None)):
            with self.subTest(s=s), self.assertRaises(ValueError):
                self.db.ingest(s, policy())
        self.assertEqual(self.db.count('blobs'), 0)

    def test_same_name_workspaces_do_not_merge(self):
        a = self.db.ingest(source(), policy())
        b = self.db.ingest(source('s2', artifact_locator='/elsewhere/one/main.py',
                                 workspace_locator='/elsewhere/one'), policy())
        self.assertNotEqual(a.project_id, b.project_id)
        unknown = self.db.ingest(source('s3', identity_authoritative=False), policy())
        self.assertIsNone(unknown.project_id)

    def test_query_document_ids_preserved(self):
        args = dict(app_id='com.apple.Safari', workspace_locator=None)
        a = self.db.ingest(source('a', artifact_locator='https://docs.example.org/doc?id=1&utm_source=x#top', **args), policy())
        b = self.db.ingest(source('b', artifact_locator='https://docs.example.org/doc?id=1', **args), policy())
        c = self.db.ingest(source('c', artifact_locator='https://docs.example.org/doc?id=2', **args), policy())
        self.assertEqual(a.artifact_id, b.artifact_id)
        self.assertNotEqual(a.artifact_id, c.artifact_id)

    def test_shared_text_has_separate_occurrences(self):
        self.db.ingest(source(), policy())
        self.db.ingest(source('second'), policy())
        self.assertEqual(self.db.count('blobs'), 1)
        self.assertEqual(self.db.count('occurrences'), 2)

    def test_unicode_span_byte_limit(self):
        self.db.ingest(source(spans=(TextSpan('span1', '🙂' * 2000, False),)), policy())
        row = self.db.connection.execute('SELECT text,truncated FROM occurrences JOIN blobs ON blob_id=blobs.id').fetchone()
        self.assertLessEqual(len(row['text'].encode()), 4096)
        self.assertTrue(row['truncated'])

    def test_unknown_schema_and_unsafe_file_identity_rejected(self):
        with self.assertRaises(ValueError):
            self.db.ingest(source(artifact_locator='/other/private.txt'), policy())
        self.assertEqual(self.db.path.stat().st_mode & 0o777, 0o600)
