"""Deletion, revocation and bounded retention share source ownership."""
from datetime import datetime, timedelta
from pathlib import Path
from .contracts import DeletionResult, BudgetStatus
from .policy import utc
from .relationships import recompute_support

def semantic_bytes(store):
    return sum(p.stat().st_size for p in (store.path,Path(str(store.path)+'-wal'),Path(str(store.path)+'-shm'),Path(str(store.path)+'-journal')) if p.exists())

def delete_sources(store,source_ids):
    source_ids=set(source_ids)
    if not source_ids: return DeletionResult(0,0)
    count=occurrences=0
    with store.transaction() as c:
        affected=set()
        for sid in source_ids:
            if not c.execute('SELECT 1 FROM sources WHERE id=?',(sid,)).fetchone(): continue
            count+=1
            affected.update(r[0] for r in c.execute('SELECT entity_id FROM support WHERE occurrence_id IN (SELECT id FROM occurrences WHERE source_id=?)',(sid,)))
            occurrences+=c.execute('SELECT count(*) FROM occurrences WHERE source_id=?',(sid,)).fetchone()[0]
            c.execute('INSERT OR IGNORE INTO tombstones VALUES(?)',(sid,))
            c.execute('DELETE FROM sources WHERE id=?',(sid,))
        recompute_support(store,affected)
        c.execute("DELETE FROM jobs WHERE episode_id IN (SELECT id FROM episodes WHERE NOT EXISTS(SELECT 1 FROM episode_evidence WHERE episode_id=episodes.id))")
        c.execute("DELETE FROM episodes WHERE NOT EXISTS(SELECT 1 FROM episode_evidence WHERE episode_id=episodes.id)")
        c.execute("DELETE FROM support WHERE entity_id NOT IN (SELECT id FROM claims) AND entity_id NOT IN (SELECT id FROM edges)")
        c.execute('DELETE FROM evidence_search WHERE blob_id IN (SELECT id FROM blobs WHERE NOT EXISTS(SELECT 1 FROM occurrences WHERE blob_id=blobs.id))')
        c.execute('DELETE FROM blobs WHERE NOT EXISTS(SELECT 1 FROM occurrences WHERE blob_id=blobs.id)')
        c.execute("UPDATE jobs SET status='cancelled',error='evidence removed' WHERE status IN ('queued','running')")
        if count:
            generation=c.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
            c.execute("INSERT OR REPLACE INTO meta VALUES('generation',?)",(str(int(generation[0])+1 if generation else 1),))
    return DeletionResult(count,occurrences)

def delete_session(store,session_id):
    ids={r[0] for r in store.connection.execute('SELECT id FROM sources WHERE session_id=?',(session_id,))}
    return delete_sources(store,ids)

def revoke_scope(store,scope,policy):
    ids=set()
    for s in store.connection.execute('SELECT id,app_id,origin FROM sources'):
        if s['app_id'] in scope.app_ids and (s['origin'] is None or not scope.origins or s['origin'] in scope.origins):
            ids.add(s['id'])
    # Revision barrier commits before any result can be accepted.
    with store.transaction() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES('revision',?)",(str(policy.revision),))
        c.execute("UPDATE jobs SET status='cancelled',error='scope revoked' WHERE status IN ('queued','running')")
    return delete_sources(store,ids)

def enforce_budget(store,now,raw_root=None,semantic_limit=250*1024*1024,raw_limit=500*1024*1024):
    if semantic_limit<=0 or raw_limit<=0: raise ValueError('Invalid budget')
    at=datetime.fromisoformat(utc(now)); cutoff=(at-timedelta(days=30)).isoformat()
    expired={r[0] for r in store.connection.execute('SELECT id FROM sources WHERE pinned=0 AND at<?',(cutoff,))}
    pruned=delete_sources(store,expired).sources
    if semantic_bytes(store)>semantic_limit:
        for row in store.connection.execute('SELECT id FROM sources WHERE pinned=0 ORDER BY at').fetchall():
            pruned+=delete_sources(store,{row[0]}).sources
            if semantic_bytes(store)<=semantic_limit: break
        with store.lock:
            store.connection.execute('VACUUM')
    raw_bytes=0
    if raw_root is not None:
        root=Path(raw_root)
        if root.resolve()!=(store.path.parent/'semantic_raw').resolve() or root.is_symlink():
            raise ValueError('Raw root must be dedicated semantic_raw directory')
        files=[]
        for p in root.glob('*') if root.exists() else []:
            if p.is_symlink() or not p.is_file(): continue
            if p.suffix not in {'.jpg','.json'}: continue
            if datetime.fromtimestamp(p.stat().st_mtime,at.tzinfo)<at-timedelta(hours=24):
                p.unlink()
            else: files.append(p)
        raw_bytes=sum(p.stat().st_size for p in files)
        for p in sorted(files,key=lambda f:f.stat().st_mtime):
            if raw_bytes<=raw_limit: break
            size=p.stat().st_size;p.unlink();raw_bytes-=size
    measured=semantic_bytes(store)
    reason='semantic_budget' if measured>semantic_limit else None
    with store.transaction() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES('paused',?)",(reason or '',))
        c.execute("INSERT OR REPLACE INTO meta VALUES('semantic_limit',?)",(str(semantic_limit),))
    return BudgetStatus(semantic_bytes(store),raw_bytes,pruned,reason)

