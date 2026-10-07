"""Scoped context packets, with citations to actual retained evidence."""
import dataclasses
import json
from .contracts import ContextPacket
from .policy import utc

def _allowed(e,scope):
    return e['app_id'] in scope.app_ids and (e.get('origin') is None or e['origin'] in scope.origins)

def resolve_citation(store,citation_id,scope):
    rows=store.evidence([citation_id])
    if not rows or not _allowed(rows[0],scope): return None
    e=rows[0]
    return {k:e[k] for k in ('id','source_id','at','text','app_id','artifact_id','origin_type','truncated')}

def project_context(store,project_id,start,end,scope):
    start,end=utc(start),utc(end)
    if start>end: raise ValueError('Invalid interval')
    if not store.connection.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone():
        raise ValueError('Unknown project')
    packet=ContextPacket(project_id,start,end)
    omitted=0
    for claim in store.connection.execute('SELECT * FROM claims WHERE project_id=? AND at<=? ORDER BY at DESC,id',(project_id,end)):
        if claim['kind']!='task' and claim['at']<start: continue
        rows=store.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(claim['id'],)).fetchall()
        citations=[]
        for row in rows:
            citation=resolve_citation(store,row[0],scope)
            if citation and citation['at']<=end and (claim['kind']=='task' or citation['at']>=start):
                citations.append(citation)
        if not citations: continue
        if len(packet.citations)>=40:
            omitted+=1;continue
        citations=citations[:40-len(packet.citations)]
        entry={'id':claim['id'],'statement':claim['statement'],'at':claim['at'],'status':claim['status'],
               'citations':[e['id'] for e in citations]}
        for e in citations: packet.citations[e['id']]=e
        kind=claim['kind']
        if claim['status']=='inferred':
            target=packet.unknowns
        elif kind=='decision':
            entry['reason']=claim['reason'] or 'Reason not recorded'
            target=packet.decisions
        elif kind=='task':
            correction=store.connection.execute("SELECT action FROM corrections WHERE subject_id=? AND action IN ('complete','reopen') AND at<=? ORDER BY at DESC,rowid DESC LIMIT 1",(claim['id'],end)).fetchone()
            if correction and correction[0]=='complete': continue
            target=packet.open_tasks
        else: target=packet.recent_changes
        if len(target)<20: target.append(entry)
        else: omitted+=1
    for artifact in store.connection.execute("SELECT a.* FROM artifacts a WHERE a.project_id=? OR a.id IN (SELECT subject_id FROM edges WHERE object_id=? AND kind='belongs_to' AND status IN ('supported','user_asserted'))",(project_id,project_id)):
        rows=store.connection.execute('SELECT o.id FROM occurrences o JOIN sources s ON s.id=o.source_id WHERE s.artifact_id=? AND s.at BETWEEN ? AND ?',(artifact['id'],start,end)).fetchall()
        permitted=[r[0] for r in rows if resolve_citation(store,r[0],scope)]
        if permitted and len(packet.artifacts)<20:
            packet.artifacts.append({'id':artifact['id'],'locator':artifact['locator'],'citations':permitted[:3]})
            for oid in permitted[:3]:
                if len(packet.citations)<40: packet.citations[oid]=resolve_citation(store,oid,scope)
    # Coverage counts are scoped; inaccessible source existence is not disclosed.
    evidence_count=0; unfinished=set(); truncated=False
    rows=store.connection.execute('SELECT o.id FROM occurrences o JOIN sources s ON s.id=o.source_id WHERE s.project_id=? AND s.at BETWEEN ? AND ?',(project_id,start,end))
    for row in rows:
        citation=resolve_citation(store,row[0],scope)
        if not citation: continue
        evidence_count+=1;truncated=truncated or bool(citation['truncated'])
        for episode in store.connection.execute("SELECT e.id,e.status FROM episodes e JOIN episode_evidence ee ON ee.episode_id=e.id WHERE ee.occurrence_id=?",(row[0],)):
            if episode['status']!='processed':unfinished.add(episode['id'])
    packet.coverage={'evidence_count':evidence_count,'unprocessed_episodes':len(unfinished),'truncated':truncated,'omitted_entries':omitted}
    if not evidence_count:packet.unknowns.append({'statement':'No permitted evidence in this interval'})
    return packet

def render_context(packet):
    doc=dataclasses.asdict(packet)
    # Citation text is resolved separately; context contains bounded source references.
    doc['citations']={k:{key:v[key] for key in ('id','at','source_id','truncated')} for k,v in packet.citations.items()}
    rendered=json.dumps(doc,ensure_ascii=False,indent=2)
    while len(rendered.encode())>16384:
        lists=[doc[k] for k in ('recent_changes','decisions','open_tasks','artifacts','conflicts','unknowns') if doc[k]]
        if not lists: break
        max(lists,key=len).pop()
        doc['coverage']['omitted_entries']+=1
        doc['coverage']['truncated']=True
        rendered=json.dumps(doc,ensure_ascii=False,indent=2)
    return rendered

