"""Native host installation targets a controlled home and quotes executable paths."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from semantic_memory.browser_install import install_browser_host, EXTENSION_ID


class BrowserInstallTests(unittest.TestCase):
    def test_installed_manifest_has_exact_extension_and_executable_host(self):
        with tempfile.TemporaryDirectory(prefix='host home ') as tmp:
            root=Path(tmp);binary=root/'native worker'
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');binary.chmod(0o700)
            result=install_browser_host(root,root/'semantic',command=[str(binary),'--worker'])
            manifest=json.loads(Path(result['manifest']).read_text())
            self.assertEqual(manifest['allowed_origins'],['chrome-extension://'+EXTENSION_ID+'/'])
            launcher=Path(manifest['path']);self.assertTrue(os.access(launcher,os.X_OK))
            run=subprocess.run([str(launcher),'chrome-extension://'+EXTENSION_ID+'/'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0);self.assertEqual(run.stdout.splitlines()[0],'--worker')
            self.assertIn('--config',run.stdout)

    def test_symlink_private_host_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'Library/Application Support/LMemM'
            base.parent.mkdir(parents=True);other=root/'other';other.mkdir();base.symlink_to(other)
            with self.assertRaises(ValueError):install_browser_host(root,root/'semantic',command=['/bin/echo'])
