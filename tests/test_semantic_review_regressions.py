import unittest
from semantic_helpers import SemanticFixture, source, policy
import json
from semantic_memory.contracts import TextSpan,SourceScope
from semantic_memory.episodes import build_request
from semantic_memory.inference import validate_extraction
from semantic_memory.relationships import apply_extraction
from semantic_memory.retention import delete_sources,enforce_budget,semantic_bytes
from semantic_memory.retrieval import project_context,render_context

class ReviewRegressions(SemanticFixture, unittest.TestCase):
    def test_unrelated_decision_never_supported(self):
        self.db.ingest(source(origin_type='user_note',spans=(TextSpan('x','We decided to use SQLite.'),)),policy())
        self.builder.accept('s1');eid=self.builder.boundary('stop','2026-10-07T10:00:01+00:00')[0]
        req=build_request(self.db,eid);e=req.evidence[0]
        candidate={'type':'decision','subject_id':e['artifact_id'],'statement':'We decided to export all private content.',
                   'evidence_ids':[e['id']],'extraction_status':'explicit'}
        apply_extraction(self.db,eid,validate_extraction(json.dumps({'candidates':[candidate]}),req))
        self.assertEqual(self.db.connection.execute('SELECT status FROM claims').fetchone()[0],'inferred')

    def test_deleted_support_does_not_leak_reason(self):
        self.db.ingest(source('secret',origin_type='user_note',spans=(TextSpan('x','We decided to use SQLite because secret-value.'),)),policy())
        self.builder.accept('secret')
        self.db.ingest(source('public',spans=(TextSpan('x','Public context about SQLite.'),)),policy())
        self.builder.accept('public');eid=self.builder.boundary('stop','2026-10-07T10:00:01+00:00')[0]
        req=build_request(self.db,eid);e=req.evidence[0]
        candidate={'type':'decision','subject_id':e['artifact_id'],'statement':e['text'],'reason':'secret-value',
                   'evidence_ids':[v['id'] for v in req.evidence],'extraction_status':'explicit'}
        apply_extraction(self.db,eid,validate_extraction(json.dumps({'candidates':[candidate]}),req))
        delete_sources(self.db,{'secret'})
        packet=project_context(self.db,e['project_id'],'2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00',SourceScope(frozenset({'com.microsoft.VSCode'})))
        self.assertNotIn('secret-value',render_context(packet))

    def test_small_budget_pressure_does_not_prune_every_source(self):
        for i in range(30):
            self.db.ingest(source(str(i),spans=(TextSpan('x',str(i)+'a'*4000),)),policy())
        before=semantic_bytes(self.db)
        status=enforce_budget(self.db,'2026-10-07T10:01:00+00:00',semantic_limit=before-4096)
        self.assertLess(status.pruned,30)
        self.assertGreater(self.db.count('sources'),0)

    def test_artifact_membership_requires_scoped_support(self):
        anchor=self.db.ingest(source('anchor'),policy())
        url='https://docs.example.org/shared'
        a=self.db.ingest(source('editor',artifact_locator=url,workspace_locator=None,spans=(TextSpan('x','Related to /projects/one'),)),policy())
        b=self.db.ingest(source('browser',app_id='com.apple.Safari',artifact_locator=url,workspace_locator=None,spans=(TextSpan('x','Generic browser text'),)),policy())
        from semantic_memory.relationships import _edge
        with self.db.transaction() as c:
            _edge(c,a.artifact_id,anchor.project_id,'belongs_to','supported','2026-10-07T10:00:00+00:00',a.occurrence_ids,None,'explicit_reference')
        packet=project_context(self.db,anchor.project_id,'2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00',SourceScope(frozenset({'com.apple.Safari'}),frozenset({'https://docs.example.org'})))
        self.assertEqual(packet.artifacts,[])
