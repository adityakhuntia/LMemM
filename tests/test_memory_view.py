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


class PaneLayoutTests(unittest.TestCase):
    """The Memory tab keeps what people use on top and folds the setup (audit: a dozen identical buttons)."""

    def test_state_dot_is_never_red(self):
        from memory_view import state_tone
        self.assertEqual([state_tone(s) for s in ('Ready', 'Processing', 'Needs attention', 'Paused', 'Disabled')],
                         ['good', 'accent', 'warn', 'quiet', 'quiet'])

    def test_one_pause_control_that_applies(self):
        from memory_view import pause_action
        self.assertEqual(pause_action('Paused'), ('Resume Memory', 'resume'))
        self.assertEqual(pause_action('Ready'), ('Pause Memory', 'pause'))
        self.assertIsNone(pause_action('Disabled'))

    def test_setup_groups_keep_every_action_and_stop_comes_last(self):
        from memory_view import ADMIN_GROUPS
        actions = [a for _t, _l, items in ADMIN_GROUPS for _b, a, _k in items]
        self.assertEqual(sorted(actions), sorted(['confirm_model', 'install_extension', 'reconnect_extension', 'preview',
                                                  'confirm_agent', 'revoke_agent', 'confirm_disconnect']))
        self.assertEqual(ADMIN_GROUPS[-1][0], 'Stop')
        kinds = {a: k for _t, _l, items in ADMIN_GROUPS for _b, a, k in items}
        self.assertEqual(kinds['revoke_agent'], 'outline')         # what cuts something off looks heavier
        self.assertEqual(kinds['confirm_disconnect'], 'outline')

class AdminGroupsFollowState(unittest.TestCase):
    def test_installed_model_is_not_offered_again(self):
        from memory_view import admin_groups
        model = next(g for g in admin_groups({'model_state': 'available'}) if g[0] == 'Search model')
        self.assertEqual(model[2], [])
        self.assertIn('Installed', model[1])
        model = next(g for g in admin_groups({'model_state': 'missing'}) if g[0] == 'Search model')
        self.assertEqual([a for _b, a, _k in model[2]], ['confirm_model'])

    def test_the_fold_button_has_words_not_an_arrow(self):
        from memory_view import admin_toggle_label
        self.assertNotIn('▴', admin_toggle_label(True) + admin_toggle_label(False))

