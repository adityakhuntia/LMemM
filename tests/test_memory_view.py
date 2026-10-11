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
    def test_evidence_preserves_provenance_and_truncation(self):
        rows=evidence_rows({'primary':[dict(text='excerpt',origin_type='observed_screen_text',truncated=True),dict(text='intentional',origin_type='user_note',truncated=False)]})
        self.assertEqual(rows[0]['provenance'],'Observed content');self.assertTrue(rows[0]['truncated'])
        self.assertEqual(rows[1]['provenance'],'Your note')
        detail=source_presentation(dict(text='excerpt',locator='/a',at='now',origin_type='observed_screen_text',truncated=True))
        self.assertTrue(detail['truncated']);self.assertEqual(detail['provenance'],'Observed content')
