"""Source-backed policy separates observations from decisions and graph membership."""
import dataclasses
import json
import re
from .contracts import ApplyResult
from .episodes import build_request
from .policy import identifier, utc, references_project

def _support(c,eid,refs,episode,method):
    for oid in refs:
        sid=identifier('support',eid+'|'+oid+'|'+method)
        c.execute("INSERT OR IGNORE INTO support VALUES(?,?,?,?,?)",(sid,eid,oid,episode,method))

def _edge(c,subject,obj,kind,status,at,refs,episode,method):
    eid=identifier('edge',subject+'|'+obj+'|'+kind)
    prior=c.execute("SELECT status FROM edges WHERE id=?",(eid,)).fetchone()
    if prior and prior[0]=='user_asserted': status='user_asserted'
    c.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_at=excluded.last_at,status=CASE WHEN edges.status='supported' AND excluded.status='inferred' THEN edges.status ELSE excluded.status END",
              (eid,subject,obj,kind,status,method,at,at))
    _support(c,eid,refs,episode,method)
    return eid

def apply_extraction_in_transaction(store,episode_id,result,request):
    c=store.connection
    if int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])!=request.revision:
        raise ValueError("Stale extraction")
    evidence={e['id']:e for e in request.evidence}
    # Evidence existence is checked at commit, not just when inference started.
    if len(store.evidence(list(evidence)))!=len(evidence):
        raise ValueError("Evidence no longer available")
    claims=edges=0
    for e in evidence.values():
        if e['project_id'] and e['artifact_id']:
            _edge(c,e['artifact_id'],e['project_id'],'belongs_to','supported',e['at'],[e['id']],episode_id,'workspace')
    for candidate in result.candidates:
        refs=candidate['evidence_ids']
        selected=[evidence[r] for r in refs]
        subject=candidate['subject_id']; obj=candidate.get('object_id'); kind=candidate['type']
        at=max(e['at'] for e in selected)
        statement=candidate['statement']
        if kind in {'belongs_to','references','supports','supersedes','contradicts'}:
            rejected=c.execute("SELECT 1 FROM corrections WHERE subject_id=? AND object_id=? AND action IN ('reject','remove')",(subject,obj)).fetchone()
            if rejected: continue
            if kind=='belongs_to':
                project=c.execute("SELECT locator FROM projects WHERE id=?",(obj,)).fetchone()
                # Explicit path evidence is objective support, independent of model score.
                explicit=bool(project and any(references_project(e['text'],project[0]) for e in selected))
                status='supported' if explicit else 'inferred'
                method='explicit_reference' if explicit else 'semantic_candidate'
            else:
                status='inferred'; method='semantic_candidate'
            _edge(c,subject,obj,kind,status,at,refs,episode_id,method); edges+=1
            continue
        user_explicit=any(e['origin_type']=='user_note' for e in selected)
        texts=[e['text'] for e in selected if e['origin_type']=='user_note']
        grounded=any(' '.join(statement.split()).lower() in ' '.join(e['text'].split()).lower() for e in selected)
        status='supported' if grounded and kind in {'observation','suggestion'} else 'inferred'
        state=None
        if kind=='decision' and grounded and user_explicit and any(re.match(r"\s*(?:we|i)\s+(?:decided|chose|agreed|selected)\b",t,re.I) and statement.lower() in t.lower() for t in texts):
            status='supported'
        if kind=='task' and grounded and user_explicit and any(re.match(r"\s*(?:next task|todo|i will|we will)\b",t,re.I) and statement.lower() in t.lower() for t in texts):
            status='supported'; state='open'
        transition=candidate.get('task_state')
        if kind=='task' and transition in {'completed','reopened'} and obj:
            target=c.execute("SELECT * FROM claims WHERE id=? AND kind='task' AND task_state='open'",(obj,)).fetchone()
            pattern=r'\s*completed task\b' if transition=='completed' else r'\s*reopen task\b'
            target_text=target['statement'].split(':',1)[-1].strip().rstrip('.').lower() if target else ''
            if target and grounded and any(re.match(pattern,t,re.I) and target_text in t.lower() for t in texts):
                status='supported';state=transition
        reason=candidate.get('reason')
        if not reason or not any(reason.lower() in e['text'].lower() for e in selected):
            reason=None
        projects={e['project_id'] for e in selected if e['project_id']}
        if not projects:
            projects={r[0] for r in c.execute("SELECT object_id FROM edges WHERE subject_id=? AND kind='belongs_to' AND status IN ('supported','user_asserted')",(subject,))}
        # Avoid arbitrary assignment to one of multiple plausible projects.
        project=next(iter(projects)) if len(projects)==1 else None
        cid=identifier('claim',subject+'|'+kind+'|'+statement)
        c.execute("INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?,?,?,?,?)",(cid,episode_id,project,kind,statement,status,state,at,reason))
        _support(c,cid,refs,episode_id,'extraction'); claims+=1
        if state in {'completed','reopened'}:
            _edge(c,cid,obj,'supersedes','supported',at,refs,episode_id,'task_transition')
    return ApplyResult(claims,edges)

def apply_extraction(store,episode_id,result):
    request=build_request(store,episode_id)
    with store.transaction():
        return apply_extraction_in_transaction(store,episode_id,result,request)

def apply_correction(store,correction):
    if correction.actor!='user' or correction.action not in {'assign','reject','remove','complete','reopen'}:
        raise ValueError("Invalid correction")
    at=utc(correction.at)
    payload=json.dumps(dataclasses.asdict(correction),sort_keys=True)
    cid=identifier('correction',payload)
    with store.transaction() as c:
        if correction.action in {'complete','reopen'}:
            if not c.execute("SELECT 1 FROM claims WHERE id=? AND kind='task'",(correction.subject_id,)).fetchone():
                raise ValueError("Unknown task")
        else:
            if not c.execute("SELECT 1 FROM artifacts WHERE id=?",(correction.subject_id,)).fetchone() or not c.execute("SELECT 1 FROM projects WHERE id=?",(correction.object_id,)).fetchone():
                raise ValueError("Unknown correction entity")
        c.execute("INSERT OR IGNORE INTO corrections VALUES(?,?,?,?,?,?)",(cid,correction.action,correction.subject_id,correction.object_id,at,payload))
        if correction.action in {'reject','remove'}:
            c.execute("DELETE FROM support WHERE entity_id IN (SELECT id FROM edges WHERE subject_id=? AND object_id=?)",(correction.subject_id,correction.object_id))
            c.execute("DELETE FROM edges WHERE subject_id=? AND object_id=?",(correction.subject_id,correction.object_id))
        elif correction.action=='assign':
            _edge(c,correction.subject_id,correction.object_id,'belongs_to','user_asserted',at,[],None,'correction')
    return cid

def recompute_support(store,entity_ids):
    c=store.connection
    for eid in entity_ids:
        ids=[r[0] for r in c.execute("SELECT occurrence_id FROM support WHERE entity_id=?",(eid,))]
        evidence=store.evidence(ids)
        claim=c.execute('SELECT * FROM claims WHERE id=?',(eid,)).fetchone()
        if claim:
            # A surviving citation must independently ground the full claim;
            # partial public support cannot retain derived private text.
            grounded=any(claim['statement'].lower() in e['text'].lower() and
                         (claim['kind'] not in {'decision','task'} or e['origin_type']=='user_note')
                         and (not claim['reason'] or claim['reason'].lower() in e['text'].lower()) for e in evidence)
            if not grounded:c.execute('DELETE FROM claims WHERE id=?',(eid,))
        edge=c.execute('SELECT * FROM edges WHERE id=?',(eid,)).fetchone()
        if not edge or edge['status']=='user_asserted':continue
        if not evidence:c.execute('DELETE FROM edges WHERE id=?',(eid,));continue
        if edge['kind']=='belongs_to':
            project=c.execute('SELECT locator FROM projects WHERE id=?',(edge['object_id'],)).fetchone()
            strong=any(e['project_id']==edge['object_id'] or (project and references_project(e['text'],project[0])) for e in evidence)
            c.execute('UPDATE edges SET status=? WHERE id=?',('supported' if strong else 'inferred',eid))
