"""Simulate intermittent native Vision failures; real OCR is tested separately."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import Foundation
import resolver


class VisionRetryTests(unittest.TestCase):
    def test_failed_accurate_ocr_retries_and_uses_successful_fast_result(self):
        vn = {name: MagicMock() for name in ("VNImageRequestHandler", "VNRecognizeTextRequest",
              "VNDetectRectanglesRequest", "VNClassifyImageRequest")}
        requests = [MagicMock() for _ in range(3)]
        for req in requests:
            req.results.return_value = []
        vn["VNRecognizeTextRequest"].alloc.return_value.init.side_effect = requests
        handler = vn["VNImageRequestHandler"].alloc.return_value.initWithURL_options_.return_value
        handler.performRequests_error_.side_effect = [(False, "combined failed"), (True, None),
                                                       (False, "accurate failed"), (True, None)]
        vn["VNDetectRectanglesRequest"].alloc.return_value.init.return_value.results.return_value = []
        vn["VNClassifyImageRequest"].alloc.return_value.init.return_value.results.return_value = []
        candidate = SimpleNamespace(confidence=lambda: 0.99, string=lambda: "Recovered text")
        box = SimpleNamespace(origin=SimpleNamespace(x=0.1, y=0.5), size=SimpleNamespace(width=0.5, height=0.1))
        requests[2].results.return_value = [SimpleNamespace(topCandidates_=lambda n: [candidate], boundingBox=lambda: box)]
        with patch.object(resolver, "vision", return_value=vn):
            lines, _, _ = resolver.run_vision("synthetic.jpg", 1000, 800)
        self.assertEqual([line["text"] for line in lines], ["Recovered text"])
        for args, _ in vn["VNImageRequestHandler"].alloc.return_value.initWithURL_options_.call_args_list:
            self.assertIsInstance(args[1], Foundation.NSDictionary)


if __name__ == "__main__":
    unittest.main()
