import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class RuntimeEnvironmentTests(unittest.TestCase):
    def test_alias_app_children_use_the_virtual_environment(self):
        from semantic_memory.runtime_environment import python_executable
        with patch.object(sys,'frozen','macosx_app',create=True),patch.object(sys,'executable','/app/Contents/MacOS/python'):
            self.assertEqual(python_executable(),str(Path(__file__).resolve().parents[1]/'.venv/bin/python'))

    def test_app_restart_uses_native_launcher_not_bundled_python(self):
        from semantic_memory.runtime_environment import launch_argv
        with tempfile.TemporaryDirectory() as d:
            native=Path(d)/'LMemM';native.touch()
            with patch.object(sys,'frozen','macosx_app',create=True),patch.dict(os.environ,{'EXECUTABLEPATH':str(native)}):
                self.assertEqual(launch_argv(['setup','--again']),[str(native),'setup','--again'])
