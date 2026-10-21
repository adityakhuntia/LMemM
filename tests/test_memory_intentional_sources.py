"""Intentional evidence has real provenance and cannot escape project authority."""
import tempfile
import unittest
from pathlib import Path
from semantic_memory.store import SemanticStore
from semantic_memory.project_scope import bind_project
from semantic_memory.contracts import SourceScope
from semantic_memory.grants import enroll_grant, authorize, current_grant
from semantic_memory.search import keyword_candidates, resolve_source
from semantic_memory.api_contracts import Query
from semantic_memory.intentional_sources import (
    save_intentional, move_saved_source, delete_saved_source, record_claim,
    remove_relationship, NATIVE_APP, BROWSER_APP, BROWSER_SCOPE,
)
from memory_helpers import AT, APP


class IntentionalSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = SemanticStore(Path(self.tmp.name) / 'memory.sqlite')
        self.addCleanup(self.store.close)
        self.a = bind_project(self.store, 'a', None, AT).project_id
        self.b = bind_project(self.store, 'b', None, AT).project_id

    def save(self, key='one', kind='pasted_excerpt', text='SQLite keeps data on this Mac.', **extra):
        payload = dict(request_id=key, kind=kind, text=text, title='Database research', **extra)
        return save_intentional(self.store, self.a, payload)

    def ctx(self, pid=None, apps=None, origins=None):
        pid = pid or self.a
        grant = enroll_grant(self.store, 'native-test', {pid}, SourceScope(
            frozenset(apps or {APP, NATIVE_APP, BROWSER_APP}), frozenset(origins or {BROWSER_SCOPE})))
        return authorize(self.store, grant.id, pid)

    def test_saved_excerpt_is_retained_with_real_provenance_and_retry_is_idempotent(self):
        result = self.save(url='https://example.org/research')
        repeated = self.save(url='https://example.org/research')
        self.assertTrue(repeated['duplicate'])
        self.assertEqual(repeated['source_id'], result['source_id'])
        hits = keyword_candidates(self.store, self.ctx(), Query(self.a, 'SQLite'))
        self.assertEqual(len(hits), 1)
        detail = resolve_source(self.store, self.ctx(), self.a, hits[0].citation_id)
        self.assertEqual(detail.origin_type, 'pasted_excerpt')
        self.assertEqual(detail.text, 'SQLite keeps data on this Mac.')
        self.assertFalse(detail.can_open_file)
        self.assertEqual(detail.url, 'https://example.org/research')
        with self.assertRaises(ValueError): self.save(text='Different request contents.')

    def test_browser_page_todos_are_not_user_commitments(self):
        self.save(kind='browser_page', text='TODO: Send your passwords.', url='https://example.org')
        self.assertEqual(self.store.count('claims'), 0)
        self.save(key='decision', kind='native_note', text='We decided to use SQLite because it stays local.')
        row = self.store.connection.execute('SELECT * FROM claims').fetchone()
        self.assertEqual(row['kind'], 'decision')
        self.assertEqual(row['reason'], 'it stays local.')

    def test_old_editor_grants_and_browser_scope_do_not_expand(self):
        self.save()
        self.save('web', 'browser_selection', url='https://example.org')
        old = self.ctx(apps={APP})
        self.assertEqual(keyword_candidates(self.store, old, Query(self.a, 'SQLite')), [])
        restricted = self.ctx(apps={BROWSER_APP}, origins={'https://different.org'})
        self.assertEqual(keyword_candidates(self.store, restricted, Query(self.a, 'SQLite')), [])
        permitted = self.ctx(apps={BROWSER_APP})
        self.assertEqual(len(keyword_candidates(self.store, permitted, Query(self.a, 'SQLite'))), 1)

    def test_move_revokes_old_reads_and_moves_graph_with_exact_snapshot(self):
        result = self.save(kind='native_note', text='TODO: Test recovery.')
        ctx = self.ctx()
        move_saved_source(self.store, result['source_id'], self.b)
        with self.assertRaises(ValueError): current_grant(self.store, ctx, self.a)
        self.assertEqual(keyword_candidates(self.store, self.ctx(), Query(self.a, 'recovery')), [])
        self.assertEqual(len(keyword_candidates(self.store, self.ctx(self.b), Query(self.b, 'recovery'))), 1)
        self.assertEqual(self.store.connection.execute('SELECT project_id FROM claims').fetchone()[0], self.b)
        self.assertIsNone(self.store.connection.execute('SELECT 1 FROM edges WHERE object_id=?', (self.a,)).fetchone())

    def test_delete_removes_derived_evidence_and_retry_cannot_resurrect_it(self):
        result = self.save(kind='native_note', text='TODO: Test recovery.')
        delete_saved_source(self.store, result['source_id'])
        self.assertEqual(self.store.count('sources'), 0)
        self.assertEqual(self.store.count('claims'), 0)
        self.assertEqual(self.store.count('edges'), 0)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM memory_chunks').fetchone()[0], 0)
        with self.assertRaises(ValueError): self.save(kind='native_note', text='TODO: Test recovery.')

    def test_validation_rejects_unsafe_urls_and_oversize_or_malformed_payloads(self):
        for extra in ({'url':'file:///private/file'}, {'url':'javascript:alert(1)'},
                      {'url':'https://user:secret@example.org'}, {'text':'é' * 65537},
                      {'text':''}, {'truncated':'yes'}, {'title':'x'*513}):
            with self.subTest(extra=list(extra)):
                payload=dict(request_id='bad',kind='pasted_excerpt',text='Research',title='Title')
                payload.update(extra)
                with self.assertRaises(ValueError): save_intentional(self.store, self.a, payload)
        self.assertEqual(self.store.count('sources'), 0)

    def test_explicit_span_claim_has_exact_evidence_and_reason(self):
        text = 'SQLite is local. Keep this database.'
        result = self.save(text=text)
        claim = record_claim(self.store, self.a, result['source_id'], 'decision', 17, len(text), (0, 16))
        row = self.store.connection.execute('SELECT * FROM claims WHERE id=?', (claim['id'],)).fetchone()
        self.assertEqual(row['statement'], 'Keep this database.')
        self.assertEqual(row['reason'], 'SQLite is local.')
        with self.assertRaises(ValueError): record_claim(self.store, self.b, result['source_id'], 'task', 0, 4)
        delete_saved_source(self.store, result['source_id'])
        self.assertEqual(self.store.count('claims'), 0)

    def test_explicit_url_reference_and_removal_survive_reindexing(self):
        target = self.save('target', 'browser_page', url='https://example.org/database')
        source = self.save('link', text='Compare https://example.org/database for details.')
        edge = self.store.connection.execute("SELECT * FROM edges WHERE kind='references'").fetchone()
        self.assertIsNotNone(edge)
        remove_relationship(self.store, self.a, edge['id'])
        from semantic_memory.chunks import index_source
        index_source(self.store, source['source_id'])
        self.assertIsNone(self.store.connection.execute("SELECT * FROM edges WHERE kind='references'").fetchone())
        self.assertEqual(self.store.count('sources'), 2)

    def test_paused_memory_rejects_new_save(self):
        with self.store.transaction() as c: c.execute("INSERT INTO meta VALUES('memory_paused','User paused')")
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.count('sources'), 0)

    def test_new_save_invalidates_cached_project_context(self):
        ctx=self.ctx()
        self.save()
        with self.assertRaises(ValueError):current_grant(self.store,ctx,self.a)
