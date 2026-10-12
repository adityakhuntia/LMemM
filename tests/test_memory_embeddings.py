"""Runtime contracts catch remote fallback, altered weights and corrupt vectors."""
import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from semantic_memory.api_contracts import ModelManifest
from semantic_memory import embedding_runtime as runtime


def local_manifest(root):
    root=Path(root);blob=b'synthetic embedding weights';digest='sha256:'+hashlib.sha256(blob).hexdigest()
    (root/'blobs').mkdir(parents=True);(root/'blobs'/digest.replace(':','-')).write_bytes(blob)
    path=root/'manifests/registry.ollama.ai/library/all-minilm/22m';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'layers':[{'mediaType':'application/vnd.ollama.image.model','digest':digest,'size':len(blob)}]}))
    return ModelManifest('all-minilm:22m',hashlib.sha256(path.read_bytes()).hexdigest(),384,512,1,'ollama-local',str(path))


class EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.manifest=local_manifest(self.tmp.name)

    def test_validated_backend_normalizes_float32_and_preserves_input(self):
        backend=runtime.load_backend(self.manifest)
        response={'embeddings':[[3.0]+[4.0]+[0.0]*382]}
        with patch.object(backend,'_post',return_value=response) as post:
            vectors=backend.embed(('Retained café.',),query=False)
            self.assertEqual(vectors.dtype,np.float32)
            self.assertEqual(vectors.shape,(1,384))
            self.assertAlmostEqual(float(vectors[0,0]),0.6,places=6)
            self.assertAlmostEqual(float(np.linalg.norm(vectors[0])),1.0,places=6)
            self.assertEqual(post.call_args.args[0]['input'],['Retained café.'])
            self.assertIs(post.call_args.args[0]['truncate'],False)
        with patch.object(backend,'_post',return_value=response) as post:
            backend.embed(('What did we choose?',),query=True)
            self.assertEqual(post.call_args.args[0]['input'],['What did we choose?'])

    def test_oversize_chunk_is_retried_truncated_instead_of_failing(self):
        backend=runtime.load_backend(self.manifest)
        good={'embeddings':[[3.0]+[4.0]+[0.0]*382]}
        calls=[]
        def post(payload):
            calls.append(payload['truncate'])
            if not payload['truncate']:raise ValueError('Local embedding input rejected; check model token limit')
            return good
        with patch.object(backend,'_post',side_effect=post):
            self.assertEqual(backend.embed(('dense code',),query=False).shape,(1,384))
        self.assertEqual(calls,[False,True])

    def test_invalid_shape_nonfinite_and_zero_vectors_are_rejected(self):
        backend=runtime.load_backend(self.manifest)
        for rows in ([[1,2]],[[0]*384],[[float('nan')]*384],[[float('inf')]*384],[]):
            with self.subTest(rows=len(rows)),patch.object(backend,'_post',return_value={'embeddings':rows}):
                with self.assertRaises(ValueError):backend.embed(('text',),query=False)

    def test_cancellation_prevents_accepting_inflight_response(self):
        backend=runtime.load_backend(self.manifest)
        def answer(payload):
            backend.cancel()
            return {'embeddings':[[1.0]+[0.0]*383]}
        with patch.object(backend,'_post',side_effect=answer):
            with self.assertRaises(RuntimeError):backend.embed(('text',),query=False)
        with self.assertRaises(RuntimeError):backend.embed(('text',),query=False)

    def test_manifest_and_every_weight_hash_are_verified(self):
        runtime.validate_manifest(self.manifest)
        for change in ({'digest':'0'*64},{'runtime':'https://example.org'},{'weights_path':'https://example.org/model'}, {'model_id':'all-minilm:cloud'},{'dimension':768}):
            with self.subTest(change=change),self.assertRaises(ValueError):runtime.load_backend(dataclasses.replace(self.manifest,**change))
        next((Path(self.tmp.name)/'blobs').iterdir()).write_bytes(b'altered weights')
        with self.assertRaises(ValueError):runtime.load_backend(self.manifest)

    def test_input_caps_and_token_overflow_fail_without_truncation(self):
        backend=runtime.load_backend(self.manifest)
        with self.assertRaises(ValueError):backend.embed(('x'*2049,),query=True)
        with self.assertRaises(ValueError):backend.embed(('x',)*9,query=False)
        with patch.object(backend,'_post',side_effect=ValueError('input exceeds model token limit')):
            with self.assertRaisesRegex(ValueError,'token limit'):backend.embed(('text',),query=False)


class NewerOllamaLayoutTests(unittest.TestCase):
    def test_manifests_v2_layout_is_accepted_with_the_same_digest_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=local_manifest(tmp)
            newer=Path(tmp)/'manifests-v2/ollama.com/library/all-minilm/22m';newer.parent.mkdir(parents=True)
            newer.write_bytes(Path(old.weights_path).read_bytes())
            runtime.validate_manifest(dataclasses.replace(old,weights_path=str(newer)))

    def test_other_locations_are_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=local_manifest(tmp)
            elsewhere=Path(tmp)/'manifests/elsewhere.example/library/all-minilm/22m';elsewhere.parent.mkdir(parents=True)
            elsewhere.write_bytes(Path(old.weights_path).read_bytes())
            with self.assertRaises(ValueError):runtime.validate_manifest(dataclasses.replace(old,weights_path=str(elsewhere)))
