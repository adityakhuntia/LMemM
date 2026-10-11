"""Chunk offsets catch lossy Unicode splitting and ownership reuse."""
import tempfile
import unittest
from memory_helpers import make_memory_fixture, memory_source
from semantic_memory import chunks
from semantic_memory.retention import delete_sources


class MemoryChunkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store,self.roots,self.policy=make_memory_fixture(self.tmp.name);self.addCleanup(self.store.close)

    def test_unicode_chunks_preserve_every_character_and_exact_offsets(self):
        text=('Café 🙂 中文 evidence.\n'*160)[:2000]
        src=self.store.ingest(memory_source('a',self.roots[0],text),self.policy)
        original=self.store.evidence(src.occurrence_ids)[0]['text']
        ids=chunks.index_source(self.store,'a')
        self.assertGreater(len(ids),1)
        rows=self.store.connection.execute('SELECT * FROM memory_chunks ORDER BY start_char').fetchall()
        covered=set()
        prior=None
        for row in rows:
            self.assertEqual(original[row['start_char']:row['end_char']],row['text'])
            self.assertLessEqual(len(row['text'].encode()),1024)
            covered.update(range(row['start_char'],row['end_char']))
            if prior:
                overlap=original[row['start_char']:prior['end_char']]
                self.assertLessEqual(len(overlap.encode()),128)
            prior=row
        self.assertEqual(covered,set(range(len(original))))
        self.assertEqual(chunks.index_source(self.store,'a'),ids)

    def test_shared_text_is_owned_by_occurrences_and_deletion_cascades_fts(self):
        for sid in ('a','b'):
            self.store.ingest(memory_source(sid,self.roots[0],'Same shared evidence.'),self.policy)
        a=chunks.index_source(self.store,'a');b=chunks.index_source(self.store,'b')
        self.assertNotEqual(a,b)
        delete_sources(self.store,{'a'})
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM memory_chunks').fetchone()[0],1)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM chunk_search').fetchone()[0],1)
        with self.assertRaises(ValueError):chunks.index_source(self.store,'a')

    def test_empty_text_has_no_chunks(self):
        self.store.ingest(memory_source('a',self.roots[0],''),self.policy)
        self.assertEqual(chunks.index_source(self.store,'a'),())
