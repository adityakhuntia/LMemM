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
    def test_service_restart_clears_cached_result(self):
        c=Client();m=MemoryController(lambda:c,lambda:{},lambda:None);m.state['result']={'primary':[{'text':'old'}]}
        m.poll([{'type':'ready'}]);self.assertIsNone(m.state['result'])
    def test_late_agent_connection_stays_with_origin_project(self):
        c=Client();m=MemoryController(lambda:c,lambda:{},lambda:None)
        m.bindings=[dict(ui_project_id=p,project_id='p'+p,active=True,workspace_root='/'+p) for p in ('a','b')]
        m.select('a');m.action('connect_agent',{'approved':True});rid=c.calls[-1][2]
        m.select('b');m.poll([dict(type='response',id=rid,result=dict(grant_id='ga',project_ids=['pa'],config_path='/private/a'))])
        self.assertIsNone(m.agent);self.assertIsNone(m.state.get('preview'))
        m.action('revoke_agent');self.assertFalse(any(call[0]=='revoke_agent' for call in c.calls))
        m.select('a');m.action('revoke_agent');self.assertEqual(c.calls[-1][:2],('revoke_agent',{'grant_id':'ga'}))
    def test_restored_connections_allow_revoke_and_late_enrollment_keeps_both_bindings(self):
        c=Client();m=MemoryController(lambda:c,lambda:{},lambda:None)
        b=dict(ui_project_id='b',project_id='pb',active=True,workspace_root='/b')
        a=dict(ui_project_id='a',project_id='pa',active=True,workspace_root='/a')
        m.bindings=[b];m.select('a');m.action('enroll',{'root':'/a'});rid=c.calls[-1][2]
        m.select('b');m.poll([dict(type='response',id=rid,result=a)])
        self.assertEqual({b['ui_project_id'] for b in m.bindings},{'a','b'})
        m.send('agent_connections',{},'agents');rid=c.calls[-1][2]
        m.poll([dict(type='response',id=rid,result=[dict(grant_id='gb',client_id='Codex',project_ids=['pb'])])])
        m.action('revoke_agent');self.assertEqual(c.calls[-1][:2],('revoke_agent',{'grant_id':'gb'}))
