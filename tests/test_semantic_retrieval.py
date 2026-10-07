from test_semantic_relationships import RelationshipTests
from semantic_memory.retrieval import project_context, resolve_citation, render_context
from semantic_memory.contracts import SourceScope
from semantic_memory.retention import delete_sources

class RetrievalTests(RelationshipTests):
    def test_project_context_and_scoped_citations(self):
        self.test_workspace_and_explicit_note_supported()
        pid=self.db.connection.execute('SELECT id FROM projects').fetchone()[0]
        scope=SourceScope(frozenset({'com.microsoft.VSCode'}))
        packet=project_context(self.db,pid,'2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00',scope)
        self.assertEqual(len(packet.decisions),1)
        self.assertIn('it stays local',render_context(packet))
        cid=next(iter(packet.citations))
        self.assertIsNotNone(resolve_citation(self.db,cid,scope))
        self.assertIsNone(resolve_citation(self.db,cid,SourceScope(frozenset())))
        hidden=project_context(self.db,pid,packet.start,packet.end,SourceScope(frozenset()))
        self.assertEqual(hidden.decisions,[])
        self.assertEqual(hidden.citations,{})
        delete_sources(self.db,{'s1'})
        self.assertIsNone(resolve_citation(self.db,cid,scope))

    def test_unknown_decisions_not_reported_as_verified(self):
        self.test_observed_ai_is_not_user_decision()
        pid=self.db.connection.execute('SELECT id FROM projects').fetchone()[0]
        packet=project_context(self.db,pid,'2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00',SourceScope(frozenset({'com.microsoft.VSCode'})))
        self.assertEqual(packet.decisions,[])
        self.assertTrue(packet.unknowns)
