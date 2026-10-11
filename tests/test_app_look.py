"""app_look: web apps get their own colour and symbol."""

import unittest

import app_look


class AppLookTests(unittest.TestCase):
    def test_gmail_has_a_red_envelope_and_unknown_apps_have_none(self):
        symbol, rgb = app_look.look("Gmail")
        self.assertEqual(symbol, "envelope.fill")
        self.assertTrue(rgb[0] > rgb[1] and rgb[0] > rgb[2])
        self.assertIsNone(app_look.look("Some Unknown App"))

    def test_every_look_is_a_symbol_and_three_colours_between_0_and_1(self):
        for app, (symbol, rgb) in app_look.WEB.items():
            self.assertTrue(symbol, app)
            self.assertEqual(len(rgb), 3, app)
            self.assertTrue(all(0 <= c <= 1 for c in rgb), app)


if __name__ == "__main__":
    unittest.main()
