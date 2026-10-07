import json
import os
import tempfile
import unittest
from pathlib import Path
from semantic_memory.live_bridge import Bridge, read_private_json
from semantic_memory.live_focus import Focus, match_window

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.roots = [self.base / 'one', self.base / 'two']
        for root in self.roots:
            root.mkdir(); (root / 'a.py').write_text('hello')
        self.now = 1000.0
        self.bridge = Bridge(self.base / 'bridge', self.roots, lambda: self.now)
        self.grant = self.bridge.open_session()
        self.focus = Focus(1, 10, (0, 0, 800, 600))
        self.seq = 0
    def tearDown(self): self.temp.cleanup()
    def msg(self, kind='connect', client='a'*32, root=0, **extra):
        self.seq += 1
        return dict(token=self.grant['token'], session=self.grant['session'], client=client,
                    seq=self.seq, at=self.now, kind=kind, focused=True, window=10,
                    workspace=self.roots[root].as_uri(), document=(self.roots[root]/'a.py').as_uri(),
                    spans=[dict(text='hello', truncated=False)], **extra)
    def connect(self, **kw):
        m=self.msg(**kw); m.pop('spans'); self.bridge.accept(m, self.focus)
    def test_projects_and_dedup(self):
        self.connect()
        e=self.bridge.accept(self.msg('snapshot'),self.focus)
        self.assertEqual(e.workspace_locator,str(self.roots[0].resolve()))
        self.assertIsNone(self.bridge.accept(self.msg('snapshot'),self.focus))
        e=self.bridge.accept(self.msg('snapshot',root=1),self.focus)
        self.assertEqual(e.workspace_locator,str(self.roots[1].resolve()))
    def test_stale_replay_token_window_and_unknown(self):
        self.connect()
        m=self.msg('snapshot'); m['at']-=3
        self.assertIsNone(self.bridge.accept(m,self.focus))
        m=self.msg('snapshot'); m['token']='bad'
        self.assertIsNone(self.bridge.accept(m,self.focus))
        m=self.msg('snapshot'); m['window']=11
        self.assertIsNone(self.bridge.accept(m,self.focus))
        m=self.msg('snapshot')
        self.assertIsNone(self.bridge.accept(m,None))
        self.assertIsNotNone(self.bridge.accept(m,self.focus))
        self.assertIsNone(self.bridge.accept(m,self.focus))
    def test_ambiguous_clients(self):
        self.connect(); self.connect(client='b'*32)
        self.assertIsNone(self.bridge.accept(self.msg('snapshot'),self.focus))
    def test_paths(self):
        self.connect()
        outside=self.base/'secret'; outside.write_text('secret')
        (self.roots[0]/'escape').symlink_to(outside)
        (self.roots[0]/'.env').write_text('secret')
        for uri in ['vscode-remote://host/a', outside.as_uri(), (self.roots[0]/'escape').as_uri(), (self.roots[0]/'.env').as_uri()]:
            m=self.msg('snapshot'); m['document']=uri
            self.assertIsNone(self.bridge.accept(m,self.focus),uri)
        child=self.roots[0]/'child'; child.mkdir(); (child/'a.py').write_text('x')
        m=self.msg('snapshot'); m.update(workspace=child.as_uri(),document=(child/'a.py').as_uri())
        self.assertIsNone(self.bridge.accept(m,self.focus))
    def test_private_file_and_bounds(self):
        path=self.base/'message.json'; path.write_text('{}'); path.chmod(0o600)
        self.assertEqual(read_private_json(path),{})
        path.chmod(0o644)
        with self.assertRaises(ValueError): read_private_json(path)
        path.chmod(0o600); path.write_text('x'*32769)
        with self.assertRaises(ValueError): read_private_json(path)
        link=self.base/'link'; link.symlink_to(path)
        with self.assertRaises((ValueError,OSError)): read_private_json(link)
        self.assertEqual((self.base/'bridge').stat().st_mode & 0o777,0o700)
    def test_oversize_source(self):
        self.connect(); m=self.msg('snapshot'); m['spans'][0]['text']='x'*4097
        self.assertIsNone(self.bridge.accept(m,self.focus))
    def test_geometry(self):
        rows=[dict(pid=1,window=10,bounds=(0,0,800,600)),dict(pid=2,window=11,bounds=(0,0,800,600))]
        self.assertEqual(match_window(1,(0,0,800,600),rows),self.focus)
        self.assertIsNone(match_window(1,(0,0,800,600),rows+rows[:1]))
        self.assertIsNone(match_window(1,None,rows))
