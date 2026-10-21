"""Browser capabilities are ingestion-only, revocable and ownership-bound."""
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from semantic_memory.service import MemoryService
from semantic_memory.browser_host import read_message, write_message, forward
from semantic_memory.browser_pairing import pair_browser, revoke_browser
from semantic_memory.live_bridge import read_private_json


class BrowserHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=MemoryService(Path(self.tmp.name)/'semantic',focus_provider=lambda:None)
        self.addCleanup(self.service.close)
        self.binding=self.service.enroll('research')
        self.project=self.binding['project_id'];self.extension='a'*32
        pair_browser(self.service,self.extension)
        self.config=read_private_json(self.service.directory/'browser-host.json')

    def call(self,method,params=None,key='request'):
        return self.service.serve_request(self.config['capability'],'browser_request',
            {'request':dict(version=1,request_id=key,method=method,params=params or {})})

    def payload(self):
        return dict(project_id=self.project,payload=dict(request_id='save-one',kind='browser_selection',
            text='SQLite stays local.',title='Research',url='https://example.org/database'))

    def test_browser_cannot_read_context_or_call_owner_methods(self):
        for method in ('bindings','resume','enroll','get_project_context'):
            with self.subTest(method=method),self.assertRaises(ValueError):
                self.service.serve_request(self.config['capability'],method,{'project_id':self.project})
        projects=self.call('list_projects')['projects']
        self.assertEqual(projects[0]['project_id'],self.project)

    def test_save_ack_is_durable_and_move_undo_are_owned(self):
        saved=self.call('save',self.payload());sid=saved['source_id']
        self.assertEqual(self.call('save',self.payload())['source_id'],sid)
        self.assertEqual(self.service.store.count('sources'),1)
        other=self.service.enroll('other')['project_id']
        self.assertEqual(self.call('move',dict(source_id=sid,project_id=other))['project_id'],other)
        self.call('undo',dict(source_id=sid))
        self.assertEqual(self.service.store.count('sources'),0)
        with self.assertRaises(ValueError):self.call('save',self.payload())

    def test_pause_lock_revoke_and_project_disable_refuse_saves(self):
        self.service.pause()
        with self.assertRaises(ValueError):self.call('save',self.payload())
        self.service.resume();self.service.system_flags.add('locked')
        with self.assertRaises(ValueError):self.call('save',self.payload())
        self.service.system_flags.clear();self.service.revoke_project(self.project)
        with self.assertRaises(ValueError):self.call('save',self.payload())
        revoke_browser(self.service)
        with self.assertRaises(ValueError):self.call('status')

    def test_repair_does_not_give_new_connector_old_save_authority(self):
        sid=self.call('save',self.payload())['source_id']
        pair_browser(self.service,self.extension)
        self.config=read_private_json(self.service.directory/'browser-host.json')
        with self.assertRaises(ValueError):self.call('undo',dict(source_id=sid))
        self.assertEqual(self.service.store.count('sources'),1)

    def test_frames_are_bounded_and_keep_native_byte_order(self):
        frame=io.BytesIO();write_message(frame,{'version':1,'text':'café'})
        frame.seek(0);self.assertEqual(read_message(frame)['text'],'café')
        for data in (b'\x01',struct.pack('=I',1048577),struct.pack('=I',2)+b'[]'):
            with self.subTest(data=data),self.assertRaises(ValueError):read_message(io.BytesIO(data))

    def test_host_checks_extension_origin_before_using_capability(self):
        with self.assertRaises(ValueError):forward(self.service.directory/'browser-host.json','chrome-extension://'+'b'*32+'/',{})

    def test_protocol_rejects_unknown_methods_and_bad_version(self):
        with self.assertRaises(ValueError):self.call('get_project_context')
        with self.assertRaises(ValueError):self.service.serve_request(self.config['capability'],'browser_request',{'request':dict(version=True,request_id='one',method='status',params={})})
