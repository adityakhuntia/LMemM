import unittest
from semantic_helpers import SemanticFixture, source, policy
from semantic_memory.episodes import EpisodeBuilder, build_request


class EpisodeTests(SemanticFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.builder = EpisodeBuilder(self.db)

    def test_flush_and_duplicate_content(self):
        self.db.ingest(source(), policy())
        self.builder.accept('s1')
        self.db.ingest(source('repeat', at='2026-10-07T10:01:00+00:00'), policy())
        self.builder.accept('repeat')
        ids = self.builder.flush('2026-10-07T10:02:00+00:00')
        self.assertEqual(len(ids), 1)
        request = build_request(self.db, ids[0])
        self.assertEqual(len(request.evidence), 1)
        self.assertLessEqual(sum(len(e['text'].encode()) for e in request.evidence), 16384)

    def test_gap_artifact_and_pause_boundaries(self):
        for sid, at, artifact in [('a','10:00:00','main.py'),('b','10:05:00','main.py'),('c','10:05:01','other.py')]:
            self.db.ingest(source(sid,at='2026-10-07T'+at+'+00:00', artifact_locator='/projects/one/'+artifact),policy())
            result=self.builder.accept(sid)
            self.assertEqual(len(result), 0 if sid=='a' else 1)
        self.assertEqual(len(self.builder.boundary('pause','2026-10-07T10:05:02+00:00')),1)

    def test_restart_and_request_byte_bound(self):
        from semantic_memory.contracts import TextSpan
        self.db.ingest(source(spans=tuple(TextSpan(str(i),str(i)+'a'*4096) for i in range(6))),policy())
        ids=self.builder.accept('s1')
        self.assertTrue(ids)
        request=build_request(self.db,ids[0])
        self.assertLessEqual(sum(len(e['text'].encode()) for e in request.evidence),16384)
        self.assertTrue(request.truncated)
        restarted=EpisodeBuilder(self.db)
        self.assertEqual(restarted.accept('s1'),[])
