#!/usr/bin/env python3
"""Synthetic full-search/resource probe. Never substitutes for the paired 30-minute native workload."""
import argparse,dataclasses,json,os,resource,sys,tempfile,time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
import numpy as np

def retrieval_gates(summary):
    try:
        overall=summary['all']['hybrid']['recall_at_5']>=.8
        gain=summary['paraphrase']['hybrid']['recall_at_5']-summary['paraphrase']['keyword']['recall_at_5']>=.1-1e-9
        exact=summary['exact']['hybrid']['recall_at_5']>=summary['exact']['keyword']['recall_at_5']
    except (KeyError,TypeError):return {'passed':False,'reason':'missing retrieval observations'}
    return {'passed':overall and gain and exact,'overall':overall,'paraphrase_gain':gain,'exact_no_regression':exact}

def claim_metrics(emitted,gold):
    gold=set(gold);statements=[c.get('statement') for c in emitted]
    unsupported=sum(s not in gold or not c.get('citations') for c,s in zip(emitted,statements))
    correct=len(emitted)-unsupported
    precision=correct/len(emitted) if emitted else None
    recall=len(set(statements)&gold)/len(gold) if gold else None
    return {'emitted':len(emitted),'gold':len(gold),'unsupported':unsupported,'precision':precision,'recall':recall,
            'passed':bool(emitted and gold and precision>=.95 and unsupported==0)}

def resource_gates(samples):
    thresholds={'paired_active_seconds':1800,'idle_seconds':60,'authorized_chunks':10000}
    required=['warm_p95_seconds','additional_runtime_peak_bytes','additional_nonmodel_peak_bytes','additional_idle_cpu_percent','loaded_model']
    if any(key not in samples for key in [*thresholds,*required]):return {'passed':False,'reason':'missing paired or loaded-model measurements'}
    passed=all(samples[k]>=v for k,v in thresholds.items()) and samples['warm_p95_seconds']<=2 and samples['additional_runtime_peak_bytes']<=3*1024**3 and samples['additional_nonmodel_peak_bytes']<=150*1024**2 and samples['additional_idle_cpu_percent']<=2 and samples['loaded_model']
    return {'passed':bool(passed)}

def assertion_probe(cases):
    from semantic_memory.store import SemanticStore
    from semantic_memory.project_scope import bind_project
    from semantic_memory.contracts import AccessPolicy,SourceScope,SourceEnvelope,TextSpan
    from semantic_memory.grants import enroll_grant,authorize
    from semantic_memory.chunks import index_source
    from semantic_memory.context_service import get_context
    from semantic_memory.search import resolve_source
    with tempfile.TemporaryDirectory() as tmp:
        store=SemanticStore(Path(tmp)/'assertions.sqlite')
        try:
            root='/synthetic/fresh-assertions/repo';b=bind_project(store,'assertions',root,'2026-10-01T00:00:00Z')
            app='com.microsoft.VSCode';policy=AccessPolicy(1,frozenset({app}),frozenset())
            for i,case in enumerate(cases):
                sid='fresh-'+str(i)
                store.ingest(SourceEnvelope(sid,'2026-10-10T10:00:00Z','fresh',app,root+'/'+sid+'.md',root,True,case['origin'],(TextSpan('visible',case['text']),),1),policy)
                index_source(store,sid)
            grant=enroll_grant(store,'fresh',[b.project_id],SourceScope(frozenset({app})));ctx=authorize(store,grant.id,b.project_id)
            packet=get_context(store,ctx,b.project_id,'2026-10-01T00:00:00Z','2026-11-01T00:00:00Z')
            emitted=list(packet.decisions)+list(packet.open_tasks)
            metrics=claim_metrics(emitted,[c['text'] for c in cases if c['kind']])
            expected={c['text']:c for c in cases};invalid=0
            for claim in emitted:
                case=expected[claim['statement']]
                if 'reason' in case and claim.get('reason')!=(case['reason'] or 'Reason not recorded'):invalid+=1
                for cid in claim['citations']:
                    source=resolve_source(store,ctx,b.project_id,cid)
                    if source is None or claim['statement'] not in source.text:invalid+=1
            metrics.update(fresh_cases=len(cases),invalid_reasons_or_citations=invalid,experimental_model_claims_enabled=False)
            metrics['passed']=metrics['passed'] and invalid==0
            return metrics
        finally:store.close()

def probe(manifest,chunks,idle_seconds):
    from semantic_memory.model_setup import OwnedEmbeddingRuntime
    from semantic_memory.embedding_runtime import load_backend
    from semantic_memory.store import SemanticStore
    from semantic_memory.project_scope import bind_project
    from semantic_memory.contracts import AccessPolicy,SourceScope,SourceEnvelope,TextSpan
    from semantic_memory.api_contracts import Query
    from semantic_memory.grants import enroll_grant,authorize
    from semantic_memory.chunks import index_source
    from semantic_memory.search import search_project
    from semantic_memory.vector_index import begin_generation,activate_generation
    runtime=OwnedEmbeddingRuntime(Path(manifest.weights_path).parents[4]);runtime.ensure()
    try:
        backend=load_backend(manifest);vector=backend.embed(('SQLite migration rollback',),query=False)[0]
        with tempfile.TemporaryDirectory() as tmp:
            store=SemanticStore(Path(tmp)/'memory.sqlite')
            try:
                root='/synthetic/resource/repo';binding=bind_project(store,'stress',root,'2026-10-01T00:00:00Z')
                app='com.microsoft.VSCode';policy=AccessPolicy(1,frozenset({app}),frozenset())
                # Actual retained sources/chunks; vectors are duplicated on purpose to
                # isolate bounded scoring overhead, not retrieval quality.
                started=time.monotonic()
                for i in range(chunks):
                    sid='stress-'+str(i)
                    store.ingest(SourceEnvelope(sid,'2026-10-10T10:00:00Z','stress',app,root+'/a.py',root,True,'observed_screen_text',(TextSpan('visible',f'SQLite migration rollback record {i}'),),1),policy)
                    index_source(store,sid)
                gid=begin_generation(store,manifest)
                with store.transaction() as c:
                    c.execute('INSERT INTO chunk_vectors SELECT id,?,? FROM memory_chunks',(gid,vector.astype(np.float32).tobytes()))
                    c.execute("UPDATE index_jobs SET state='done'")
                activate_generation(store,gid)
                grant=enroll_grant(store,'stress',[binding.project_id],SourceScope(frozenset({app})))
                ctx=authorize(store,grant.id,binding.project_id);query=Query(binding.project_id,'migration rollback')
                times=[]
                for _ in range(12):
                    t=time.perf_counter();result=search_project(store,backend,ctx,query);times.append(time.perf_counter()-t)
                cpu=time.process_time();t=time.monotonic();time.sleep(idle_seconds)
                idle=(time.process_time()-cpu)/(time.monotonic()-t)*100
                return {'kind':'synthetic full hybrid search probe; not paired native acceptance','authorized_chunks':chunks,'loaded_model':True,
                        'build_seconds':time.monotonic()-started-idle_seconds,'warm_p95_seconds':float(np.percentile(times[2:],95)),
                        'warm_search_seconds':times,'primary_count':len(result.primary),'nonmodel_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        'idle_seconds':idle_seconds,'probe_idle_cpu_percent':idle,'db_bytes':store.path.stat().st_size,
                        'limitations':['duplicated document vectors isolate index cost','no paired native baseline','runtime RSS and energy not measured','not the 30-minute representative workload']}
            finally:store.close()
    finally:runtime.close()

def main():
    from semantic_memory.api_contracts import ModelManifest
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--chunks',type=int,default=10000);p.add_argument('--idle-seconds',type=float,default=60)
    a=p.parse_args();result=probe(ModelManifest(**json.loads(a.manifest.read_text())),a.chunks,a.idle_seconds)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
