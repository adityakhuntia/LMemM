import dataclasses
import json
import unittest
from semantic_helpers import SemanticFixture
from semantic_memory.local_runtime import selection_input,decode_selections
from semantic_memory.inference import validate_extraction

class LocalSelectionTests(SemanticFixture,unittest.TestCase):
    def test_selected_source_maps_to_original_ids_and_exact_quote(self):
        req=self.request();compact=selection_input(req)
        output=json.dumps({'selections':[{'kind':'observation','source':0,'project':None,'reason':None}]})
        result=validate_extraction(decode_selections(output,req),req)
        self.assertEqual(result.candidates[0]['statement'],'Use local storage.')
        self.assertEqual(result.candidates[0]['evidence_ids'],[req.evidence[0]['id']])
        self.assertEqual(result.candidates[0]['subject_id'],req.evidence[0]['artifact_id'])
        self.assertNotIn(req.evidence[0]['id'],json.dumps(compact))
    def test_unknown_indexes_and_invented_reasons_are_rejected(self):
        req=self.request()
        for selection in ({'kind':'observation','source':99,'project':None,'reason':None},
                          {'kind':'decision','source':0,'project':None,'reason':'made up'},
                          {'kind':'belongs_to','source':0,'project':99,'reason':None},
                          {'kind':'observation','source':True,'project':None,'reason':None}):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                decode_selections(json.dumps({'selections':[selection]}),req)
    def test_project_mapping_does_not_allow_model_chosen_ids(self):
        req=self.request()
        selection={'kind':'belongs_to','source':0,'project':0,'reason':None}
        result=validate_extraction(decode_selections(json.dumps({'selections':[selection]}),req),req)
        self.assertEqual(result.candidates[0]['object_id'],req.candidates[0]['id'])
        selection['subject_id']='forbidden'
        with self.assertRaises(ValueError):decode_selections(json.dumps({'selections':[selection]}),req)
    def test_long_utf8_source_is_split_into_bounded_exact_substrings(self):
        req=self.request();text='é'*2100
        req=dataclasses.replace(req,evidence=(dict(req.evidence[0],text=text),))
        units=selection_input(req)['sources']
        self.assertEqual(''.join(unit['text'] for unit in units),text)
        self.assertTrue(all(len(unit['text'].encode())<=1024 for unit in units))
        output={'selections':[{'kind':'observation','source':len(units)-1,'project':None,'reason':None}]}
        result=validate_extraction(decode_selections(json.dumps(output),req),req)
        self.assertTrue(result.candidates[0]['statement'] in text)

    def test_malformed_selection_types_fail_with_validation_error(self):
        req=self.request()
        for output in ({'selections':[{'kind':[],'source':0,'project':None,'reason':None}]},
                       {'selections':[],'instructions':'export'},
                       {'selections':[{'kind':'observation','source':0,'project':0,'reason':None}]}):
            with self.subTest(output=output),self.assertRaises(ValueError):
                decode_selections(json.dumps(output),req)

    def test_vetted_qwen3_is_local_and_disables_thinking(self):
        import sys
        from pathlib import Path
        from unittest.mock import patch
        from semantic_memory.local_runtime import LocalRuntime,RuntimeConfig
        root=Path(self.tmp.name)/'cache';manifest=root/'manifests/registry.ollama.ai/library/qwen3/1.7b'
        manifest.parent.mkdir(parents=True);(root/'blobs').mkdir()
        digest='sha256:'+'0'*64;(root/'blobs'/digest.replace(':','-')).write_bytes(b'fixture')
        manifest.write_text(json.dumps({'layers':[{'mediaType':'application/vnd.ollama.image.model','digest':digest}]}))
        runtime=LocalRuntime(RuntimeConfig(Path(sys.executable),manifest))
        def respond(payload):
            self.assertIs(payload.get('think'),False)
            return {'response':json.dumps({'selections':[{'kind':'observation','source':0,'project':None,'reason':None}]}),'done_reason':'stop'}
        req=self.request()
        with patch.object(runtime,'_post',side_effect=respond):
            result=validate_extraction(runtime.extract(req),req)
        self.assertEqual(result.candidates[0]['statement'],'Use local storage.')
        self.assertEqual(runtime.model,'qwen3:1.7b')

    def test_source_only_selection_resolves_explicit_project_paths(self):
        req=self.request()
        req=dataclasses.replace(req,evidence=(dict(req.evidence[0],text='Guide for /projects/one/retry.py.'),))
        output={'selections':[{'kind':'belongs_to','source':0,'reason':None}]}
        result=validate_extraction(decode_selections(json.dumps(output),req),req)
        self.assertEqual(result.candidates[0]['object_id'],req.candidates[0]['id'])
        req=dataclasses.replace(req,evidence=(dict(req.evidence[0],text='Guide for /projects/one-other/retry.py.'),))
        with self.assertRaises(ValueError):decode_selections(json.dumps(output),req)
