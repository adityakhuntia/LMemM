import unittest
from memory_controller import MemoryController
class Client:
    def __init__(self):self.calls=[];self.events=[]
    def request(self,*args):self.calls.append(args)
    def poll(self):e,self.events=self.events,[];return e
class ControllerTests(unittest.TestCase):
    def test_submit_only_and_response_project_fence(self):
        c=Client();m=MemoryController(lambda:c,lambda:{},lambda:None)
        m.bindings=[dict(ui_project_id='a',project_id='pa',active=True,workspace_root='/a')]
        m.select('a');m.action('query',{'text':'rollback'})
        self.assertFalse(any(call[0]=='search_project_memory' for call in c.calls))
        m.action('submit',{});call=c.calls[-1]
        self.assertEqual(call[0],'search_project_memory');self.assertEqual(call[1]['project_id'],'pa')
        m.select('b');c.events=[dict(type='response',id=call[2],result={'primary':[{'text':'a'}]})];m.poll()
        self.assertIsNone(m.state['result'])
    def test_source_open_requires_fresh_resolution(self):
        c=Client();m=MemoryController(lambda:c,lambda:{},lambda:None)
        m.bindings=[dict(ui_project_id='a',project_id='pa',active=True,workspace_root='/a')];m.select('a')
        m.action('source',{'citation_id':'cite'})
        self.assertEqual(c.calls[-1][:2],('resolve_citation',{'project_id':'pa','citation_id':'cite'}))
