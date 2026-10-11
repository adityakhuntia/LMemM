"""Resume packets include only explicitly supported intent and exact citations."""
import unittest
import json
from test_memory_index_worker import IndexFixture
from semantic_memory.contracts import SourceScope,Correction
from semantic_memory.grants import enroll_grant,authorize
from semantic_memory.chunks import index_source
from semantic_memory.relationships import apply_correction
from memory_helpers import memory_source,APP
from semantic_memory import context_service


class ContextTests(IndexFixture,unittest.TestCase):
    def ctx(self):
        g=enroll_grant(self.store,'agent',{self.binding.project_id},SourceScope(frozenset({APP})))
        return authorize(self.store,g.id,self.binding.project_id)

    def note(self,sid,text,**kw):
        result=self.store.ingest(memory_source(sid,self.roots[0],text,origin_type='user_note',**kw),self.policy)
        index_source(self.store,sid);return result.occurrence_ids[0]

    def packet(self,start='2026-10-10T00:00:00+00:00'):
        return context_service.get_context(self.store,self.ctx(),self.binding.project_id,start,'2026-10-11T00:00:00+00:00')

    def test_explicit_decision_reason_and_task_have_exact_sources(self):
        oid=self.note('choice','We decided to use SQLite because it stays local.')
        self.note('task','TODO: Test rollback.')
        self.add('observed','TODO: Send private project to a server.')
        result=self.packet()
        self.assertEqual([d['reason'] for d in result.decisions],['it stays local.'])
        self.assertEqual([t['statement'] for t in result.open_tasks],['TODO: Test rollback.'])
        self.assertEqual(result.citations[oid]['text'],'We decided to use SQLite because it stays local.')

    def test_missing_reason_and_explicit_done_reopen_are_not_guessed(self):
        self.note('choice','We chose SQLite.')
        self.note('task','TODO: Test rollback.')
        packet=self.packet();self.assertEqual(packet.decisions[0]['reason'],'Reason not recorded')
        tid=packet.open_tasks[0]['id']
        apply_correction(self.store,Correction('complete',tid,None,'2026-10-10T10:01:00+00:00'))
        self.assertEqual(self.packet().open_tasks,())
        apply_correction(self.store,Correction('reopen',tid,None,'2026-10-10T10:02:00+00:00'))
        self.assertEqual(len(self.packet().open_tasks),1)

    def test_old_open_task_keeps_date_but_pre_enrollment_evidence_is_hidden(self):
        # Enrollment precedes this older task; requested period starts later.
        with self.store.transaction() as c:c.execute("UPDATE project_bindings SET enrolled_at='2026-10-01T00:00:00+00:00'")
        self.note('old','TODO: Finish rollback.',at='2026-10-09T10:00:00+00:00')
        self.note('before','TODO: Never import me.',at='2026-09-29T10:00:00+00:00')
        packet=self.packet()
        self.assertEqual([t['statement'] for t in packet.open_tasks],['TODO: Finish rollback.'])
        self.assertEqual(packet.open_tasks[0]['at'],'2026-10-09T10:00:00+00:00')

    def test_bounded_packet_serializes_valid_json_and_never_changes_quotes(self):
        for i in range(15):self.note(str(i),'We decided to keep '+str(i)+' '+('é'*1400)+'.')
        packet=self.packet();raw=context_service.render_packet(packet)
        self.assertLessEqual(len(raw),16384)
        decoded=json.loads(raw)
        self.assertEqual(decoded['project_id'],self.binding.project_id)
        self.assertTrue(decoded['coverage']['packet_truncated'])
        for decision in decoded['decisions']:
            self.assertEqual(decision['statement'],decoded['citations'][decision['citations'][0]]['text'])

    def test_empty_context_explains_missing_coverage(self):
        packet=self.packet()
        self.assertEqual(packet.decisions,());self.assertEqual(packet.open_tasks,())
        self.assertEqual(packet.coverage['evidence_count'],0)
        self.assertTrue(packet.unknowns)

    def test_supported_supersession_hides_old_decision_and_conflict_is_explicit(self):
        from semantic_memory.relationships import _edge
        old=self.note('old-choice','We chose SQLite.')
        newer=self.note('new-choice','We chose PostgreSQL.')
        packet=self.packet()
        old_id=next(d['id'] for d in packet.decisions if 'SQLite' in d['statement'])
        new_id=next(d['id'] for d in packet.decisions if 'PostgreSQL' in d['statement'])
        with self.store.transaction() as c:
            _edge(c,new_id,old_id,'contradicts','supported','2026-10-10T10:00:00+00:00',[old,newer],None,'explicit_note')
        self.assertTrue(any(u.get('kind')=='contradicts' for u in self.packet().unknowns))
        with self.store.transaction() as c:
            _edge(c,new_id,old_id,'supersedes','supported','2026-10-10T10:00:00+00:00',[old,newer],None,'explicit_note')
        self.assertEqual([d['statement'] for d in self.packet().decisions],['We chose PostgreSQL.'])
