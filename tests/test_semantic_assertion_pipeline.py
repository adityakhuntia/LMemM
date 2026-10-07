import json
import unittest
from pathlib import Path
from semantic_memory.evaluation import evaluate,load_fixture_manifest

class SourceQuoteExtractor:
    synthetic=True
    def extract(self,request):
        e=request.evidence[0]
        return json.dumps({'candidates':[{'type':'decision','subject_id':e['artifact_id'],
            'statement':e['text'],'evidence_ids':[e['id']],'extraction_status':'explicit'}]})

class AssertionPipelineTests(unittest.TestCase):
    def test_actual_store_output_and_privacy_probes_are_scored(self):
        corpus=load_fixture_manifest(Path(__file__).parent/'fixtures/project_memory/assertions-v2.json')
        # Keep one real permitted envelope; synthetic extractor cannot earn model selection.
        corpus['cases']=[dict(corpus['cases'][12])];corpus['development']=[corpus['cases'][0]['id']]
        report=evaluate(corpus,SourceQuoteExtractor(),'development')
        self.assertEqual(report['assertion_metrics']['true_positive'],1)
        self.assertEqual(report['privacy_metrics']['forbidden_source_leaks'],0)
        self.assertGreaterEqual(report['privacy_metrics']['probes'],3)
        self.assertFalse(report['selection_pass'])
        self.assertFalse(report['actual_local_model'])
    def test_missing_gold_cannot_report_semantic_quality(self):
        corpus=load_fixture_manifest(Path(__file__).parent/'fixtures/project_memory/manifest.json')
        report=evaluate(dict(corpus,cases=[corpus['cases'][12]]),SourceQuoteExtractor(),'development')
        self.assertFalse(report['quality_pass'])
        self.assertIn('proposition/reason accuracy',report['acceptance_incomplete'])
