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


class InstallProgressTests(unittest.TestCase):
    def test_pull_output_becomes_a_percentage(self):
        import io
        from semantic_memory.model_setup import OwnedEmbeddingRuntime
        runtime = OwnedEmbeddingRuntime(tempfile.mkdtemp())
        runtime.progress = 0
        class Pull:
            stdout = io.BufferedReader(io.BytesIO(b"pulling manifest\rpulling 1b226e28...  12%\rpulling 1b226e28...  57% \x1b[K\r"))
        runtime._read_progress(Pull)
        self.assertEqual(runtime.progress, 57)

    def test_progress_never_reaches_100_until_the_pull_finishes(self):
        import io
        from semantic_memory.model_setup import OwnedEmbeddingRuntime
        runtime = OwnedEmbeddingRuntime(tempfile.mkdtemp())
        runtime.progress = 0
        class Pull:
            stdout = io.BufferedReader(io.BytesIO(b"pulling  100%\r"))
        runtime._read_progress(Pull)
        self.assertEqual(runtime.progress, 99)


class ControllerExtensionInstallTests(unittest.TestCase):
    def test_extension_install_runs_in_the_app_and_reports_success_or_the_reason(self):
        import threading
        from unittest import mock
        from memory_controller import MemoryController
        from semantic_memory import model_setup
        client = mock.Mock(directory=Path(tempfile.mkdtemp()) / "project-memory")
        controller = MemoryController(lambda: client, lambda: {}, lambda: None)
        def wait():
            for thread in threading.enumerate():
                if thread is not threading.current_thread() and thread.daemon:
                    thread.join(2)
        with mock.patch.object(model_setup, "install_extension", return_value={"installed": True}):
            controller.action("install_extension")
            wait()
        self.assertIn("Quit VS Code", controller.notice[0])
        self.assertFalse(controller.notice[1])
        with mock.patch.object(model_setup, "install_extension", side_effect=ValueError("VS Code was not found. Open VS Code…")):
            controller.action("install_extension")
            wait()
        self.assertTrue(controller.notice[1])
        self.assertIn("VS Code was not found", controller.notice[0])
        self.assertTrue(controller.poll([]))
        client.request.assert_not_called()


class VsCodeDiscoveryAndDownloadTests(unittest.TestCase):
    def test_vscode_is_found_through_spotlight_when_not_in_applications(self):
        from unittest import mock
        from semantic_memory import model_setup
        with tempfile.TemporaryDirectory() as d:
            cli = Path(d) / "Elsewhere" / "Visual Studio Code.app" / "Contents" / "Resources" / "app" / "bin" / "code"
            cli.parent.mkdir(parents=True);cli.write_text("#!/bin/sh\n")
            listing = mock.Mock(stdout=str(Path(d) / "Elsewhere" / "Visual Studio Code.app") + "\n")
            with mock.patch.object(model_setup.shutil, "which", return_value=None), \
                 mock.patch.object(model_setup.subprocess, "run", return_value=listing):
                self.assertEqual(model_setup._vscode_cli(), str(cli))

    def test_download_progress_counts_bytes_on_disk_not_file_size(self):
        from semantic_memory.model_setup import OwnedEmbeddingRuntime, DOWNLOAD_BYTES
        with tempfile.TemporaryDirectory() as d:
            runtime = OwnedEmbeddingRuntime(d);runtime.progress = 0
            blobs = runtime.weights / "blobs";blobs.mkdir(parents=True)
            sparse = blobs / "sha256-x-partial"
            with open(sparse, "wb") as handle:handle.truncate(DOWNLOAD_BYTES)   # pre-sized, nothing written yet
            runtime._measure_download()
            self.assertLess(runtime.progress, 5)
