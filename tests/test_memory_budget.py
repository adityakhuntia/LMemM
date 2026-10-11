"""Quota tests include non-DB bridge buffers and preserve pinned evidence."""
import unittest
from pathlib import Path
from test_memory_index_worker import IndexFixture
from semantic_memory import retention


class MemoryBudgetTests(IndexFixture,unittest.TestCase):
    def test_bridge_buffers_count_toward_semantic_budget(self):
        bridge=self.store.path.parent/'bridge';bridge.mkdir(mode=0o700)
        (bridge/'events').mkdir();(bridge/'events'/'pending.json').write_bytes(b'x'*20000)
        usage=retention.memory_usage(self.store,bridge)
        self.assertEqual(usage['bridge_bytes'],20000)
        self.assertEqual(usage['total_bytes'],usage['database_bytes']+20000)
        self.assertEqual(retention.semantic_bytes(self.store),usage['total_bytes'])

    def test_pinned_over_budget_does_not_destroy_evidence(self):
        self.add()
        with self.store.transaction() as c:c.execute('UPDATE sources SET pinned=1')
        status=retention.enforce_budget(self.store,'2026-10-10T11:00:00+00:00',semantic_limit=1)
        self.assertEqual(status.paused_reason,'semantic_budget')
        self.assertEqual(self.store.count('sources'),1)

    def test_budget_directory_symlinks_are_rejected(self):
        external=Path(self.tmp.name)/'outside';external.mkdir()
        bridge=self.store.path.parent/'bridge';bridge.symlink_to(external,target_is_directory=True)
        with self.assertRaises(ValueError):retention.memory_usage(self.store,bridge)
