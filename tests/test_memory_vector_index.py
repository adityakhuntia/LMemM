"""Real SQLite vector scoring catches cross-scope ranking and mixed dimensions."""
import unittest
import numpy as np
from test_memory_index_worker import IndexFixture
from semantic_memory.grants import enroll_grant,authorize
from semantic_memory.contracts import SourceScope
from memory_helpers import APP
from semantic_memory.api_contracts import Query
from semantic_memory import vector_index


class VectorIndexTests(IndexFixture, unittest.TestCase):
    def test_scoring_uses_only_active_generation_and_current_scope(self):
        self.add('a','SQLite local choice.');self.add('b','Unrelated shipping label.');self.drain()
        vector_index.activate_generation(self.store,self.gen)
        g=enroll_grant(self.store,'agent',{self.binding.project_id},SourceScope(frozenset({APP})))
        ctx=authorize(self.store,g.id,self.binding.project_id)
        hits=vector_index.vector_candidates(self.store,ctx,Query(self.binding.project_id,'local database'),np.array([1,0,0],dtype=np.float32))
        self.assertEqual(hits[0].text,'SQLite local choice.')
        self.assertEqual(hits[0].score,1.0)
        for v in (np.ones(4),np.zeros(3),np.array([float('nan'),0,1])):
            with self.assertRaises(ValueError):vector_index.vector_candidates(self.store,ctx,Query(self.binding.project_id,'query'),v)
        # A rebuild makes only keyword retrieval available, never stale mixed vectors.
        vector_index.begin_generation(self.store,self.backend.manifest)
        self.assertEqual(vector_index.vector_candidates(self.store,ctx,Query(self.binding.project_id,'query'),np.array([1,0,0])),[])
