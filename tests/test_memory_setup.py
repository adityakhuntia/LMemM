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

    def test_failed_spawn_closes_control_pipe_for_retry(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            runtime=OwnedEmbeddingRuntime(d)
            self.addCleanup(runtime.close)
            with patch('semantic_memory.model_setup.shutil.which',return_value='/synthetic/ollama'), \
                 patch('semantic_memory.model_setup.socket.socket'), \
                 patch('semantic_memory.model_setup.subprocess.Popen',side_effect=OSError('Cannot execute')):
                with self.assertRaises(OSError):runtime.ensure()
            self.assertIsNone(runtime.control)
