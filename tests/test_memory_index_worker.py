"""Index lifecycle tests catch replay work, stale inference commits and oversized batches."""
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
import numpy as np
from memory_helpers import make_memory_fixture,memory_source,APP,AT
from semantic_memory.api_contracts import ModelManifest
from semantic_memory.project_scope import bind_project
from semantic_memory.contracts import SourceScope
from semantic_memory.grants import enroll_grant,revoke_grant
from semantic_memory.retention import delete_sources
from semantic_memory import index_worker,vector_index


class FakeEmbedder:
    def __init__(self):
        self.manifest=ModelManifest('synthetic','a'*64,3,512,1,'fake','/synthetic/model')
        self.calls=0;self.max_payload=0;self.on_embed=None
    def embed(self,texts,*,query):
        self.calls+=1;self.max_payload=max(self.max_payload,sum(len(t.encode()) for t in texts))
        if self.on_embed:self.on_embed()
        return np.asarray([[1,0,0] if 'SQLite' in t else [0,1,0] for t in texts],dtype=np.float32)
    def cancel(self):pass


class IndexFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store,self.roots,self.policy=make_memory_fixture(self.tmp.name);self.addCleanup(self.store.close)
        self.binding=bind_project(self.store,'a',self.roots[0],AT)
        self.backend=FakeEmbedder();self.gen=vector_index.begin_generation(self.store,self.backend.manifest)
        self.worker=index_worker.IndexWorker(self.store,self.backend)

    def add(self,sid='a',text='SQLite stays local.'):
        self.store.ingest(memory_source(sid,self.roots[0],text),self.policy)
        index_worker.schedule_source(self.store,sid)

    def drain(self):
        for _ in range(100):
            if not self.worker.run_one():return
        self.fail('Index worker did not finish bounded jobs')



class IndexWorkerTests(IndexFixture, unittest.TestCase):
    def test_replay_and_shared_text_reuse_embeddings(self):
        self.add();self.drain();calls=self.backend.calls
        index_worker.schedule_source(self.store,'a');self.drain()
        self.assertEqual(self.backend.calls,calls)
        self.add('b');self.drain()
        self.assertEqual(self.backend.calls,calls)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_vectors').fetchone()[0],2)

    def test_delete_or_revoke_during_embedding_commits_nothing(self):
        self.add()
        self.backend.on_embed=lambda:delete_sources(self.store,{'a'})
        self.worker.run_one()
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_vectors').fetchone()[0],0)
        self.backend.on_embed=None;self.add('b')
        g=enroll_grant(self.store,'agent',{self.binding.project_id},SourceScope(frozenset({APP})))
        self.backend.on_embed=lambda:revoke_grant(self.store,g.id)
        self.worker.run_one()
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_vectors').fetchone()[0],0)

    def test_pause_and_bounded_payload(self):
        self.add(text='SQLite evidence. '*240)
        with self.store.transaction() as c:c.execute("INSERT OR REPLACE INTO meta VALUES('memory_paused','1')")
        self.assertFalse(self.worker.run_one());self.assertEqual(self.backend.calls,0)
        with self.store.transaction() as c:c.execute("DELETE FROM meta WHERE key='memory_paused'")
        self.drain();self.assertLessEqual(self.backend.max_payload,128*1024)

    def test_incomplete_rebuild_never_activates_and_restart_is_resumable(self):
        self.add()
        with self.assertRaises(ValueError):vector_index.activate_generation(self.store,self.gen)
        index_worker.IndexWorker(self.store,self.backend).run_one()
        self.drain();vector_index.activate_generation(self.store,self.gen)
        newer=replace(self.backend.manifest,digest='b'*64)
        gen2=vector_index.begin_generation(self.store,newer)
        self.assertNotEqual(gen2,self.gen)
        self.assertIsNone(vector_index.active_generation(self.store))
        with self.assertRaises(ValueError):vector_index.activate_generation(self.store,gen2)

    def test_existing_evidence_is_chunked_when_rebuilding_after_restart(self):
        self.store.ingest(memory_source('prior',self.roots[0],'SQLite persisted evidence.'),self.policy)
        gen=vector_index.begin_generation(self.store,self.backend.manifest)
        self.drain()
        vector_index.activate_generation(self.store,gen)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_vectors').fetchone()[0],1)

    def test_two_workers_share_one_model_slot(self):
        import threading
        self.add()
        entered=threading.Event();release=threading.Event()
        def hold():
            entered.set()
            if not release.wait(5):raise RuntimeError('test timeout')
        self.backend.on_embed=hold
        thread=threading.Thread(target=self.worker.run_one);thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertFalse(index_worker.IndexWorker(self.store,self.backend).run_one())
            self.assertEqual(self.backend.calls,1)
        finally:release.set();thread.join(5)
        self.assertFalse(thread.is_alive())

    def test_quota_and_manifest_mismatch_never_activate_partial_vectors(self):
        self.add()
        self.backend.manifest=replace(self.backend.manifest,digest='c'*64)
        with self.assertRaises(ValueError):self.worker.run_one()
        self.backend.manifest=replace(self.backend.manifest,digest='a'*64)
        with self.store.transaction() as c:c.execute("INSERT OR REPLACE INTO meta VALUES('semantic_limit','1')")
        self.worker.run_one()
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_vectors').fetchone()[0],0)
        with self.assertRaises(ValueError):vector_index.activate_generation(self.store,self.gen)

    def test_pending_query_takes_priority_between_background_jobs(self):
        self.add()
        self.store.query_waiters=1
        self.assertFalse(self.worker.run_one())
        self.assertEqual(self.backend.calls,0)
