import tempfile
import unittest
from pathlib import Path
from semantic_memory.local_runtime import LocalRuntime,RuntimeConfig
from semantic_memory.evaluation import score_predictions,load_fixture_manifest

class EvaluationTests(unittest.TestCase):
    def test_metrics_count_false_positives_and_missing_predictions(self):
        report=score_predictions([{'expected':'decision','predicted':['decision']},
                                  {'expected':'none','predicted':['decision']},
                                  {'expected':'task','predicted':[]}])
        self.assertEqual(report['claim_precision'],.5)
        self.assertEqual(report['claim_recall'],.5)
        self.assertEqual(report['unsupported_assertions'],1)

    def test_corpus_split_is_disjoint_and_fixed(self):
        corpus=load_fixture_manifest(Path(__file__).parent/'fixtures/project_memory/manifest.json')
        self.assertEqual(len(corpus['cases']),24)
        self.assertFalse(set(corpus['development'])&set(corpus['heldout']))
        self.assertEqual(len(corpus['heldout']),8)

    def test_missing_assets_and_remote_configuration_fail_before_request(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):LocalRuntime(RuntimeConfig(Path('/missing'),Path(temp)/'missing'))
            with self.assertRaises(ValueError):LocalRuntime(RuntimeConfig(Path('/usr/local/bin/ollama'),Path(temp),arguments=('https://cloud.example',)))
