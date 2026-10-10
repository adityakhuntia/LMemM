"""The first-run window's type and look: Figtree ships with the app (with its licence), every
symbol and weight the window asks for is named, and the accent is blue. Source checks only."""
import ast
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


class SetupAssets(unittest.TestCase):
    def test_figtree_ships_with_its_licence(self):
        fonts = os.path.join(ROOT, "assets", "fonts")
        self.assertGreater(os.path.getsize(os.path.join(fonts, "Figtree[wght].ttf")), 20000)
        self.assertIn("SIL Open Font License", open(os.path.join(fonts, "OFL.txt")).read())

    def test_the_accent_is_blue_not_orange(self):
        tree = ast.parse(open(os.path.join(ROOT, "src", "setup_kit.py")).read())
        accent = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "ACCENT")
        r, g, b = ast.literal_eval(accent.value)
        self.assertGreater(b, r + 0.4)                    # clearly blue
        self.assertGreater(b, g)

    def test_alignment_values_match_the_existing_widget_code(self):
        """widget.py (running on a Mac) uses setAlignment_(1) for centre; the kit must agree, or every
        line of text lands on the wrong side."""
        import re
        kit = open(os.path.join(ROOT, "src", "setup_kit.py")).read()
        self.assertIn("LEFT, CENTER, RIGHT = 0, 1, 2", kit)
        widget = open(os.path.join(ROOT, "src", "widget.py")).read()
        self.assertRegex(widget, r"setAlignment_\(1\)")
        self.assertIn("# centre", widget)

    def test_every_role_has_an_icon(self):
        import re
        ui = open(os.path.join(ROOT, "src", "onboarding_ui.py")).read()
        ob = open(os.path.join(ROOT, "src", "onboarding.py")).read()
        roles = re.search(r"ROLES = \(([^)]*)\)", ob).group(1)
        for role in re.findall(r'"(\w+)"', roles):
            self.assertIn(f'"{role}":', ui.split("ROLE_SYMBOLS")[1].split("}")[0], role)

    def test_labels_are_drawn_by_the_kit_not_by_text_fields(self):
        ui = open(os.path.join(ROOT, "src", "onboarding_ui.py")).read()
        self.assertNotIn("_label(", ui)                   # NSTextField labels sit high in a button
        self.assertNotIn("systemOrange", ui.replace("NSColor.systemOrangeColor() if state == onboarding.RESTART", ""))


if __name__ == "__main__":
    unittest.main()
