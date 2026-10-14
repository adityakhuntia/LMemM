"""The hard-coded colours keep their contrast (audit: the orange on the light pill was 2.1-2.8:1)."""
import unittest

import palette as p


class PaletteContrast(unittest.TestCase):
    def test_pill_marks_read_on_both_pills(self):            # marks: 3:1
        self.assertGreaterEqual(p.contrast(p.ORANGE_ON_DARK_PILL, p.PILL_DARK), 3.0)
        self.assertGreaterEqual(p.contrast(p.ORANGE_ON_LIGHT_PILL, p.PILL_LIGHT), 3.0)

    def test_pill_warning_reads_on_both_pills(self):         # it is text-like: 4.5:1
        self.assertGreaterEqual(p.contrast(p.RED_ON_DARK_PILL, p.PILL_DARK), 4.5)
        self.assertGreaterEqual(p.contrast(p.RED_ON_LIGHT_PILL, p.PILL_LIGHT), 4.5)

    def test_accent_buttons_and_words(self):
        self.assertGreaterEqual(p.contrast(p.ACCENT, (1, 1, 1)), 4.5)
        self.assertGreaterEqual(p.contrast(p.ACCENT_TEXT_ON_LIGHT, p.CARD_LIGHT), 4.5)
        self.assertGreaterEqual(p.contrast(p.ACCENT_TEXT_ON_DARK, p.CARD_DARK), 4.5)

    def test_orange_words_on_the_note_card(self):
        self.assertGreaterEqual(p.contrast(p.ORANGE_TEXT_ON_LIGHT, p.CARD_LIGHT), 4.5)
        self.assertGreaterEqual(p.contrast(p.ORANGE_TEXT_ON_DARK, p.CARD_DARK), 4.5)

    def test_contrast_is_symmetric_and_bounded(self):
        self.assertAlmostEqual(p.contrast((0, 0, 0), (1, 1, 1)), 21.0, places=1)
        self.assertEqual(p.contrast(p.ACCENT, (1, 1, 1)), p.contrast((1, 1, 1), p.ACCENT))


if __name__ == "__main__":
    unittest.main()
