#!/usr/bin/env python3
"""Frozen synthetic retrieval comparison; never installs models or reads projects."""
import argparse
import dataclasses
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from semantic_memory.api_contracts import ModelManifest, Query
from semantic_memory.contracts import SourceEnvelope, TextSpan, AccessPolicy, SourceScope
from semantic_memory.embedding_runtime import load_backend
from semantic_memory.store import SemanticStore
from semantic_memory.project_scope import bind_project
from semantic_memory.grants import enroll_grant,authorize
from semantic_memory.chunks import index_source
from semantic_memory.search import keyword_candidates


def score_ranking(ranking,gold):
    if not gold:return None
    gold=set(gold)
    return {'recall_at_5':len(set(ranking[:5])&gold)/len(gold),
            'mrr':next((1/(i+1) for i,item in enumerate(ranking) if item in gold),0.0)}


def load_fixture(directory,split):
    manifest=json.loads((directory/'manifest.json').read_text())
    for key in ('corpus',split):
        name=manifest['files'][key];raw=(directory/name).read_bytes()
        digest_key={'development':'development_sha256','held_out':'held_out_sha256','corpus':'corpus_sha256'}[key]
        if hashlib.sha256(raw).hexdigest()!=manifest[digest_key]:raise ValueError('Frozen fixture hash mismatch')
    return manifest,json.loads((directory/manifest['files']['corpus']).read_text()),json.loads((directory/manifest['files'][split]).read_text())


def evaluate(directory,manifest,split):
    fixture,corpus,questions=load_fixture(directory,split)
    backend=load_backend(manifest)
    app='com.microsoft.VSCode';policy=AccessPolicy(1,frozenset({app}),frozenset())
    embeddings={};embedding_seconds=0.0;timings=[];details=[]
    with tempfile.TemporaryDirectory() as temp:
        store=SemanticStore(Path(temp)/'memory.sqlite3')
        try:
            bindings={name:bind_project(store,name,root,'2026-10-01T00:00:00+00:00') for name,root in fixture['projects'].items()}
            grant=enroll_grant(store,'synthetic-evaluator',{b.project_id for b in bindings.values()},SourceScope(frozenset({app})))
            for source in corpus:
                if not source['ingested']:continue
                s=SourceEnvelope(source['source_id'],source['at'],source['session_id'],app,source['artifact'],fixture['projects'][source['project']],True,source['origin_type'],(TextSpan(source['span_id'],source['text']),),1)
                result=store.ingest(s,policy)
                if result.occurrence_ids[0]!=source['occurrence_id']:raise ValueError('Gold occurrence identity mismatch')
                index_source(store,s.source_id)
                started=time.perf_counter();embeddings[source['occurrence_id']]=backend.embed((source['text'],),query=False)[0];embedding_seconds+=time.perf_counter()-started
            for q in questions:
                binding=bindings[q['project']];ctx=authorize(store,grant.id,binding.project_id)
                query=Query(binding.project_id,q['text'],q['start'],q['end'])
                started=time.perf_counter();qv=backend.embed((q['text'],),query=True)[0];timings.append(time.perf_counter()-started)
                permitted=[s for s in corpus if s['ingested'] and s['project']==q['project'] and q['start']<=s['at']<=q['end']]
                vector=sorted(permitted,key=lambda s:(-float(embeddings[s['occurrence_id']]@qv),s['occurrence_id']))[:50]
                vr=[s['occurrence_id'] for s in vector]
                kr=list(dict.fromkeys(h.citation_id for h in keyword_candidates(store,ctx,query)))
                scores={}
                for ranking in (kr,vr):
                    for i,oid in enumerate(ranking):scores[oid]=scores.get(oid,0)+1/(60+i+1)
                hybrid=sorted(scores,key=lambda oid:(-scores[oid],oid))
                details.append({'id':q['id'],'kind':q['kind'],'gold_count':len(q['gold_occurrence_ids']),
                                'scores':{name:score_ranking(rank,q['gold_occurrence_ids']) for name,rank in [('keyword',kr),('vector',vr),('hybrid',hybrid)]},
                                'rankings':{'keyword':kr[:10],'vector':vr[:10],'hybrid':hybrid[:10]}})
        finally:store.close()
    summary={}
    for kind in ('all','exact','paraphrase'):
        subset=[d for d in details if d['gold_count'] and (kind=='all' or d['kind']==kind)]
        summary[kind]={'count':len(subset)}
        for method in ('keyword','vector','hybrid'):
            summary[kind][method]={metric:sum(d['scores'][method][metric] for d in subset)/len(subset) if subset else None for metric in ('recall_at_5','mrr')}
    return {'model_id':manifest.model_id,'model_digest':manifest.digest,'dimension':manifest.dimension,'fixture':fixture,'split':split,'summary':summary,'details':details,'embedding_seconds':embedding_seconds,'query_embedding_seconds':{'count':len(timings),'p50':float(np.percentile(timings,50)),'p95':float(np.percentile(timings,95))},'acceptance':'development comparison only' if split=='development' else 'held-out retrieval only; other acceptance gates separate'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True,help='Explicit installed local ModelManifest JSON')
    p.add_argument('--fixtures',type=Path,default=Path('tests/fixtures/project_memory/retrieval-v1'))
    p.add_argument('--split',choices=('development','held_out'),default='development')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();manifest=ModelManifest(**json.loads(args.manifest.read_text()))
    result=evaluate(args.fixtures,manifest,args.split)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('model_id','split','summary','query_embedding_seconds')},indent=2))

if __name__=='__main__':main()
