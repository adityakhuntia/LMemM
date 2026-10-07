import unittest
from semantic_helpers import SemanticFixture, source, policy
import json
from semantic_memory.episodes import build_request
from semantic_memory.contracts import TextSpan, Correction
from semantic_memory.inference import validate_extraction
from semantic_memory.relationships import apply_extraction, apply_correction

class RelationshipTests(SemanticFixture, unittest.TestCase):
    def test_workspace_and_explicit_note_supported(self):
        self.db.ingest(source(origin_type='user_note',spans=(TextSpan('span1','We decided to use SQLite because it stays local.'),)),policy())
        self.builder.accept('s1'); eid=self.builder.boundary('stop','2026-10-07T10:00:01+00:00')[0]
        req=build_request(self.db,eid); e=req.evidence[0]
        payload={'candidates':[{'type':'decision','subject_id':e['artifact_id'],'statement':e['text'],
                  'evidence_ids':[e['id']],'extraction_status':'explicit','reason':'it stays local'}]}
        apply_extraction(self.db,eid,validate_extraction(json.dumps(payload),req))
        claim=self.db.connection.execute('SELECT * FROM claims').fetchone()
        self.assertEqual(claim['status'],'supported')
        self.assertEqual(claim['reason'],'it stays local')
        self.assertTrue(self.db.connection.execute("SELECT 1 FROM edges WHERE kind='belongs_to' AND status='supported'").fetchone())

    def test_observed_ai_is_not_user_decision(self):
        req=self.request(); e=req.evidence[0]
        payload={'candidates':[{'type':'decision','subject_id':e['artifact_id'],'statement':'We chose a hosted database',
                               'evidence_ids':[e['id']],'extraction_status':'explicit'}]}
        apply_extraction(self.db,req.episode_id,validate_extraction(json.dumps(payload),req))
        self.assertEqual(self.db.connection.execute('SELECT status FROM claims').fetchone()[0],'inferred')

    def test_browser_link_requires_actual_project_reference(self):
        anchored=self.db.ingest(source(),policy())
        self.db.ingest(source('web',app_id='com.apple.Safari',artifact_locator='https://docs.example.org/sqlite',
                      workspace_locator=None,spans=(TextSpan('web','General SQLite reference.'),)),policy())
        self.builder.accept('web'); eid=self.builder.boundary('stop','2026-10-07T10:00:01+00:00')[0]
        req=build_request(self.db,eid); e=req.evidence[0]
        payload={'candidates':[{'type':'belongs_to','subject_id':e['artifact_id'],'object_id':anchored.project_id,
                  'statement':'Related to project one','evidence_ids':[e['id']],'extraction_status':'observed'}]}
        result=validate_extraction(json.dumps(payload),req)
        apply_extraction(self.db,eid,result)
        self.assertEqual(self.db.connection.execute("SELECT status FROM edges WHERE subject_id=?",(e['artifact_id'],)).fetchone()[0],'inferred')
        apply_correction(self.db,Correction('reject',e['artifact_id'],anchored.project_id,'2026-10-07T10:01:00+00:00'))
        apply_extraction(self.db,eid,result)
        self.assertFalse(self.db.connection.execute('SELECT 1 FROM edges WHERE subject_id=?',(e['artifact_id'],)).fetchone())
