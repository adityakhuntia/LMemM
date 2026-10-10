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


class ObjcMethodNames(unittest.TestCase):
    """PyObjC turns a method on an Objective-C subclass into a selector: its argument count must match
    its name's colons. `def restyle(self, fill, border)` crashes at import on a Mac ("expects 0
    arguments"), so any method that takes arguments must be named with underscores (`restyle_border_`)."""

    OBJC_BASES = {"NSView", "NSObject", "NSWindow", "NSPanel", "NSTextField", "_Flipped", "_Tap", "_KeyPanel"}

    def test_methods_with_arguments_have_underscored_names(self):
        problems = []
        for path in glob.glob(os.path.join(SRC, "*.py")):
            tree = ast.parse(open(path).read())
            objc_classes = set(self.OBJC_BASES)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                    if bases & objc_classes:
                        objc_classes.add(node.name)
                        for fn in node.body:
                            if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("__"):
                                continue
                            decorated = any("python_method" in ast.dump(d) for d in fn.decorator_list)
                            extra = len(fn.args.args) - 1
                            if extra > 0 and "_" not in fn.name and not decorated:
                                problems.append(f"{os.path.basename(path)}:{node.name}.{fn.name}")
        self.assertEqual(problems, [])
