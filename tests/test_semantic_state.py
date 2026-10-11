import json
import unittest
from semantic_helpers import SemanticFixture,source,policy
from semantic_memory.contracts import TextSpan,SourceScope
from semantic_memory.episodes import build_request
from semantic_memory.inference import validate_extraction
from semantic_memory.relationships import apply_extraction
from semantic_memory.retrieval import project_context

class StateTests(SemanticFixture,unittest.TestCase):
    def extract(self,sid,text,at,kind='task',object_id=None,state='open'):
        self.db.ingest(source(sid,at=at,origin_type='user_note',spans=(TextSpan('x',text),)),policy())
        self.builder.accept(sid);eid=self.builder.boundary('stop',at)[0];req=build_request(self.db,eid);e=req.evidence[0]
        candidate={'type':kind,'subject_id':e['artifact_id'],'object_id':object_id,'statement':text,'evidence_ids':[e['id']],'extraction_status':'explicit'}
        if kind=='task':candidate['task_state']=state
        apply_extraction(self.db,eid,validate_extraction(json.dumps({'candidates':[candidate]}),req))
        return self.db.connection.execute('SELECT id FROM claims WHERE statement=?',(text,)).fetchone()[0]

    def test_source_backed_task_done_and_reopen_as_of_interval(self):
        task=self.extract('first','Next task: add the rollback test.','2026-10-07T10:00:00+00:00')
        self.extract('done','Completed task: add the rollback test.','2026-10-07T11:00:00+00:00',object_id=task,state='completed')
        self.extract('reopen','Reopen task: add the rollback test.','2026-10-07T12:00:00+00:00',object_id=task,state='reopened')
        pid=self.db.connection.execute('SELECT id FROM projects').fetchone()[0]
        scope=SourceScope(frozenset({'com.microsoft.VSCode'}))
        done=project_context(self.db,pid,'2026-10-07T00:00:00+00:00','2026-10-07T11:30:00+00:00',scope)
        reopened=project_context(self.db,pid,done.start,'2026-10-07T12:30:00+00:00',scope)
        self.assertFalse(done.open_tasks)
        self.assertEqual(len(reopened.open_tasks),1)

    def test_validated_conflict_is_visible_without_overwriting(self):
        old=self.extract('old','We decided to use SQLite.','2026-10-07T10:00:00+00:00',kind='decision')
        new=self.extract('new','We decided to use PostgreSQL.','2026-10-07T11:00:00+00:00',kind='decision')
        eid=self.db.connection.execute('SELECT episode_id FROM claims WHERE id=?',(new,)).fetchone()[0]
        req=build_request(self.db,eid);candidate={'type':'contradicts','subject_id':new,'object_id':old,'statement':'Different database choices.',
            'evidence_ids':[e['id'] for e in req.evidence],'extraction_status':'inferred'}
        apply_extraction(self.db,eid,validate_extraction(json.dumps({'candidates':[candidate]}),req))
        pid=self.db.connection.execute('SELECT id FROM projects').fetchone()[0]
        packet=project_context(self.db,pid,'2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00',SourceScope(frozenset({'com.microsoft.VSCode'})))
        self.assertTrue(packet.conflicts)
        self.assertEqual(len(packet.decisions),2)
