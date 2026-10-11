"""Hand-calculated scoring prevents optimistic retrieval reports."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('memory_eval',Path(__file__).parents[1]/'scripts/evaluate_memory_retrieval.py')


class EvaluatorTests(unittest.TestCase):
    def test_recall_and_mrr_are_computed_from_gold_not_returned_count(self):
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertEqual(m.score_ranking(['wrong','gold'],['gold']),{'recall_at_5':1.0,'mrr':0.5})
        self.assertEqual(m.score_ranking(['a','b','c','d','e','gold'],['gold']),{'recall_at_5':0.0,'mrr':1/6})
        self.assertIsNone(m.score_ranking(['irrelevant'],[]))
