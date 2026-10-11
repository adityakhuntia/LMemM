"""Project/grant tests catch scope widening, unstable identity and stale grants."""
import tempfile
import unittest
from pathlib import Path
from memory_helpers import make_memory_fixture, AT, APP
from semantic_memory.contracts import SourceScope
from semantic_memory import project_scope, grants
from semantic_memory.api_contracts import Query


class MemoryScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store, self.roots, _ = make_memory_fixture(self.tmp.name)
        self.addCleanup(self.store.close)

    def bind(self, ui='a', root=None):
        return project_scope.bind_project(self.store, ui, root or self.roots[0], AT)

    def test_same_basename_is_distinct_and_rebinding_cannot_change_identity(self):
        a = self.bind(); b = self.bind('b', self.roots[1])
        self.assertNotEqual(a.project_id, b.project_id)
        self.assertEqual(self.bind(), a)
        with self.assertRaises(ValueError): self.bind('a', self.roots[1])
        with self.assertRaises(ValueError): self.bind('b', self.roots[0])
        self.assertEqual(project_scope.resolve_binding(self.store, 'a'), a)

    def test_relative_and_symlink_roots_have_one_canonical_identity(self):
        root = Path(self.roots[0]); root.mkdir(parents=True)
        alias = Path(self.tmp.name) / 'alias'; alias.symlink_to(root, target_is_directory=True)
        a = self.bind(root=str(alias.parent / '.' / 'alias'))
        self.assertEqual(a.workspace_root, str(root.resolve()))
        with self.assertRaises(ValueError): self.bind('b', str(root))
        with self.assertRaises(ValueError): self.bind('relative', 'relative/repo')
        with self.assertRaises(ValueError): self.bind('whole-disk', '/')

    def test_unknown_and_denied_projects_are_indistinguishable(self):
        a = self.bind(); b = self.bind('b', self.roots[1])
        g = grants.enroll_grant(self.store, 'agent-1', frozenset({a.project_id}), SourceScope(frozenset({APP})))
        ctx = grants.authorize(self.store, g.id, a.project_id)
        self.assertEqual(ctx.grant_id, g.id)
        failures = []
        for pid in (b.project_id, 'does-not-exist'):
            with self.assertRaises(ValueError) as e: grants.authorize(self.store, g.id, pid)
            failures.append(str(e.exception))
        self.assertEqual(failures, ['unavailable', 'unavailable'])
        self.assertEqual(grants.current_grant(self.store, ctx, a.project_id), g)

    def test_revocation_invalidates_existing_context_and_survives_reopen(self):
        a = self.bind()
        g = grants.enroll_grant(self.store, 'agent', {a.project_id}, SourceScope(frozenset({APP})))
        ctx = grants.authorize(self.store, g.id, a.project_id)
        revision = grants.revoke_grant(self.store, g.id)
        self.assertGreater(revision, ctx.policy_revision)
        with self.assertRaises(ValueError): grants.current_grant(self.store, ctx, a.project_id)
        with self.assertRaises(ValueError): grants.authorize(self.store, g.id, a.project_id)
        # Stored user evidence/project identity remains after revoking an agent.
        self.assertEqual(project_scope.resolve_binding(self.store, 'a'), a)

    def test_grant_cannot_enroll_unknown_or_inactive_project(self):
        a = self.bind()
        with self.assertRaises(ValueError): grants.enroll_grant(self.store, 'agent', {'missing'}, SourceScope(frozenset({APP})))
        project_scope.set_binding_active(self.store, 'a', False)
        self.assertFalse(project_scope.resolve_binding(self.store, 'a').active)
        with self.assertRaises(ValueError): grants.enroll_grant(self.store, 'agent', {a.project_id}, SourceScope(frozenset({APP})))

    def test_query_rejects_oversized_text_invalid_time_or_limit(self):
        for kwargs in ({'text':'é'*1025},{'limit':11},{'limit':True},{'start':'2026-10-10'}, {'start':AT,'end':'2026-10-09T00:00:00+00:00'}):
            values = dict(project_id='p', text='query', start=None, end=None); values.update(kwargs)
            with self.assertRaises(ValueError): Query(**values)
        self.assertEqual(Query('p','é'*1024,None,None).limit, 10)
