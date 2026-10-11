import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('acceptance',Path(__file__).parents[1]/'scripts/benchmark_memory_mvp.py')
class AcceptanceTests(unittest.TestCase):
    def module(self):
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_missing_observations_never_pass(self):
        m=self.module();self.assertFalse(m.resource_gates({})['passed'])
        self.assertFalse(m.claim_metrics([],[])['passed'])
    def test_unsupported_claims_and_missing_citations_fail(self):
        m=self.module();self.assertFalse(m.claim_metrics([{'statement':'invented','citations':[]}],['expected'])['passed'])
    def test_retrieval_exact_regression_fails(self):
        m=self.module();summary={'all':{'hybrid':{'recall_at_5':.9}},'paraphrase':{'hybrid':{'recall_at_5':.9},'keyword':{'recall_at_5':.5}},'exact':{'hybrid':{'recall_at_5':.8},'keyword':{'recall_at_5':1.0}}}
        self.assertFalse(m.retrieval_gates(summary)['passed'])
    def test_frozen_fixture_validation_rejects_changed_bytes(self):
        import tempfile,shutil,importlib.util
        path=Path(__file__).parents[1]/'scripts/evaluate_memory_retrieval.py'
        sp=importlib.util.spec_from_file_location('frozen',path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'fixture';shutil.copytree(Path(__file__).parent/'fixtures/project_memory/retrieval-v1',folder)
            with (folder/'held-out.json').open('a') as f:f.write(' ')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):m.load_fixture(folder,'held_out')

    def test_fresh_default_claims_have_manual_labels_and_exact_citations(self):
        import json
        cases=json.loads((Path(__file__).parent/'fixtures/project_memory/assertions-v1/cases.json').read_text())
        metrics=self.module().assertion_probe(cases)
        self.assertTrue(metrics['passed'],metrics)
        self.assertEqual(metrics['emitted'],8)
    def test_duplicate_gold_and_overlapping_query_ids_are_rejected(self):
        sp=importlib.util.spec_from_file_location('eval_validation',Path(__file__).parents[1]/'scripts/evaluate_memory_retrieval.py')
        m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
        q={'id':'same','gold_occurrence_ids':['g'],'kind':'exact','text':'identifier'}
        corpus=[{'occurrence_id':'g','ingested':True}]
        with self.assertRaises(ValueError):m.validate_queries(corpus,[q],[q])
        with self.assertRaises(ValueError):m.validate_queries(corpus,[{**q,'gold_occurrence_ids':['g','g']}],[])
