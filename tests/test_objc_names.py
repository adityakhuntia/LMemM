"""Every Objective-C class defined in src/ must have a unique Python name: PyObjC registers
classes globally, so two modules defining `_Tile` crash at import ("overriding existing
Objective-C class"). Source check only; needs no macOS."""
import ast
import collections
import glob
import os
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")


class ObjcClassNames(unittest.TestCase):
    def test_no_class_name_is_defined_twice(self):
        seen = collections.defaultdict(list)
        for path in glob.glob(os.path.join(SRC, "*.py")):
            for node in ast.parse(open(path).read()).body:
                if isinstance(node, ast.ClassDef):
                    seen[node.name].append(os.path.basename(path))
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual(dupes, {})


if __name__ == "__main__":
    unittest.main()
