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
        self.base = Path(self.temp.name).resolve()
        self.roots = [self.base / 'one', self.base / 'two']
        for root in self.roots:
            root.mkdir(); (root / 'a.py').write_text('hello')
        self.now = 1000.0
        self.bridge = Bridge(self.base / 'bridge', self.roots, lambda: self.now)
        self.grant = self.bridge.open_session()
        self.focus = Focus(1, 10, (0, 0, 800, 600),title='LMemM '+'a'*32)
        self.seq = 0
    def tearDown(self): self.temp.cleanup()
    def msg(self, kind='connect', client='a'*32, root=0, **extra):
        self.seq += 1
        return dict(revision=self.bridge.revision,token=self.grant['token'], session=self.grant['session'], client=client,
                    seq=self.seq, at=self.now, kind=kind, focused=True, window=10,
                    workspace=self.roots[root].as_uri(), document=(self.roots[root]/'a.py').as_uri(),
                    spans=[dict(text='hello', truncated=False)], **extra)
    def connect(self, **kw):
        m=self.msg(**kw); m.pop('spans');
        from dataclasses import replace
        self.bridge.accept(m, replace(self.focus,title='LMemM '+m['client']))
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
        m=self.msg('snapshot')
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

class NativeFocusTests(unittest.TestCase):
 def test_native_errors_deny(self):
  from unittest.mock import patch
  from semantic_memory.live_focus import focused_context
  with patch('input_monitor.secure_input_enabled',return_value=None):self.assertIsNone(focused_context())
 def test_nonfinite_clock_deny(self):
  case=BridgeTests();case.setUp()
  try:
   case.connect();m=case.msg('snapshot');m['at']=float('nan')
   self.assertIsNone(case.bridge.accept(m,case.focus))
  finally:case.tearDown()

class NativeSecureElementTests(unittest.TestCase):
 def test_secure_focused_element_denies_even_without_carbon_flag(self):
  from types import SimpleNamespace as NS
  from unittest.mock import patch
  from semantic_memory.live_focus import focused_context
  app=NS(bundleIdentifier=lambda:'com.microsoft.VSCode',processIdentifier=lambda:1)
  def attribute(element,name,ignored):
   return 0,{'AXFocusedWindow':'window','AXPosition':'position','AXSize':'size','AXFocusedUIElement':'element','AXRole':'AXTextField','AXSubrole':'AXSecureTextField'}[name]
  ax=NS(AXUIElementCreateApplication=lambda pid:'app',AXUIElementCreateSystemWide=lambda:'system',AXUIElementCopyAttributeValue=attribute,AXUIElementGetPid=lambda e,x:(0,1),AXValueGetValue=lambda value,kind,x:(True,NS(x=0,y=0) if value=='position' else NS(width=800,height=600)),kAXValueCGPointType=1,kAXValueCGSizeType=2)
  quartz=NS(kCGWindowListOptionOnScreenOnly=1,CGWindowListCopyWindowInfo=lambda x,y:[{'kCGWindowLayer':0,'kCGWindowOwnerPID':1,'kCGWindowNumber':10,'kCGWindowBounds':dict(X=0,Y=0,Width=800,Height=600)}])
  kit=NS(NSWorkspace=NS(sharedWorkspace=lambda:NS(frontmostApplication=lambda:app)))
  with patch.dict('sys.modules',{'AppKit':kit,'Quartz':quartz,'ApplicationServices':ax}),patch('input_monitor.secure_input_enabled',return_value=False):
   self.assertIsNone(focused_context())

class ReviewedBridgeTests(unittest.TestCase):
 setUp=BridgeTests.setUp
 tearDown=BridgeTests.tearDown
 msg=BridgeTests.msg
 connect=BridgeTests.connect
 def test_excluded_lexical_symlink(self):
  self.connect();alias=self.roots[0]/'.env';alias.symlink_to(self.roots[0]/'a.py')
  m=self.msg('snapshot');m['document']=alias.as_uri()
  self.assertIsNone(self.bridge.accept(m,self.focus))
 def test_connect_requires_native_challenge_and_no_rebind(self):
  m=self.msg();m.pop('spans');self.bridge.accept(m,Focus(1,20,(0,0,800,600)))
  self.assertNotIn('a'*32,self.bridge.clients)
  self.connect();m=self.msg();m.pop('spans');self.bridge.accept(m,Focus(1,20,(0,0,800,600),title='LMemM '+'a'*32))
  self.assertEqual(self.bridge.clients['a'*32]['window'],10)

class EpochTests(unittest.TestCase):
 setUp=BridgeTests.setUp
 tearDown=BridgeTests.tearDown
 msg=BridgeTests.msg
 connect=BridgeTests.connect
 def test_old_generation_denied(self):
  self.connect();m=self.msg('snapshot');m['revision']=self.bridge.revision
  self.bridge.revision+=1
  self.assertIsNone(self.bridge.accept(m,self.focus))
 def test_expiry_removes_client_and_ack(self):
  self.connect();self.now+=3
  self.assertEqual(self.bridge.expire(),['a'*32]);self.assertFalse(self.bridge.clients)

class UnicodeIngressTests(unittest.TestCase):
 setUp=BridgeTests.setUp
 tearDown=BridgeTests.tearDown
 msg=BridgeTests.msg
 connect=BridgeTests.connect
 def test_valid_utf8_envelope_not_charged_as_ascii_escape_expansion(self):
  self.connect();m=self.msg('snapshot');m['spans']=[dict(text='😀'*1024,truncated=False) for i in range(4)]
  self.assertLess(len(json.dumps(m,ensure_ascii=False).encode()),32768)
  self.assertIsNotNone(self.bridge.accept(m,self.focus))

class AppFocusFallbackTests(unittest.TestCase):
 def test_app_focus_fallback_keeps_owner_and_secure_checks(self):
  from types import SimpleNamespace as NS
  from unittest.mock import patch
  from semantic_memory.live_focus import focused_context
  app=NS(bundleIdentifier=lambda:'com.microsoft.VSCode',processIdentifier=lambda:1)
  state={'owner':1,'role':'AXGroup','subrole':None}
  def attribute(element,name,ignored):
   if element=='system':return -25204,None
   if name=='AXRole':return 0,state['role']
   if name=='AXSubrole':return -25212,state['subrole']
   return 0,{'AXFocusedWindow':'window','AXPosition':'position','AXSize':'size','AXFocusedUIElement':'element','AXTitle':'LMemM test'}[name]
  ax=NS(AXUIElementCreateApplication=lambda pid:'app',AXUIElementCreateSystemWide=lambda:'system',AXUIElementCopyAttributeValue=attribute,AXUIElementGetPid=lambda e,x:(0,state['owner']),AXValueGetValue=lambda value,kind,x:(True,NS(x=0,y=0) if value=='position' else NS(width=800,height=600)),kAXValueCGPointType=1,kAXValueCGSizeType=2)
  quartz=NS(kCGWindowListOptionOnScreenOnly=1,CGWindowListCopyWindowInfo=lambda x,y:[{'kCGWindowLayer':0,'kCGWindowOwnerPID':1,'kCGWindowNumber':10,'kCGWindowBounds':dict(X=0,Y=0,Width=800,Height=600)}])
  kit=NS(NSWorkspace=NS(sharedWorkspace=lambda:NS(frontmostApplication=lambda:app)))
  with patch.dict('sys.modules',{'AppKit':kit,'Quartz':quartz,'ApplicationServices':ax}),patch('input_monitor.secure_input_enabled',return_value=False):
   self.assertIsNotNone(focused_context())
   state['owner']=2;self.assertIsNone(focused_context())
   state.update(owner=1,role='AXTextField',subrole='AXSecureTextField');self.assertIsNone(focused_context())

class LeaseHeartbeatTests(unittest.TestCase):
 setUp=BridgeTests.setUp
 tearDown=BridgeTests.tearDown
 msg=BridgeTests.msg
 connect=BridgeTests.connect
 def test_registered_publisher_metadata_survives_denied_native_focus(self):
  from semantic_memory.live_bridge import write_private_json
  self.connect();self.now+=1.5;m=self.msg('heartbeat')
  write_private_json(self.bridge.directory/'events'/('a'*32+'.json'),m)
  self.bridge.accept(m,None);self.now+=1
  self.assertEqual(self.bridge.expire(),[])
  self.assertFalse(self.bridge.clients['a'*32]['focused'])

class DisconnectLeaseTests(unittest.TestCase):
 setUp=BridgeTests.setUp
 tearDown=BridgeTests.tearDown
 msg=BridgeTests.msg
 connect=BridgeTests.connect
 def test_explicit_disconnect_expires_immediately(self):
  from semantic_memory.live_bridge import write_private_json
  self.connect();message=self.msg('disconnect')
  write_private_json(self.bridge.directory/'events'/('a'*32+'.json'),message)
  self.bridge.accept(message,None)
  self.assertEqual(self.bridge.expire(),['a'*32])
