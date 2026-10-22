"""Release-review regressions exercise real stores, scope filters and migration."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from semantic_memory.store import SemanticStore,SCHEMA
from semantic_memory.migrations import V2_SQL,VERSION
from semantic_memory.project_scope import bind_project
from semantic_memory.intentional_sources import save_intentional,move_saved_source,delete_saved_source,record_claim,NATIVE_APP,BROWSER_APP,BROWSER_SCOPE
from semantic_memory.grants import enroll_grant,authorize
from semantic_memory.contracts import SourceScope
from semantic_memory.api_contracts import Query
from semantic_memory.search import keyword_candidates,resolve_source
from semantic_memory.resume import resume_project


class LaunchOneRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'memory.sqlite'
        self.store=SemanticStore(self.path);self.addCleanup(self.store.close)
        self.a=bind_project(self.store,'alpha',None,'2026-10-01T00:00:00+00:00').project_id

    def ctx(self,pid=None):
        pid=pid or self.a
        g=enroll_grant(self.store,'test',{pid},SourceScope(frozenset({NATIVE_APP,BROWSER_APP}),frozenset({BROWSER_SCOPE})))
        return authorize(self.store,g.id,pid)

    def save(self,key,text,**extra):
        return save_intentional(self.store,self.a,dict(request_id=key,kind='pasted_excerpt',text=text,title='Source',**extra),at='2026-10-10T10:00:00+00:00')

    def test_move_to_newer_project_keeps_historical_snapshot_visible(self):
        saved=self.save('old','SQLite is local.')
        b=bind_project(self.store,'beta',None,'2026-10-20T00:00:00+00:00').project_id
        move_saved_source(self.store,saved['source_id'],b)
        hits=keyword_candidates(self.store,self.ctx(b),Query(b,'SQLite'))
        self.assertEqual(len(hits),1)
        self.assertEqual(resolve_source(self.store,self.ctx(b),b,hits[0].citation_id).at,'2026-10-10T10:00:00+00:00')
        self.assertEqual(len(resume_project(self.store,self.ctx(b),b)['saved_activity']),1)

    def test_large_decisions_are_bounded_without_changing_retained_evidence(self):
        for i in range(10):
            text=str(i)+' '+('x'*131060)
            saved=self.save(str(i),text)
            record_claim(self.store,self.a,saved['source_id'],'decision',0,len(text))
        result=resume_project(self.store,self.ctx(),self.a)
        self.assertLess(len(json.dumps(result).encode()),1048576)
        self.assertEqual(len(result['decisions']),10)
        self.assertTrue(result['coverage'].get('display_shortened'))
        self.assertEqual(self.store.connection.execute('SELECT max(length(text)) FROM blobs').fetchone()[0],131062)

    def test_delete_removes_locator_and_incoming_reference_edges(self):
        page=self.save('page','Database comparison.',url='https://example.org/database')
        self.save('reference','See https://example.org/database for details.')
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM edges WHERE kind='references'").fetchone()[0],1)
        delete_saved_source(self.store,page['source_id'])
        self.assertIsNone(self.store.connection.execute('SELECT id FROM artifacts WHERE locator=?',('https://example.org/database',)).fetchone())
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM edges WHERE kind='references'").fetchone()[0],0)

    def test_invalid_existing_upgrade_backup_never_counts_as_recoverable(self):
        legacy=Path(self.tmp.name)/'legacy.sqlite'
        c=sqlite3.connect(legacy);c.executescript(SCHEMA)
        for statement in V2_SQL:c.execute(statement)
        c.execute("INSERT INTO meta VALUES('memory_revision','1')");c.execute('PRAGMA user_version=2');c.commit();c.close()
        legacy.with_name(legacy.name+'.pre-v'+str(VERSION)).touch(mode=0o600)
        try:
            upgraded=SemanticStore(legacy)
        except (ValueError,sqlite3.DatabaseError):
            with sqlite3.connect(legacy) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],2)
        else:
            upgraded.close()
            with sqlite3.connect(legacy.with_name(legacy.name+'.pre-v'+str(VERSION))) as c:
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],2)
