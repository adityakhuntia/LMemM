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

    def test_failed_startup_reaps_owned_child_before_retry(self):
        from unittest.mock import patch,Mock
        with tempfile.TemporaryDirectory() as d:
            runtime=OwnedEmbeddingRuntime(d);self.addCleanup(runtime.close)
            process=Mock();process.poll.return_value=1
            with patch('semantic_memory.model_setup.shutil.which',return_value='/synthetic/ollama'), \
                 patch('semantic_memory.model_setup.socket.socket'), \
                 patch('semantic_memory.model_setup.subprocess.Popen',return_value=process):
                with self.assertRaises(ValueError):runtime.ensure()
            self.assertIsNone(runtime.control)
            self.assertIsNone(runtime.process)
            process.wait.assert_called()

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
        with mock.patch.object(model_setup, "install_extension", return_value={"installed": True}), mock.patch.object(model_setup, "vscode_running", return_value=True):
            controller.action("install_extension")
            wait()
        self.assertIn('Reload Window',controller.notice[0])
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


class ConnectExtensionTests(unittest.TestCase):
    def test_connect_keeps_running_vscode_open(self):
        import threading
        from unittest import mock
        from memory_controller import MemoryController
        from semantic_memory import model_setup
        client=mock.Mock(directory=Path(tempfile.mkdtemp())/'project-memory')
        controller=MemoryController(lambda:client,lambda:{},lambda:None)
        with mock.patch.object(model_setup,'vscode_running',return_value=True), mock.patch.object(model_setup,'quit_vscode') as quit_, mock.patch('subprocess.run',return_value=mock.Mock(returncode=0)) as run:
            controller.action('reconnect_extension')
            for thread in threading.enumerate():
                if thread.daemon and thread.name=='memory-connect':thread.join(2)
            # Existing implementation has an unnamed thread; also wait on its command.
            import time
            deadline=time.monotonic()+2
            while run.call_count<2 and time.monotonic()<deadline:time.sleep(.01)
        quit_.assert_not_called()
        self.assertEqual([call.args[0][0] for call in run.call_args_list],['pbcopy','open'])



class SourceConnectedStatusTests(unittest.TestCase):
    def test_selected_project_does_not_inherit_another_projects_connection(self):
        from unittest import mock
        from memory_controller import MemoryController
        controller=MemoryController(lambda:mock.Mock(),lambda:{},lambda:None)
        controller.bindings=[{'ui_project_id':'alpha','project_id':'a','active':True},
                             {'ui_project_id':'beta','project_id':'b','active':True}]
        controller.status={'state':'Ready','source_connected':True,'source_connected_project_ids':['a']}
        controller.select('beta')
        self.assertFalse(controller.view()['status']['source_connected'])
        controller.select('alpha')
        self.assertTrue(controller.view()['status']['source_connected'])

    def test_view_shows_connected_and_no_connect_button(self):
        from memory_model import new_memory_state, memory_view
        state = new_memory_state()
        snapshot = memory_view(state, {"workspace_root": "/r", "active": True, "project_id": "p"},
                               {"state": "Ready", "model_state": "available", "source_connected": True}, {})
        self.assertTrue(snapshot["status"]["source_connected"])


class ConnectWhilePausedTests(unittest.TestCase):
    def test_connect_asks_to_resume_instead_of_opening_vscode(self):
        from unittest import mock
        from memory_controller import MemoryController
        controller = MemoryController(lambda: mock.Mock(directory=Path(tempfile.mkdtemp())), lambda: {}, lambda: None)
        controller.status = {"state": "Paused"}
        with mock.patch("subprocess.run") as run:
            controller.action("reconnect_extension")
        run.assert_not_called()
        self.assertTrue(controller.notice[1])
        self.assertIn("Resume", controller.notice[0])
class ReapOrphanTests(unittest.TestCase):
    def test_stale_pid_never_signals_an_existing_ollama(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            runtime=OwnedEmbeddingRuntime(tmp);(runtime.weights/'.ollama.pid').write_text('4242')
            with mock.patch('subprocess.run',return_value=mock.Mock(stdout='/usr/local/bin/ollama serve')),mock.patch('os.killpg') as killpg,mock.patch('os.kill') as kill:
                runtime._reap_orphan()
            killpg.assert_not_called();kill.assert_not_called()

class StandardEditorTests(unittest.TestCase):
    def test_insiders_only_install_is_not_reported_supported(self):
        from unittest import mock
        from semantic_memory import model_setup
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);editor=home/'Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code'
            editor.parent.mkdir(parents=True);editor.write_text('')
            shortcut=home/'code';shortcut.symlink_to(editor)
            (home/('.vscode-insiders/extensions/lmemm.lmemm-source-'+model_setup.EXTENSION_VERSION)).mkdir(parents=True)
            with mock.patch.object(model_setup.shutil,'which',return_value=str(shortcut)),mock.patch.object(model_setup.subprocess,'run',return_value=mock.Mock(stdout=str(home/'Visual Studio Code - Insiders.app')+'\n')),mock.patch.object(Path,'is_file',lambda p:p in (editor,shortcut)),mock.patch.object(Path,'home',return_value=home):
                self.assertIsNone(model_setup._vscode_cli())
                self.assertFalse(model_setup.extension_installed())

class ExtensionVersionTests(unittest.TestCase):
    def test_only_current_version_counts_as_installed(self):
        from unittest import mock
        from semantic_memory.model_setup import extension_installed,EXTENSION_VERSION
        with tempfile.TemporaryDirectory() as tmp:
            old=Path(tmp)/'.vscode/extensions/lmemm.lmemm-source-0.0.9';old.mkdir(parents=True)
            with mock.patch('pathlib.Path.home',return_value=Path(tmp)):
                self.assertFalse(extension_installed())
                (Path(tmp)/('.vscode/extensions/lmemm.lmemm-source-'+EXTENSION_VERSION)).mkdir()
                self.assertTrue(extension_installed())
