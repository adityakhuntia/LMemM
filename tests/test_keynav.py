import unittest
import keynav as k

ROWS = {"side": [("a", "A"), ("b", "B")], "main": [("x", "X"), ("y", "Y"), ("z", "Z")]}
S = lambda zone="main", id=None: {"zone": zone, "id": id}


class KeyNavTests(unittest.TestCase):
    def test_down_takes_first_then_walks_and_stops(self):
        st = S()
        seen = []
        for _ in range(5):
            st, _cb = k.press(st, ROWS, k.DOWN)
            seen.append(st["id"])
        self.assertEqual(seen, ["x", "y", "z", "z", "z"])

    def test_up_from_nothing_takes_last_and_stops_at_first(self):
        st, _ = k.press(S(), ROWS, k.UP)
        self.assertEqual(st["id"], "z")
        for _ in range(5):
            st, _ = k.press(st, ROWS, k.UP)
        self.assertEqual(st["id"], "x")

    def test_return_opens_the_highlighted_row_only(self):
        self.assertEqual(k.press(S(id="y"), ROWS, k.RETURN)[1], "Y")
        self.assertEqual(k.press(S(id="y"), ROWS, k.ENTER)[1], "Y")
        self.assertIsNone(k.press(S(), ROWS, k.RETURN)[1])
        self.assertIsNone(k.press(S(id="gone"), ROWS, k.RETURN)[1])

    def test_left_and_right_change_zone_and_clear_the_highlight(self):
        st, _ = k.press(S("main", "y"), ROWS, k.LEFT)
        self.assertEqual(st, S("side", None))
        st, _ = k.press(st, ROWS, k.RIGHT)
        self.assertEqual(st, S("main", None))

    def test_a_zone_with_no_rows_is_not_entered(self):
        rows = {"side": [], "main": [("x", "X")]}
        st, _ = k.press(S("main", "x"), rows, k.LEFT)
        self.assertEqual(st, S("main", "x"))

    def test_empty_zone_falls_to_the_other(self):
        rows = {"side": [("a", "A")], "main": []}
        st, _ = k.press(S("main"), rows, k.DOWN)
        self.assertEqual(st, S("side", "a"))

    def test_nothing_anywhere(self):
        st, cb = k.press(S(), {"side": [], "main": []}, k.DOWN)
        self.assertEqual((st["id"], cb), (None, None))

    def test_other_keys_do_nothing(self):
        self.assertEqual(k.press(S(id="x"), ROWS, 0), (S(id="x"), None))


if __name__ == "__main__":
    unittest.main()
