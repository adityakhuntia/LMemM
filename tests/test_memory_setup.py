import tempfile,unittest,zipfile
from pathlib import Path
from semantic_memory.model_setup import OwnedEmbeddingRuntime,SELECTED_DIGEST,build_extension
class SetupTests(unittest.TestCase):
    def test_extension_install_artifact_contains_executable_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            path=build_extension(Path(d)/'source.vsix')
            with zipfile.ZipFile(path) as archive:
                self.assertIn('extension/extension.js',archive.namelist())
                self.assertIn('extension.vsixmanifest',archive.namelist())
                self.assertIn('[Content_Types].xml',archive.namelist())
    def test_runtime_start_is_explicit_and_manifest_is_pinned(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=OwnedEmbeddingRuntime(Path(d))
            self.assertIsNone(runtime.process)
            self.assertEqual(runtime.manifest().digest,SELECTED_DIGEST)
            runtime.close()


class ExtensionInstallMessagesTests(unittest.TestCase):
    def test_missing_vscode_says_how_to_install_by_hand(self):
        from unittest import mock
        from semantic_memory import model_setup
        with tempfile.TemporaryDirectory() as d, mock.patch.object(model_setup,'_vscode_cli',return_value=None):
            with self.assertRaises(ValueError) as caught:model_setup.install_extension(d)
        self.assertIn('Install from VSIX',str(caught.exception))
        self.assertIn('lmemm-source.vsix',str(caught.exception))

    def test_cli_failure_reports_its_own_message(self):
        from unittest import mock
        from semantic_memory import model_setup
        failed=mock.Mock(returncode=1,stderr='bad extension\n',stdout='')
        with tempfile.TemporaryDirectory() as d, mock.patch.object(model_setup,'_vscode_cli',return_value='/bin/echo'), mock.patch.object(model_setup.subprocess,'run',return_value=failed):
            with self.assertRaises(ValueError) as caught:model_setup.install_extension(d)
        self.assertIn('bad extension',str(caught.exception))
