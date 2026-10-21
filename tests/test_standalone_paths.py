"""Installed workers and data imports must not depend on a developer checkout."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from semantic_memory.runtime_environment import worker_argv, standalone_resources
from semantic_memory.data_import import import_legacy_data


class StandalonePathTests(unittest.TestCase):
    def test_dock_launch_can_find_installed_ollama_without_shell_path(self):
        from semantic_memory.model_setup import ollama_binary
        with patch('semantic_memory.model_setup.shutil.which',return_value=None),patch('semantic_memory.model_setup.os.access',return_value=True),patch.object(Path,'is_file',lambda p:str(p)=='/Applications/Ollama.app/Contents/Resources/ollama'):
            self.assertEqual(ollama_binary(),'/Applications/Ollama.app/Contents/Resources/ollama')
    def test_installed_voice_helper_never_compiles_inside_signed_app(self):
        import dictation
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);helper=root/'bin/LMemM Listen.app/Contents/MacOS/listen'
            helper.parent.mkdir(parents=True);helper.touch();helper.chmod(0o700)
            with patch.object(dictation,'HERE',str(root)),patch.object(dictation,'LISTEN_APP',str(helper.parents[2])),patch('semantic_memory.runtime_environment.standalone_resources',return_value=root):
                self.assertTrue(dictation.ensure_listener())

    def test_frozen_workers_use_app_entry_and_not_venv_or_path_python(self):
        with tempfile.TemporaryDirectory(prefix='Installed App ') as tmp:
            resources=Path(tmp)/'LMemM.app/Contents/Resources';resources.mkdir(parents=True)
            (resources/'standalone.json').write_text('{"version":1}')
            native=resources.parent/'MacOS/LMemM';native.parent.mkdir();native.touch()
            with patch.object(sys,'frozen','macosx_app',create=True),patch.dict(os.environ,{'RESOURCEPATH':str(resources),'EXECUTABLEPATH':str(native)}):
                self.assertEqual(standalone_resources(),resources)
                self.assertEqual(worker_argv('memory-service',['--headless']),[str(native),'--lmemm-worker','memory-service','--headless'])

    def test_import_is_explicit_atomic_and_keeps_original_and_citation_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'legacy';source.mkdir();(source/'memory').mkdir()
            (source/'memory/memory.json').write_text('{"items":[]}')
            (source/'semantic').mkdir();(source/'semantic/memory.sqlite').write_bytes(b'citation-fixture')
            target=root/'installed/data'
            result=import_legacy_data(source,target)
            self.assertEqual((target/'semantic/memory.sqlite').read_bytes(),b'citation-fixture')
            self.assertEqual((source/'semantic/memory.sqlite').read_bytes(),b'citation-fixture')
            self.assertTrue(Path(result['backup']).is_dir())
            with self.assertRaises(ValueError):import_legacy_data(source,target)

    def test_symlink_or_interrupted_copy_cannot_replace_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'legacy';source.mkdir();(source/'memory').mkdir()
            (source/'memory/memory.json').write_text('{"items":[]}')
            target=root/'installed/data'
            (source/'escape').symlink_to('/private')
            with self.assertRaises(ValueError):import_legacy_data(source,target)
            self.assertFalse(target.exists());(source/'escape').unlink()
            with patch('semantic_memory.data_import.shutil.copytree',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):import_legacy_data(source,target)
            self.assertFalse(target.exists())
