"""Exercise the native local-only request gate without a microphone or permissions."""

import subprocess
import tempfile
import unittest
from pathlib import Path


class SpeechPolicyTests(unittest.TestCase):
    def test_native_policy_refuses_unsupported_recognizer_and_requires_local_when_supported(self):
        source = Path(__file__).resolve().parents[1] / "native" / "listen" / "listen.m"
        harness = '''
#define main listener_main
#include "LISTENER_SOURCE"
#undef main
@interface FakeRecognizer : NSObject
@property BOOL supportsOnDeviceRecognition;
@end
@implementation FakeRecognizer
@end
@interface FakeRequest : NSObject
@property BOOL requiresOnDeviceRecognition;
@end
@implementation FakeRequest
@end
int main(void) {
    @autoreleasepool {
        FakeRecognizer *rec = [FakeRecognizer new];
        FakeRequest *req = [FakeRequest new];
        if (configureLocalRecognition((id)rec, (id)req)) return 1;
        if (req.requiresOnDeviceRecognition) return 2;
        rec.supportsOnDeviceRecognition = YES;
        if (!configureLocalRecognition((id)rec, (id)req)) return 3;
        if (!req.requiresOnDeviceRecognition) return 4;
    }
    return 0;
}
'''.replace("LISTENER_SOURCE", str(source))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy.m").write_text(harness)
            built = subprocess.run(["clang", "-fobjc-arc", "-framework", "Foundation",
                                    "-framework", "Speech", "-framework", "AVFoundation",
                                    str(root / "policy.m"), "-o", str(root / "policy")],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(root / "policy")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
