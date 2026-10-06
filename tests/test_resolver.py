"""macOS integration tests: exercise the actual Vision bridge and OCR engine."""

import tempfile
import unittest
from pathlib import Path

import AppKit
import Foundation

import resolver
from memory_content import extract_content


class VisionTests(unittest.TestCase):
    def test_invalid_image_reports_vision_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.jpg"
            path.write_bytes(b"This is not an image")
            with self.assertRaisesRegex(RuntimeError, "Vision failed"):
                resolver.run_vision(str(path), 800, 300)

    def test_recognizes_text_in_generated_image(self):
        # No personal captures are needed to reproduce the bridge failure.
        image = AppKit.NSImage.alloc().initWithSize_((800, 300))
        image.lockFocus()
        try:
            AppKit.NSColor.whiteColor().set()
            AppKit.NSRectFill(((0, 0), (800, 300)))
            Foundation.NSString.stringWithString_("We chose SQLite because the data stays local.").drawAtPoint_withAttributes_(
                (40, 140),
                {AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(30),
                 AppKit.NSForegroundColorAttributeName: AppKit.NSColor.blackColor()},
            )
        finally:
            image.unlockFocus()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text.tiff"
            image.TIFFRepresentation().writeToFile_atomically_(str(path), True)
            width, height = resolver.image_size(str(path))
            lines, rects, _ = resolver.run_vision(str(path), width, height)
        self.assertIn("We chose SQLite", " ".join(line["text"] for line in lines))
        self.assertTrue(all(line["box"][2] > 0 and line["box"][3] > 0 for line in lines))
        meta = {"app": "Notes", "window": "Project plan", "iso": "2026-10-04T09:00:00",
                "window_region": [0, 0, 1, 1]}
        objects, _ = resolver.classify(lines, rects, meta, width, height)
        content = extract_content({"objects": objects, "image_size": {"w": width, "h": height}}, meta)
        self.assertIn("We chose SQLite because the data stays local.", content["decision_quotes"])


if __name__ == "__main__":
    unittest.main()
