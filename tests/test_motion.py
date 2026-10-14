"""The motion budget from the Kowalski audit, held as numbers (no Mac needed)."""
import unittest

import motion


class MotionBudget(unittest.TestCase):
    def test_every_ui_duration_is_under_300ms(self):
        for name in ("PRESS_SECONDS", "POP_SECONDS", "MODAL_SECONDS", "STEP_SECONDS", "CELEBRATE_SECONDS"):
            self.assertLess(getattr(motion, name), 0.3, name)

    def test_nothing_grows_from_zero(self):
        self.assertGreaterEqual(motion.POP_SCALE, 0.9)
        self.assertGreaterEqual(motion.MODAL_SCALE, 0.9)

    def test_the_curve_is_an_ease_out(self):                  # starts fast: the first control point is steep
        x1, y1, x2, y2 = motion.EASE
        self.assertGreater(y1 / max(x1, 1e-9), 1.0)
        self.assertEqual(y2, 1.0)

    def test_without_a_mac_motion_is_off_and_harmless(self):
        self.assertFalse(motion.reduced())                    # no AppKit here
        motion.pop(object())                                  # best effort: never raises
        motion.step(object())
        motion.fade_in(object())


if __name__ == "__main__":
    unittest.main()
