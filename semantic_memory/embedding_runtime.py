"""Pinned local embeddings via the owned cloud-disabled Ollama runtime."""
import hashlib
import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol
import numpy as np
from .api_contracts import ModelManifest
from .local_runtime import NoRedirect

# No caller-supplied endpoint and no implicit installation or remote aliases.
ENDPOINT = 'http://127.0.0.1:11455/api/embed'
CANDIDATES = {'all-minilm:22m':384, 'all-minilm:33m':384}


class EmbeddingBackend(Protocol):
    manifest: ModelManifest
    def embed(self,texts:tuple[str,...],*,query:bool)->np.ndarray: ...
    def cancel(self)->None: ...


def _sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def validate_manifest(manifest):
    if (manifest.runtime!='ollama-local' or manifest.model_id not in CANDIDATES
        or manifest.dimension!=CANDIDATES[manifest.model_id] or manifest.max_input_tokens!=512
        or manifest.chunk_version!=1 or not re.fullmatch('[0-9a-f]{64}',manifest.digest)):
        raise ValueError('Unsupported local embedding manifest')
    path=Path(manifest.weights_path)
    if not path.is_absolute() or not path.is_file() or path.stat().st_size>32768:
        raise ValueError('Local model assets required')
    model,tag=manifest.model_id.split(':')
    if tuple(path.parts[-5:])!=('manifests','registry.ollama.ai','library',model,tag) or _sha256(path)!=manifest.digest:
        raise ValueError('Embedding manifest digest/path mismatch')
    doc=json.loads(path.read_text());layers=doc.get('layers',[])
    if not layers or not any(l.get('mediaType')=='application/vnd.ollama.image.model' for l in layers):
        raise ValueError('Local embedding weights absent')
    root=path.parents[4]
    for layer in layers:
        digest=layer.get('digest','')
        if not re.fullmatch('sha256:[0-9a-f]{64}',digest):raise ValueError('Invalid weight digest')
        blob=root/'blobs'/digest.replace(':','-')
        if not blob.is_file() or _sha256(blob)!=digest[7:]:raise ValueError('Embedding weight digest mismatch')


class OllamaEmbeddingBackend:
    def __init__(self,manifest):
        validate_manifest(manifest)
        self.manifest=manifest;self.cancelled=threading.Event()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def _post(self,payload):
        request=urllib.request.Request(ENDPOINT,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=30) as response:raw=response.read(1024*1024+1)
        except urllib.error.HTTPError as error:
            # Error bodies can echo source text; expose a fixed local failure.
            raise ValueError('Local embedding input rejected; check model token limit') from error
        if len(raw)>1024*1024:raise ValueError('Oversize embedding response')
        return json.loads(raw)

    def embed(self,texts,*,query):
        if self.cancelled.is_set():raise RuntimeError('Embedding cancelled')
        if not isinstance(texts,tuple) or not 1<=len(texts)<=8:
            raise ValueError('Embedding batch must contain 1–8 texts')
        cap=2048 if query else 4096
        if any(not isinstance(t,str) or not t or len(t.encode())>cap for t in texts):
            raise ValueError('Invalid embedding input')
        # MiniLM uses symmetric sentence embeddings: no query/document prefix.
        response=self._post({'model':self.manifest.model_id,'input':list(texts),'truncate':False,'keep_alive':'30s'})
        if self.cancelled.is_set():raise RuntimeError('Embedding cancelled')
        try:matrix=np.asarray(response['embeddings'],dtype=np.float32)
        except (KeyError,TypeError,ValueError) as error:raise ValueError('Invalid embeddings') from error
        if matrix.shape!=(len(texts),self.manifest.dimension) or not np.isfinite(matrix).all():
            raise ValueError('Invalid embedding dimensions/values')
        norms=np.linalg.norm(matrix,axis=1,keepdims=True)
        if not np.isfinite(norms).all() or (norms<=0).any():raise ValueError('Zero/invalid embedding norm')
        return matrix/norms

    def cancel(self):self.cancelled.set()

    def unload(self):
        self._post({'model':self.manifest.model_id,'input':[], 'keep_alive':0})


def load_backend(manifest):return OllamaEmbeddingBackend(manifest)
