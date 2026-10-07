"""Reproducible synthetic evaluation; injected outputs are never a semantic pass."""
import dataclasses
import json
import math
import resource
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from .contracts import AccessPolicy,SourceEnvelope,TextSpan,SourceScope
from .store import SemanticStore
from .episodes import EpisodeBuilder,build_request
from .inference import validate_extraction
from .relationships import apply_extraction
from .retrieval import project_context,resolve_citation
from .retention import semantic_bytes,delete_sources,revoke_scope
from .scoring import score_assertions

def load_fixture_manifest(path):
    doc=json.loads(Path(path).read_text())
    ids=[c['id'] for c in doc['cases']]
    if len(ids)!=len(set(ids)) or len(ids)<20 or set(doc['development'])&set(doc['heldout']) or set(ids)!=set(doc['development'])|set(doc['heldout']) or len(doc['heldout'])<math.ceil(len(ids)/3):
        raise ValueError("Invalid labelled corpus split")
    if doc.get('version')==2:
        for case in doc['cases']:
            if not isinstance(case.get('gold'),list) or 'membership' not in case:
                raise ValueError('Missing assertion labels')
            for gold in case['gold']:
                if gold.get('kind') not in {'decision','task','observation','suggestion'} or not isinstance(gold.get('statement'),str) or not gold['statement']:
                    raise ValueError('Invalid assertion label')
    return doc

def _privacy_probes(db,projects,access):
    start,end='2026-10-07T00:00:00+00:00','2026-10-08T00:00:00+00:00'
    leaks=probes=0
    denied=SourceScope(frozenset())
    full=SourceScope(access.allowed_apps,access.allowed_origins)
    for project in projects:
        packet=project_context(db,project,start,end,denied);probes+=1
        if packet.citations or any((packet.recent_changes,packet.decisions,packet.open_tasks,packet.artifacts,packet.conflicts)):
            leaks+=1
        for section in (packet.unknowns,):
            if any(entry.get('citations') for entry in section):leaks+=1
    browser_ids={r[0] for r in db.connection.execute('SELECT o.id FROM occurrences o JOIN sources s ON s.id=o.source_id WHERE s.app_id=?',('com.apple.Safari',))}
    revoke_scope(db,SourceScope(frozenset({'com.apple.Safari'})),dataclasses.replace(access,revision=access.revision+1))
    for project in projects:
        packet=project_context(db,project,start,end,full);probes+=1
        if any(oid in browser_ids for oid in packet.citations):leaks+=1
    remaining={r[0] for r in db.connection.execute('SELECT id FROM sources')}
    delete_sources(db,remaining)
    for project in projects:
        packet=project_context(db,project,start,end,full);probes+=1
        if packet.citations or any((packet.recent_changes,packet.decisions,packet.open_tasks,packet.artifacts,packet.conflicts)):
            leaks+=1
        if any(entry.get('citations') for entry in packet.unknowns):leaks+=1
    for oid in browser_ids:
        probes+=1
        if resolve_citation(db,oid,full) is not None:leaks+=1
    return {'forbidden_source_leaks':leaks,'probes':probes,
            'scope':'empty caller scope, browser revocation, all-source deletion, citation resolution on the evaluated fixture store'}

def score_predictions(rows):
    tp=fp=fn=unsupported=0
    for row in rows:
        expected=set() if row['expected']=='none' else {row['expected']}
        predicted=set(row['predicted'])
        tp+=len(expected&predicted);fp+=len(predicted-expected);fn+=len(expected-predicted)
        unsupported+=len((predicted-expected)&{'decision','task_completion'})
    return {'claim_precision':tp/(tp+fp) if tp+fp else 0,'claim_recall':tp/(tp+fn) if tp+fn else 0,'unsupported_assertions':unsupported,
            'true_positive':tp,'false_positive':fp,'false_negative':fn}

def _rss():
    # Include isolated Ollama server/runner, not another user's existing instance.
    p=subprocess.run(['ps','-axo','pid,ppid,rss,command'],capture_output=True,text=True,check=True)
    rows=[]
    for line in p.stdout.splitlines()[1:]:
        values=line.strip().split(None,3)
        if len(values)==4:
            try:rows.append((int(values[0]),int(values[1]),int(values[2]),values[3]))
            except ValueError:pass
    roots={pid for pid,ppid,rss,cmd in rows if 'ollama serve' in cmd and str(pid)!=str(__import__('os').getpid())}
    # Root isolation is recorded from listener service by benchmark script.
    return rows

class ResourceSampler:
    def __init__(self):
        self.stop=threading.Event();self.peak_rss=0;self.peak_model_bytes=0
        proc=subprocess.run(['/usr/sbin/lsof','-tiTCP:11455','-sTCP:LISTEN'],capture_output=True,text=True)
        self.root=int(proc.stdout.strip()) if proc.stdout.strip().isdigit() else None
        self.thread=threading.Thread(target=self.sample,daemon=True)
    def sample(self):
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while not self.stop.wait(.2):
            rows=_rss();selected={self.root} if self.root else set()
            for _ in range(4):selected.update(pid for pid,ppid,rss,cmd in rows if ppid in selected)
            self.peak_rss=max(self.peak_rss,sum(rss*1024 for pid,ppid,rss,cmd in rows if pid in selected))
            try:
                with opener.open('http://127.0.0.1:11455/api/ps',timeout=1) as response:
                    doc=json.loads(response.read(65536))
                self.peak_model_bytes=max(self.peak_model_bytes,sum(m.get('size',0) for m in doc.get('models',[])))
            except (OSError,ValueError):pass
    def finish(self):
        self.stop.set();self.thread.join(3)
        return max(self.peak_rss,self.peak_model_bytes)

def evaluate(corpus,extractor,split,output=None,timing_repeats=1):
    if split not in {'development','heldout'}:raise ValueError('Unknown split')
    selected=[c for c in corpus['cases'] if c['id'] in corpus[split]]
    access=AccessPolicy(1,frozenset({'com.microsoft.VSCode','com.apple.Safari'}),frozenset({'https://docs.example.org'}))
    rows=[];latencies=[];peak_db=0;artifact_tp=artifact_fp=artifact_fn=0
    sampler=ResourceSampler();sampler.thread.start()
    with tempfile.TemporaryDirectory() as temp:
        db=SemanticStore(Path(temp)/'semantic.sqlite3')
        try:
            # Project anchors are structural, independent of test labels.
            for name in ('one','two'):
                db.ingest(SourceEnvelope('anchor-'+name,'2026-10-07T09:00:00+00:00','fixture','com.microsoft.VSCode','/projects/'+name+'/main.py','/projects/'+name,True,'trusted_artifact_snapshot',(TextSpan('x','Project '+name+' workspace.'),),1),access)
            for case in selected:
                is_browser=case['kind']=='browser';project=case['project']
                locator='https://docs.example.org/'+case['id'] if is_browser else '/projects/'+project+'/main.py'
                envelope=SourceEnvelope(case['id'],case['at'],'fixture','com.apple.Safari' if is_browser else 'com.microsoft.VSCode',
                    locator,None if is_browser else '/projects/'+project,True,'user_note' if case['kind']=='note' else 'observed_screen_text',
                    (TextSpan('text',case['text']),),1)
                ingest=db.ingest(envelope,access);builder=EpisodeBuilder(db);builder.accept(case['id'])
                eid=builder.boundary('fixture',case['at'])[0];request=build_request(db,eid)
                started=time.monotonic();error=None;predicted=[];payload=None
                try:
                    payload=extractor.extract(request)
                    result=validate_extraction(payload,request)
                    apply_extraction(db,eid,result)
                    predicted=[c['type'] for c in result.candidates]
                except Exception as exc:error=type(exc).__name__
                latencies.append(time.monotonic()-started)
                for _ in range(timing_repeats-1):
                    started=time.monotonic()
                    try:extractor.extract(request)
                    except (OSError,ValueError,RuntimeError):pass
                    latencies.append(time.monotonic()-started)
                correct_project=next(p['id'] for p in request.candidates if p['locator']=='/projects/'+project)
                edges=db.connection.execute("SELECT object_id FROM edges WHERE subject_id=? AND kind='belongs_to' AND status IN ('supported','user_asserted')",(ingest.artifact_id,)).fetchall()
                targets={r[0] for r in edges}
                expected=set() if case['expected']=='none' else {correct_project}
                artifact_tp+=len(targets&expected);artifact_fp+=len(targets-expected);artifact_fn+=len(expected-targets)
                asserted=[r['kind'] for r in db.connection.execute('SELECT kind FROM claims WHERE episode_id=? AND status IN (?,?)',(eid,'supported','user_asserted'))]
                assertions=[]
                for claim in db.connection.execute('SELECT * FROM claims WHERE episode_id=?',(eid,)):
                    refs=[r[0] for r in db.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(claim['id'],))]
                    assertions.append({'kind':claim['kind'],'statement':claim['statement'],'reason':claim['reason'],
                                       'task_state':claim['task_state'],'status':claim['status'],'citations':refs})
                rows.append({'gold':case.get('gold',[]),'evidence':{e['id']:e['text'] for e in request.evidence},'assertions':assertions,'id':case['id'],'expected':case['expected'],'predicted':predicted,'supported_claims':asserted,'error':error,'seconds':latencies[-1],'output':payload})
                peak_db=max(peak_db,semantic_bytes(db))
            metrics=score_predictions(rows)
            metrics.update(association_precision=artifact_tp/(artifact_tp+artifact_fp) if artifact_tp+artifact_fp else 0,
                           artifact_recall=artifact_tp/(artifact_tp+artifact_fn) if artifact_tp+artifact_fn else 0,
                           association_true_positive=artifact_tp,association_false_positive=artifact_fp,association_false_negative=artifact_fn)
            assertion_metrics=score_assertions(rows) if corpus.get('version')==2 else None
            privacy_metrics=_privacy_probes(db,[r[0] for r in db.connection.execute('SELECT id FROM projects')],access)
            # Semantic recall explicitly reported; an empty extractor cannot pass.
            quality_pass=metrics['association_precision']>=.95 and metrics['artifact_recall']>=.8 and metrics['claim_recall']>=.8 and metrics['unsupported_assertions']==0 and not any(r['error'] for r in rows)
            fixture_quality_pass=bool(assertion_metrics and assertion_metrics['claim_precision']>=.95 and assertion_metrics['claim_recall']>=.8 and assertion_metrics['unsupported_assertions']==0 and assertion_metrics['invalid_citations']==0 and assertion_metrics['invalid_grounding']==0 and privacy_metrics['forbidden_source_leaks']==0 and metrics['association_precision']>=.95 and metrics['artifact_recall']>=.8 and not any(r['error'] for r in rows))
            report={'corpus_version':corpus.get('version',1),'corpus_hash':__import__('hashlib').sha256(json.dumps(corpus,sort_keys=True).encode()).hexdigest(),
                    'assertion_metrics':assertion_metrics,'privacy_metrics':privacy_metrics,'fixture_quality_pass':fixture_quality_pass,'split':split,'synthetic_corpus':True,'actual_local_model':extractor.__class__.__module__=='semantic_memory.local_runtime',
                    'model':getattr(extractor,'model','injected'),'manifest_hash':getattr(extractor,'manifest_hash',None),'extractor_version':getattr(extractor,'version',None),'prompt_hash':getattr(extractor,'prompt_hash',None),
                    'metrics':metrics,'quality_pass':fixture_quality_pass and extractor.__class__.__module__=='semantic_memory.local_runtime','classification_gate_pass':quality_pass,'acceptance_incomplete':(['real-session representativeness','full enabled-worker resources'] if assertion_metrics is not None else ['proposition/reason accuracy','forbidden-source leakage']),'metric_scope':'metrics is candidate-type classification; assertion_metrics scores exact gold quote/reason/state and citations on stored claims; privacy_metrics probes evaluated-store boundaries','rows':rows,'latencies_seconds':latencies,'semantic_bytes':peak_db,
                    'python_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    'energy_metrics':'not measured','resource_pass':False,'selection_pass':False}
        finally:db.close()
    peak_runtime=sampler.finish()
    report['runtime_peak_bytes']=peak_runtime
    report['runtime_weight_hashes']=getattr(extractor,'weight_hashes',[])
    report['p95_seconds']=sorted(latencies)[max(0,math.ceil(.95*len(latencies))-1)] if latencies else None
    report['timing_samples']=len(latencies)
    report['idle_cpu_percent']=None
    report['resource_incomplete']=['60-second idle CPU sample']
    report['resource_partial_pass']=0<peak_runtime<=3*1024**3 and report['python_peak_rss_bytes']<=150*1024**2 and report['p95_seconds']<=30
    if output:
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(report,indent=2))
    return report

def benchmark(config,corpus):
    from .local_runtime import LocalRuntime
    return evaluate(corpus,LocalRuntime(config),'heldout')
