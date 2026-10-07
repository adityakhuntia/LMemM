"""Untrusted model JSON is validated before relationship policy sees it."""
import json
import threading
from .contracts import ExtractionResult, JobResult

CLAIM_TYPES={"observation","decision","suggestion","task"}
EDGE_TYPES={"belongs_to","references","supports","supersedes","contradicts"}

def validate_extraction(payload, request):
    if not isinstance(payload,str) or len(payload.encode())>32768:
        raise ValueError("Oversized extraction")
    try: doc=json.loads(payload)
    except (ValueError,TypeError): raise ValueError("Invalid extraction JSON") from None
    if not isinstance(doc,dict) or set(doc)!={'candidates'} or not isinstance(doc['candidates'],list) or len(doc['candidates'])>24:
        raise ValueError("Invalid extraction envelope")
    evidence={e['id']:e for e in request.evidence}
    entities={v for e in request.evidence for v in (e.get('artifact_id'),e.get('project_id')) if v}
    entities.update(c['id'] for c in request.candidates)
    result=[]
    allowed={'type','subject_id','object_id','evidence_ids','statement','extraction_status','reason'}
    for candidate in doc['candidates']:
        if not isinstance(candidate,dict) or set(candidate)-allowed or not {'type','subject_id','evidence_ids','statement','extraction_status'}<=set(candidate):
            raise ValueError("Invalid candidate fields")
        if candidate['type'] not in CLAIM_TYPES|EDGE_TYPES or candidate['subject_id'] not in entities:
            raise ValueError("Unsupported candidate type or subject")
        if candidate.get('object_id') is not None and candidate['object_id'] not in entities:
            raise ValueError("Unknown object")
        if candidate['type'] in EDGE_TYPES and not candidate.get('object_id'):
            raise ValueError("Relationship requires object")
        refs=candidate['evidence_ids']
        if not isinstance(refs,list) or not refs or len(refs)>16 or any(not isinstance(r,str) or r not in evidence for r in refs):
            raise ValueError("Unknown evidence")
        if candidate['extraction_status'] not in {'observed','inferred','explicit'}:
            raise ValueError("Invalid extraction status")
        for name,limit in (('statement',1024),('reason',512)):
            value=candidate.get(name,'')
            if not isinstance(value,str) or len(value.encode())>limit:
                raise ValueError("Oversized candidate field")
        if not candidate['statement'].strip():
            raise ValueError("Empty statement")
        result.append(dict(candidate,evidence_ids=list(dict.fromkeys(refs))))
    return ExtractionResult(tuple(result))

class InferenceWorker:
    def __init__(self,store,extractor):
        self.store=store; self.extractor=extractor; self.guard=threading.Lock()
        with store.transaction() as c:
            c.execute("UPDATE jobs SET status='unprocessed',error='interrupted' WHERE status='running'")
    def enqueue(self,episode_id):
        from .episodes import build_request
        request=build_request(self.store,episode_id)
        if not request.evidence:
            return False
        size=sum(len(e['text'].encode()) for e in request.evidence)
        with self.store.transaction() as c:
            queued=c.execute("SELECT count(*),coalesce(sum(bytes),0) FROM jobs WHERE status IN ('queued','running')").fetchone()
            if queued[0]>=8 or queued[1]+size>131072 or c.execute("SELECT 1 FROM jobs WHERE episode_id=?",(episode_id,)).fetchone():
                return False
            c.execute("INSERT INTO jobs(episode_id,status,bytes) VALUES(?,'queued',?)",(episode_id,size))
            return True
    def status(self):
        return dict(self.store.connection.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall())
    def cancel_scope(self,scope):
        self.extractor.cancel()
        with self.store.transaction() as c:
            c.execute("UPDATE jobs SET status='cancelled',error='scope boundary' WHERE status IN ('queued','running')")
    def run_one(self):
        from .episodes import build_request
        if not self.guard.acquire(blocking=False):
            return None
        try:
            with self.store.transaction() as c:
                row=c.execute("SELECT episode_id FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
                if not row: return None
                eid=row[0]
                c.execute("UPDATE jobs SET status='running' WHERE episode_id=?",(eid,))
            request=build_request(self.store,eid)
            result=None
            for attempt in range(1,3):
                try:
                    result=validate_extraction(self.extractor.extract(request),request)
                    break
                except (ValueError,TimeoutError,RuntimeError):
                    pass
            status='processed' if result is not None else 'unprocessed'
            with self.store.transaction() as c:
                revision=int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
                job=c.execute("SELECT status FROM jobs WHERE episode_id=?",(eid,)).fetchone()
                if not job or job[0]!='running' or revision!=request.revision:
                    status='cancelled'
                elif result is not None:
                    # Relationship implementation runs inside this transaction.
                    from .relationships import apply_extraction_in_transaction
                    apply_extraction_in_transaction(self.store,eid,result,request)
                c.execute("UPDATE jobs SET status=?,attempts=?,error=? WHERE episode_id=?",(status,attempt,None if status=='processed' else status,eid))
                c.execute("UPDATE episodes SET status=? WHERE id=?",(status,eid))
            return JobResult(eid,status,attempt)
        finally: self.guard.release()

