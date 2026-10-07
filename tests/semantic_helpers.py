"""Synthetic fixtures shared by semantic tests; no inherited test duplication."""
import tempfile
import unittest
from pathlib import Path
from semantic_memory.contracts import AccessPolicy, SourceEnvelope, TextSpan
from semantic_memory.store import SemanticStore

def policy(revision=1):
    return AccessPolicy(revision, frozenset({'com.microsoft.VSCode','com.apple.Safari'}),
                        frozenset({'https://docs.example.org'}), frozenset())

def source(sid='s1', **changes):
    values=dict(source_id=sid,at='2026-10-07T10:00:00+00:00',session_id='session',
        app_id='com.microsoft.VSCode',artifact_locator='/projects/one/main.py',workspace_locator='/projects/one',
        identity_authoritative=True,origin_type='observed_screen_text',spans=(TextSpan('span1','Use local storage.',False),),
        policy_revision=1,private_context=False,browser_context_known=True)
    values.update(changes)
    return SourceEnvelope(**values)

class SemanticFixture:
    def setUp(self):
        from semantic_memory.episodes import EpisodeBuilder
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=SemanticStore(Path(self.tmp.name)/'semantic.sqlite3');self.addCleanup(self.db.close)
        self.builder=EpisodeBuilder(self.db)
    def request(self):
        from semantic_memory.episodes import build_request
        self.db.ingest(source(),policy());self.builder.accept('s1')
        eid=self.builder.boundary('stop','2026-10-07T10:01:00+00:00')[0]
        return build_request(self.db,eid)
    def seed_decision(self):
        import json
        from semantic_memory.episodes import build_request
        from semantic_memory.inference import validate_extraction
        from semantic_memory.relationships import apply_extraction
        self.db.ingest(source(origin_type='user_note',spans=(TextSpan('span1','We decided to use SQLite because it stays local.'),)),policy())
        self.builder.accept('s1');eid=self.builder.boundary('stop','2026-10-07T10:00:01+00:00')[0]
        req=build_request(self.db,eid);e=req.evidence[0]
        candidate={'type':'decision','subject_id':e['artifact_id'],'statement':e['text'],'evidence_ids':[e['id']],'extraction_status':'explicit','reason':'it stays local'}
        apply_extraction(self.db,eid,validate_extraction(json.dumps({'candidates':[candidate]}),req))
    def seed_unverified(self):
        import json
        from semantic_memory.inference import validate_extraction
        from semantic_memory.relationships import apply_extraction
        req=self.request();e=req.evidence[0]
        candidate={'type':'decision','subject_id':e['artifact_id'],'statement':'We chose a hosted database','evidence_ids':[e['id']],'extraction_status':'explicit'}
        apply_extraction(self.db,req.episode_id,validate_extraction(json.dumps({'candidates':[candidate]}),req))

