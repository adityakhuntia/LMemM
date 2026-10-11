"""Output-boundary checks catch stale cached snippets after scope/data changes."""
import unittest
import threading
from memory_helpers import APP
from test_memory_index_worker import IndexFixture
from semantic_memory.api_contracts import Query
from semantic_memory.contracts import SourceScope
from semantic_memory.grants import enroll_grant,authorize,revoke_grant
from semantic_memory.vector_index import activate_generation
from semantic_memory.search import search_project,resolve_source
from semantic_memory import context_service,retention,grants


class RevocationTests(IndexFixture,unittest.TestCase):
    def ctx(self):
        g=enroll_grant(self.store,'agent',{self.binding.project_id},SourceScope(frozenset({APP})))
        return g,authorize(self.store,g.id,self.binding.project_id)

    def test_saved_result_cannot_be_serialized_after_source_deletion(self):
        self.add('a','SQLite PRIVATE_CANARY');g,ctx=self.ctx()
        result=search_project(self.store,None,ctx,Query(self.binding.project_id,'SQLite'))
        retention.delete_memory_source(self.store,'a')
        with self.assertRaises(ValueError):context_service.serialize_authorized(self.store,ctx,result)

    def test_saved_result_cannot_be_serialized_after_grant_revocation(self):
        self.add('a','SQLite PRIVATE_CANARY');g,ctx=self.ctx()
        result=search_project(self.store,None,ctx,Query(self.binding.project_id,'SQLite'))
        revoke_grant(self.store,g.id)
        with self.assertRaises(ValueError):context_service.serialize_authorized(self.store,ctx,result)

    def test_revocation_during_query_embedding_never_returns_snippet(self):
        self.add();self.drain();activate_generation(self.store,self.gen);g,ctx=self.ctx()
        entered=threading.Event();release=threading.Event();outcome=[]
        def hold():
            entered.set()
            if not release.wait(5):raise RuntimeError('test timeout')
        self.backend.on_embed=hold
        def query():
            try:outcome.append(search_project(self.store,self.backend,ctx,Query(self.binding.project_id,'SQLite')))
            except ValueError:outcome.append('unavailable')
        t=threading.Thread(target=query);t.start()
        try:
            self.assertTrue(entered.wait(5));revoke_grant(self.store,g.id)
        finally:release.set();t.join(5)
        self.assertEqual(outcome,['unavailable'])

    def test_project_revocation_immediately_invalidates_context(self):
        self.add();g,ctx=self.ctx()
        grants.revoke_project(self.store,self.binding.project_id)
        with self.assertRaises(ValueError):search_project(self.store,None,ctx,Query(self.binding.project_id,'SQLite'))

    def test_source_scope_is_blocked_before_physical_cleanup(self):
        from unittest.mock import patch
        from semantic_memory.contracts import AccessPolicy
        self.add('a','SQLite PRIVATE_CANARY');g,_=self.ctx()
        actual=retention.delete_sources
        def cleanup(ids_store,ids):
            fresh=authorize(self.store,g.id,self.binding.project_id)
            result=search_project(self.store,None,fresh,Query(self.binding.project_id,'SQLite'))
            self.assertEqual(result.primary,())
            return actual(ids_store,ids)
        with patch.object(retention,'delete_sources',side_effect=cleanup):
            retention.revoke_scope(self.store,SourceScope(frozenset({APP})),AccessPolicy(2,frozenset(),frozenset()))
