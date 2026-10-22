"""User-directed sources, independent of editor and filesystem identity."""
import hashlib
import json
import re
from datetime import datetime, timezone
from .api_contracts import valid_id
from .policy import identifier, origin, utc
from .index_worker import paused, schedule_source
from .grants import bump_revision

NATIVE_APP = 'com.lmemm.intentional'
BROWSER_APP = 'com.lmemm.browser'
BROWSER_SCOPE = 'lmemm:explicit-browser-saves'
KINDS = {'native_note','pasted_excerpt','browser_selection','browser_page'}


def _project(c, project_id):
    valid_id(project_id)
    row = c.execute('SELECT * FROM project_bindings WHERE project_id=? AND active=1', (project_id,)).fetchone()
    if not row: raise ValueError('Project unavailable')
    return row


def _payload(payload):
    if not isinstance(payload, dict) or set(payload) - {'request_id','kind','text','title','url','truncated'}:
        raise ValueError('Invalid saved source')
    p = dict(payload)
    valid_id(p.get('request_id'))
    if p.get('kind') not in KINDS: raise ValueError('Unsupported saved source')
    for field, limit in (('text',131072),('title',512),('url',8192)):
        value = p.get(field, '' if field != 'url' else None)
        if value is None and field == 'url': continue
        if not isinstance(value,str) or '\x00' in value or (len(value.encode()) if field=='text' else len(value)) > limit:
            raise ValueError('Invalid '+field)
    if not p.get('text','').strip(): raise ValueError('Save some text first')
    p.setdefault('title','');p.setdefault('url',None);p.setdefault('truncated',False)
    if type(p['truncated']) is not bool: raise ValueError('Invalid truncation flag')
    if p['url']: origin(p['url'])
    if p['kind'].startswith('browser_') and not p['url']: raise ValueError('Browser save requires a URL')
    return p


def save_intentional(store, project_id, payload, *, owner='native', at=None):
    """Caller authenticates owner; retries cannot resurrect a deleted snapshot."""
    p = _payload(payload);valid_id(owner)
    digest = hashlib.sha256(json.dumps([project_id,p,owner],sort_keys=True).encode()).hexdigest()
    request = identifier('save',owner+'|'+p['request_id'])
    sid = identifier('saved-source',request)
    at = utc(at or datetime.now(timezone.utc).isoformat())
    with store.lock:
        with store.transaction() as c:
            binding = _project(c,project_id)
            if paused(store): raise ValueError('Memory is paused')
            prior = c.execute('SELECT * FROM save_receipts WHERE request_id=?',(request,)).fetchone()
            if prior:
                if prior['digest'] != digest: raise ValueError('Conflicting save retry')
                source = c.execute('SELECT project_id FROM sources WHERE id=?',(prior['source_id'],)).fetchone()
                if not source: raise ValueError('Saved source was removed')
                result = {'source_id':prior['source_id'],'project_id':source[0],'duplicate':True}
            else:
                if at < binding['enrolled_at']: raise ValueError('Source predates project enrollment')
                from .retention import semantic_bytes
                limit = c.execute("SELECT value FROM meta WHERE key='semantic_limit'").fetchone()
                if semantic_bytes(store) + 65536 + len(p['text'].encode())*4 > (int(limit[0]) if limit else 250*1024*1024):
                    raise ValueError('Memory storage budget reached')
                browser = p['kind'].startswith('browser_')
                app = BROWSER_APP if browser else NATIVE_APP
                kind = 'user_note' if p['kind']=='native_note' else p['kind']
                aid = identifier('artifact',sid)
                locator = p['url'] or 'lmemm-note:'+sid
                c.execute('INSERT INTO artifacts VALUES(?,?,?)',(aid,locator,project_id))
                c.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,0)',
                    (sid,digest,at,'native-notes' if p['kind']=='native_note' else 'intentional',app,
                     origin(p['url']) if browser else None,aid,project_id,kind,1))
                blob = identifier('blob',p['text']);oid = identifier('evidence',sid+'|saved')
                if c.execute('INSERT OR IGNORE INTO blobs VALUES(?,?,?)',
                             (blob,p['text'],identifier('normal',' '.join(p['text'].split())))).rowcount:
                    c.execute('INSERT INTO evidence_search VALUES(?,?)',(blob,p['text']))
                c.execute('INSERT INTO occurrences VALUES(?,?,?,?,?)',(oid,sid,blob,'saved',int(p['truncated'])))
                c.execute('INSERT INTO source_details VALUES(?,?,?,?,?)',(sid,p['title'],p['url'],p['kind'],owner))
                c.execute('INSERT INTO save_receipts VALUES(?,?,?,?)',(request,digest,sid,project_id))
                bump_revision(c)
                result = {'source_id':sid,'project_id':project_id,'duplicate':False}
        schedule_source(store,sid)
        return result


def move_saved_source(store, source_id, project_id):
    with store.lock:
        with store.transaction() as c:
            _project(c,project_id)
            source = c.execute('SELECT s.* FROM sources s JOIN source_details d ON d.source_id=s.id WHERE s.id=?',(source_id,)).fetchone()
            if not source: raise ValueError('Saved source unavailable')
            _project(c,source['project_id'])
            if source['project_id']==project_id: return {'source_id':source_id,'project_id':project_id}
            aid=source['artifact_id']
            entities={r[0] for r in c.execute('SELECT entity_id FROM support WHERE occurrence_id IN (SELECT id FROM occurrences WHERE source_id=?)',(source_id,))}
            for eid in entities:
                c.execute('UPDATE claims SET project_id=? WHERE id=?',(project_id,eid))
            # Project membership and cross-source relations cannot cross ownership.
            edges=[r[0] for r in c.execute('SELECT id FROM edges WHERE subject_id=? OR object_id=?',(aid,aid))]
            for eid in edges:
                c.execute('DELETE FROM support WHERE entity_id=?',(eid,))
                c.execute('DELETE FROM edges WHERE id=?',(eid,))
            c.execute('UPDATE sources SET project_id=? WHERE id=?',(project_id,source_id))
            c.execute('UPDATE artifacts SET project_id=? WHERE id=?',(project_id,aid))
            bump_revision(c)
        schedule_source(store,source_id)
        return {'source_id':source_id,'project_id':project_id}


def delete_saved_source(store, source_id):
    with store.lock:
        if not store.connection.execute('SELECT 1 FROM sources WHERE id=?',(source_id,)).fetchone():
            raise ValueError('Saved source unavailable')
        from .retention import delete_sources
        return {'removed':delete_sources(store,{source_id},forget=True).sources}


def record_claim(store, project_id, source_id, kind, start, end, reason_span=None):
    if kind not in {'task','decision'}: raise ValueError('Choose task or decision')
    with store.transaction() as c:
        _project(c,project_id)
        row=c.execute('SELECT o.id,b.text,s.at,s.artifact_id FROM occurrences o JOIN blobs b ON b.id=o.blob_id JOIN sources s ON s.id=o.source_id WHERE s.id=? AND s.project_id=?',(source_id,project_id)).fetchone()
        if not row: raise ValueError('Source unavailable')
        def span(a,b):
            if type(a) is not int or type(b) is not int or not 0<=a<b<=len(row['text']): raise ValueError('Invalid evidence span')
            return row['text'][a:b]
        statement=span(start,end);reason=span(*reason_span) if reason_span else None
        cid=identifier('claim',source_id+'|'+kind+'|'+str(start)+'|'+str(end))
        c.execute('INSERT OR IGNORE INTO claims VALUES(?,NULL,?,?,?,?,?,?,?)',(cid,project_id,kind,statement,'user_asserted','open' if kind=='task' else None,row['at'],reason))
        from .relationships import _support,_edge
        _support(c,cid,[row['id']],None,'user_recorded')
        _edge(c,cid,row['artifact_id'],'supports','user_asserted',row['at'],[row['id']],None,'user_recorded')
        bump_revision(c)
        return {'id':cid,'statement':statement,'reason':reason}


def remove_relationship(store, project_id, edge_id):
    with store.transaction() as c:
        _project(c,project_id)
        edge=c.execute("SELECT e.* FROM edges e JOIN artifacts a ON a.id=e.subject_id WHERE e.id=? AND a.project_id=? AND e.kind='references'",(edge_id,project_id)).fetchone()
        if not edge: raise ValueError('Relationship unavailable')
        correction=identifier('correction','remove-reference|'+edge_id)
        c.execute('INSERT OR IGNORE INTO corrections VALUES(?,?,?,?,?,?)',(correction,'remove_reference',edge['subject_id'],edge['object_id'],datetime.now(timezone.utc).isoformat(),'{}'))
        c.execute('DELETE FROM support WHERE entity_id=?',(edge_id,))
        c.execute('DELETE FROM edges WHERE id=?',(edge_id,))
        bump_revision(c)
