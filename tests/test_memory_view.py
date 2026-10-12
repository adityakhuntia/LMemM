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


class FriendlyTextTests(unittest.TestCase):
    def test_dates_read_as_today_yesterday_or_day_month(self):
        from datetime import datetime, timezone
        from memory_view import friendly
        now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        tz = now.astimezone().tzinfo
        def local(day, hour):
            return datetime(2026, 10, day, hour, 5, tzinfo=tz).astimezone(timezone.utc).isoformat()
        self.assertEqual(friendly(local(12, 9), now).split(",")[0], "Today")
        self.assertEqual(friendly(local(11, 9), now).split(",")[0], "Yesterday")
        self.assertTrue(friendly(local(3, 9), now).startswith("3 Oct, "))
        self.assertEqual(friendly("not a date", now), "not a date")

    def test_long_file_names_are_cut_in_the_middle(self):
        from memory_view import short_name
        name = short_name("/Users/a/.lmemm-project-notes/native-3131876c15f4e10d0127af062170c0a1.md")
        self.assertLessEqual(len(name), 26)
        self.assertIn("…", name)
        self.assertTrue(name.endswith("c0a1.md"))
        self.assertEqual(short_name("/x/short.md"), "short.md")
