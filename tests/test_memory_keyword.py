"""Real FTS queries must enforce project, source, time and current grant scope."""
import dataclasses
import tempfile
import unittest
from memory_helpers import make_memory_fixture, memory_source, APP, AT
from semantic_memory.contracts import SourceScope
from semantic_memory.api_contracts import Query
from semantic_memory.project_scope import bind_project
from semantic_memory.grants import enroll_grant, authorize, revoke_grant
from semantic_memory import chunks, search
from semantic_memory.retention import delete_sources


class MemoryKeywordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store,self.roots,self.policy=make_memory_fixture(self.tmp.name);self.addCleanup(self.store.close)
        self.a=bind_project(self.store,'a',self.roots[0],'2026-10-01T00:00:00+00:00')
        self.b=bind_project(self.store,'b',self.roots[1],'2026-10-01T00:00:00+00:00')
        self.grant=enroll_grant(self.store,'agent',{self.a.project_id},SourceScope(frozenset({APP})))
        self.ctx=authorize(self.store,self.grant.id,self.a.project_id)

    def add(self,sid,text,root=None,**kw):
        result=self.store.ingest(memory_source(sid,root or self.roots[0],text,**kw),self.policy)
        chunks.index_source(self.store,sid)
        return result.occurrence_ids[0]

    def query(self,text,**kw):
        return search.keyword_candidates(self.store,self.ctx,Query(self.a.project_id,text,**kw))

    def test_scope_precedes_limit_even_when_other_project_has_better_matches(self):
        for i in range(55):self.add('denied-'+str(i),'needle needle needle',self.roots[1])
        allowed=self.add('allowed','needle local evidence')
        self.assertEqual([h.citation_id for h in self.query('needle')],[allowed])
        self.assertIsNone(search.resolve_source(self.store,self.ctx,self.a.project_id,self.add('denied2','needle',self.roots[1])))

    def test_literal_query_operators_and_punctuation_never_widen_scope(self):
        self.add('a','café retry_upload')
        self.add('b','not related',self.roots[1])
        self.assertEqual(len(self.query('café')),1)
        for value in ('" OR *', 'NEAR(retry_upload)', "'; DROP TABLE sources; --"):
            self.query(value)  # Treat tokens literally; no FTS syntax exception/injection.
        for value in ('','   ','!!!'):
            with self.assertRaisesRegex(ValueError,'searchable'):self.query(value)
        self.assertEqual(self.store.count('sources'),2)

    def test_shared_text_dedup_keeps_authorized_citation_after_delete(self):
        a=self.add('a','Same shared text.');b=self.add('b','Same shared text.')
        self.assertEqual(len(self.query('shared')),1)
        delete_sources(self.store,{'a'})
        self.ctx=authorize(self.store,self.grant.id,self.a.project_id)
        self.assertEqual([h.citation_id for h in self.query('shared')],[b])
        self.assertIsNone(search.resolve_source(self.store,self.ctx,self.a.project_id,a))
        detail=search.resolve_source(self.store,self.ctx,self.a.project_id,b)
        self.assertEqual(detail.text,'Same shared text.')

    def test_retained_versions_are_resolved_exactly_and_time_filtered(self):
        old=self.add('old','Old retained SQLite choice.',at='2026-10-09T10:00:00+00:00')
        new=self.add('new','New retained SQLite choice.')
        hits=self.query('SQLite',start='2026-10-10T00:00:00+00:00',end='2026-10-11T00:00:00+00:00')
        self.assertEqual([h.citation_id for h in hits],[new])
        self.assertEqual(search.resolve_source(self.store,self.ctx,self.a.project_id,old).text,'Old retained SQLite choice.')

    def test_revoked_context_cannot_query_or_resolve(self):
        oid=self.add('a','Private canary.')
        revoke_grant(self.store,self.grant.id)
        with self.assertRaises(ValueError):self.query('canary')
        with self.assertRaises(ValueError):search.resolve_source(self.store,self.ctx,self.a.project_id,oid)

    def test_pre_enrollment_evidence_and_ungranted_apps_remain_unavailable(self):
        old=self.add('old','Older canary.',at='2026-09-20T10:00:00+00:00')
        self.assertEqual(self.query('canary'),[])
        self.assertIsNone(search.resolve_source(self.store,self.ctx,self.a.project_id,old))
        empty=enroll_grant(self.store,'other',{self.a.project_id},SourceScope(frozenset({'other-app'})))
        ctx=authorize(self.store,empty.id,self.a.project_id)
        self.add('new','New canary.')
        self.assertEqual(search.keyword_candidates(self.store,ctx,Query(self.a.project_id,'canary')),[])
