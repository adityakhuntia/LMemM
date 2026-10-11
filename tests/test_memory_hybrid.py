"""Hybrid search must find paraphrases without making similarity into facts."""
import unittest
from test_memory_index_worker import IndexFixture
from semantic_memory.api_contracts import Query
from semantic_memory.contracts import SourceScope
from semantic_memory.grants import enroll_grant,authorize
from semantic_memory.vector_index import activate_generation
from semantic_memory import search
from memory_helpers import APP


class HybridTests(IndexFixture,unittest.TestCase):
    def context(self):
        g=enroll_grant(self.store,'agent',{self.binding.project_id},SourceScope(frozenset({APP})))
        return authorize(self.store,g.id,self.binding.project_id)

    def test_paraphrase_uses_vectors_and_returns_inspectable_evidence(self):
        self.add('a','SQLite keeps the database on this device.');self.drain();activate_generation(self.store,self.gen)
        result=search.search_project(self.store,self.backend,self.context(),Query(self.binding.project_id,'SQLite storage'))
        self.assertEqual(result.mode,'hybrid')
        self.assertEqual(result.primary[0].text,'SQLite keeps the database on this device.')
        self.assertTrue(result.primary[0].citation_id.startswith('evidence-'))
        self.assertLessEqual(len(result.primary),10);self.assertLessEqual(len(result.related),10)

    def test_pause_never_calls_model_and_existing_keywords_remain_available(self):
        self.add();self.drain();activate_generation(self.store,self.gen)
        with self.store.transaction() as c:c.execute("INSERT OR REPLACE INTO meta VALUES('memory_paused','1')")
        before=self.backend.calls
        result=search.search_project(self.store,self.backend,self.context(),Query(self.binding.project_id,'SQLite'))
        self.assertEqual(result.mode,'keyword-only');self.assertEqual(self.backend.calls,before)
        self.assertEqual(len(result.primary),1)

    def test_supported_reference_expands_once_only_to_permitted_captured_artifacts(self):
        from dataclasses import replace
        from semantic_memory.chunks import index_source
        from memory_helpers import memory_source
        target=replace(memory_source('target',self.roots[0],'Relevant rollback implementation.'),artifact_locator=self.roots[0]+'/rollback.py')
        self.store.ingest(target,self.policy);index_source(self.store,'target')
        self.add('reference','SQLite context references ./rollback.py and ./not-captured.py')
        result=search.search_project(self.store,None,self.context(),Query(self.binding.project_id,'SQLite'))
        self.assertEqual(len(result.primary),1)
        self.assertEqual([r.text for r in result.related],['Relevant rollback implementation.'])
        self.assertEqual(result.related[0].related_to,result.primary[0].citation_id)
