"""Never enter our own AppKit accessibility implementation from a worker."""
import os
import unittest
from unittest.mock import Mock, patch

import ax
import trail_mac


class SelfAccessibilityTests(unittest.TestCase):
    def test_legacy_reader_skips_self_before_any_native_call(self):
        with patch.object(ax, 'AS') as native:
            self.assertIsNone(ax.read(os.getpid(), 'Python'))
            self.assertEqual(native.mock_calls, [])

    def test_trail_front_hides_self_but_preserves_other_python_apps(self):
        app = Mock()
        app.processIdentifier.return_value = os.getpid()
        app.localizedName.return_value = 'Python'
        app.bundleIdentifier.return_value = 'org.python.python'
        with patch.object(trail_mac.macos, 'NSWorkspace') as workspace:
            workspace.sharedWorkspace.return_value.frontmostApplication.return_value = app
            self.assertIsNone(trail_mac.front())
            app.processIdentifier.return_value = os.getpid() + 1
            self.assertEqual(trail_mac.front()['pid'], os.getpid() + 1)

    def test_trail_reader_skips_self_before_permissions_or_tree_calls(self):
        reader = trail_mac.AXReader.__new__(trail_mac.AXReader)
        reader.AS = Mock()
        self.assertIsNone(reader.read({'pid': os.getpid(), 'bundle_id': 'org.python.python'}, True))
        self.assertEqual(reader.AS.mock_calls, [])

    def test_click_inspection_skips_self_before_native_hit_testing(self):
        reader = Mock()
        with patch.object(trail_mac, 'front', return_value=None):
            self.assertEqual(trail_mac.click_target(reader, 10, 20), (None, None))
        self.assertEqual(reader.mock_calls, [])
