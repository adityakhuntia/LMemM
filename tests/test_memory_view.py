import unittest
from memory_view import evidence_rows,source_presentation
class ViewTests(unittest.TestCase):
    def test_rows_keep_citations_and_snapshot(self):
        rows=evidence_rows({'open_tasks':[{'statement':'TODO: Ship','at':'2026-10-10','citations':['c1']}], 'primary':[{'text':'retained','citation_id':'c2','at':'2026-10-10'}]})
        self.assertEqual(rows[0]['citation_id'],'c2')
        self.assertEqual(rows[0]['text'],'retained')
    def test_source_unavailable_and_current_file_are_distinct(self):
        v=source_presentation({'text':'old snapshot','locator':'/repo/a','at':'then','can_open_file':False})
        self.assertEqual(v['text'],'old snapshot');self.assertFalse(v['open_enabled'])
        self.assertIn('today',v['open_explanation'].lower())
