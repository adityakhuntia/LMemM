import json
from test_semantic_episodes import EpisodeTests
from semantic_memory.inference import InferenceWorker, validate_extraction
from semantic_memory.episodes import build_request
from test_semantic_store import source, policy

class FakeExtractor:
    def __init__(self, payload='{"candidates":[]}'):
        self.payload=payload; self.calls=0; self.cancelled=False
    def extract(self, request):
        self.calls+=1
        return self.payload
    def cancel(self): self.cancelled=True

class InferenceTests(EpisodeTests):
    def request(self):
        self.db.ingest(source(),policy()); self.builder.accept('s1')
        eid=self.builder.boundary('stop','2026-10-07T10:01:00+00:00')[0]
        return build_request(self.db,eid)

    def test_rejects_unknown_refs_and_model_commands(self):
        request=self.request()
        invalid=[{'candidates':[{'type':'decision','statement':'invented','subject_id':'unknown','evidence_ids':['unknown']}]},
                 {'candidates':[],'command':'send data'}, {'candidates':'wrong'}]
        for payload in invalid:
            with self.assertRaises(ValueError): validate_extraction(json.dumps(payload),request)

    def test_retry_then_visible_unprocessed(self):
        request=self.request(); fake=FakeExtractor('invalid JSON')
        worker=InferenceWorker(self.db,fake)
        self.assertTrue(worker.enqueue(request.episode_id))
        self.assertFalse(worker.enqueue(request.episode_id))
        result=worker.run_one()
        self.assertEqual((result.status,result.attempts),('unprocessed',2))
        self.assertEqual(fake.calls,2)
        self.assertEqual(self.db.count('occurrences'),1)

    def test_revision_change_during_inference_never_commits(self):
        request=self.request(); db=self.db
        class Revoker(FakeExtractor):
            def extract(self, request):
                with db.transaction() as c: c.execute("UPDATE meta SET value='2' WHERE key='revision'")
                return super().extract(request)
        worker=InferenceWorker(self.db,Revoker())
        worker.enqueue(request.episode_id)
        self.assertEqual(worker.run_one().status,'cancelled')

    def test_queue_count_bound(self):
        for i in range(9):
            self.db.ingest(source('s'+str(i),at=f'2026-10-07T10:{i:02d}:00+00:00'),policy())
            self.builder.accept('s'+str(i)); self.builder.boundary('stop',f'2026-10-07T10:{i:02d}:01+00:00')
        ids=[r[0] for r in self.db.connection.execute('SELECT id FROM episodes')]
        worker=InferenceWorker(self.db,FakeExtractor())
        self.assertEqual(sum(worker.enqueue(i) for i in ids),8)
