"""One deterministic resume composer for native Memory and read-only agents."""
import dataclasses
import json
from datetime import datetime,timedelta,timezone
from .api_contracts import Query,ContextResult
from .grants import current_grant
from .search import scope_filter,JOINS,hit,resolve_source


def time_bounds(start=None,end=None):
    end=end or datetime.now(timezone.utc).isoformat()
    query=Query('time-bounds','',start,end)
    end=query.end
    start=query.start or (datetime.fromisoformat(end)-timedelta(days=2)).isoformat()
    return start,end


def get_context(store,ctx,project_id,start=None,end=None):
    start,end=time_bounds(start,end)
    with store.lock:
        current_grant(store,ctx,project_id)
        citations={};decisions=[];tasks=[];conflicts=[];superseded=set()
        for edge in store.connection.execute("SELECT * FROM edges WHERE kind IN ('contradicts','supersedes') AND status IN ('supported','user_asserted') AND last_at<=? AND method!='task_transition'",(end,)):
            endpoints=store.connection.execute('SELECT project_id FROM claims WHERE id IN (?,?)',(edge['subject_id'],edge['object_id'])).fetchall()
            refs=[r[0] for r in store.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(edge['id'],))]
            details=[resolve_source(store,ctx,project_id,oid) for oid in refs]
            if len(endpoints)!=2 or any(r[0]!=project_id for r in endpoints) or not details or any(d is None or d.at>end for d in details):continue
            if edge['kind']=='supersedes':superseded.add(edge['object_id'])
            elif edge['last_at']>=start and len(conflicts)<10:
                conflicts.append({'kind':'contradicts','statement':'Retained evidence contains conflicting decisions','citations':refs})
                for d in details:citations[d.citation_id]=dataclasses.asdict(d)
        for claim in store.connection.execute("SELECT * FROM claims WHERE project_id=? AND status IN ('supported','user_asserted') AND at<=? ORDER BY at DESC,id",(project_id,end)):
            if claim['kind'] not in {'task','decision'} or claim['id'] in superseded:continue
            if claim['kind']!='task' and claim['at']<start:continue
            refs=[r[0] for r in store.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(claim['id'],))]
            details=[resolve_source(store,ctx,project_id,oid) for oid in refs]
            if not refs or any(d is None for d in details):continue
            details=[d for d in details if d.at<=end and (claim['kind']=='task' or d.at>=start)]
            if not details:continue
            # Every emitted assertion is grounded in a permitted intentional note.
            if not any(d.origin_type=='user_note' and claim['statement'] in d.text for d in details):continue
            if claim['kind']=='task':
                if claim['task_state']!='open':continue
                correction=store.connection.execute("SELECT action FROM corrections WHERE subject_id=? AND action IN ('complete','reopen') AND at<=? ORDER BY at DESC,rowid DESC LIMIT 1",(claim['id'],end)).fetchone()
                if correction and correction[0]=='complete':continue
                transitions=store.connection.execute("SELECT cl.* FROM edges e JOIN claims cl ON cl.id=e.subject_id WHERE e.object_id=? AND e.method='task_transition' AND cl.at<=? ORDER BY cl.at DESC,cl.id",(claim['id'],end)).fetchall()
                latest=None
                for transition in transitions:
                    tids=[r[0] for r in store.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(transition['id'],))]
                    if tids and all(resolve_source(store,ctx,project_id,t) for t in tids):latest=transition;break
                if not correction and latest and latest['task_state']=='completed':continue
            entry={'id':claim['id'],'statement':claim['statement'],'at':claim['at'],'citations':[d.citation_id for d in details]}
            if claim['kind']=='decision':entry['reason']=claim['reason'] or 'Reason not recorded'
            target=tasks if claim['kind']=='task' else decisions
            if len(target)>=10:continue
            target.append(entry)
            for detail in details:citations[detail.citation_id]=dataclasses.asdict(detail)
        query=Query(project_id,'',start,end);where,args=scope_filter(store,ctx,query)
        rows=store.connection.execute('''SELECT c.*,s.artifact_id,a.locator,s.at,s.origin_type,o.truncated FROM memory_chunks c '''+JOINS+'''
            WHERE '''+where+' ORDER BY s.at DESC,c.id LIMIT 10',args).fetchall()
        recent=[];seen=set()
        for row in rows:
            if row['occurrence_id'] in seen:continue
            seen.add(row['occurrence_id']);item=hit(row);recent.append(dataclasses.asdict(item))
            detail=resolve_source(store,ctx,project_id,item.citation_id)
            citations[item.citation_id]=dataclasses.asdict(detail)
        count=store.connection.execute('''SELECT count(DISTINCT o.id) FROM memory_chunks c '''+JOINS+' WHERE '+where,args).fetchone()[0]
        coverage={'evidence_count':count,'start':start,'end':end,'packet_truncated':False,'claims':'explicit supported intent only'}
        unknowns=tuple(conflicts) if count else tuple(conflicts)+({'statement':'No permitted evidence in this interval'},)
        current_grant(store,ctx,project_id)
        return ContextResult(project_id,ctx.policy_revision,start,end,tuple(decisions),tuple(tasks),tuple(recent),unknowns,citations,coverage)


def render_packet(result):
    """Trim whole entries/citations, never edit a retained quote to fit a packet."""
    doc=dataclasses.asdict(result) if dataclasses.is_dataclass(result) else json.loads(json.dumps(result))
    for key in ('decisions','open_tasks','recent_evidence','unknowns','primary','related'):
        if key in doc:doc[key]=list(doc[key])
    def encode():return json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    def prune_citations():
        if 'citations' not in doc:return
        used=set()
        for key in ('decisions','open_tasks','recent_evidence','unknowns'):
            for entry in doc.get(key,[]):
                used.update(entry.get('citations',[]))
                if 'citation_id' in entry:used.add(entry['citation_id'])
        doc['citations']={k:v for k,v in doc['citations'].items() if k in used}
    raw=encode()
    while len(raw)>16384:
        doc.setdefault('coverage',{})['packet_truncated']=True
        for key in ('related','recent_evidence','primary','decisions','open_tasks','unknowns'):
            if doc.get(key):doc[key].pop();break
        else:raise ValueError('Packet metadata exceeds limit')
        prune_citations();raw=encode()
    return raw


def serialize_authorized(store,ctx,result):
    """Final service output boundary; stale computed packets are never reusable."""
    with store.lock:
        current_grant(store,ctx,result.project_id)
        if result.policy_revision!=ctx.policy_revision:raise ValueError('unavailable')
        ids=set(getattr(result,'citations',{}))
        for item in (*getattr(result,'primary',()),*getattr(result,'related',())):ids.add(item.citation_id)
        for oid in ids:
            if resolve_source(store,ctx,result.project_id,oid) is None:raise ValueError('unavailable')
        raw=render_packet(result)
        current_grant(store,ctx,result.project_id)
        return raw
