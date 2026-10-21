"""Versioned SQLite vectors, scored in bounded batches after SQL authorization."""
import dataclasses
import heapq
import json
import secrets
from datetime import datetime,timezone
import numpy as np
from .api_contracts import ModelManifest
from .grants import current_grant
from .search import JOINS,scope_filter,hit


def active_generation(store):
    with store.lock:
        row=store.connection.execute("SELECT * FROM index_generations WHERE state='active'").fetchone()
        return dict(row) if row else None


def begin_generation(store,manifest):
    gid='index-'+secrets.token_hex(12)
    with store.transaction() as c:
        # Retain prior vectors until successful activation, but never serve them
        # while a new model/chunk version is rebuilding.
        c.execute("UPDATE index_generations SET state='retired' WHERE state='active'")
        c.execute("DELETE FROM index_generations WHERE state='building'")
        c.execute('INSERT INTO index_generations VALUES(?,?,?,?)',(gid,json.dumps(dataclasses.asdict(manifest),sort_keys=True),'building',datetime.now(timezone.utc).isoformat()))
        c.execute('DELETE FROM index_jobs')
        c.execute("INSERT INTO index_jobs(source_id,generation_id,state) SELECT s.id,?,'queued' FROM sources s JOIN project_bindings p ON p.project_id=s.project_id WHERE p.active=1 AND s.at>=p.enrolled_at AND (s.origin IS NULL OR EXISTS(SELECT 1 FROM source_details sd WHERE sd.source_id=s.id AND sd.kind IN ('browser_page','browser_selection')))",(gid,))
    return gid


def activate_generation(store,generation_id):
    with store.transaction() as c:
        row=c.execute('SELECT * FROM index_generations WHERE id=?',(generation_id,)).fetchone()
        if not row or row['state'] not in {'building','active'}:raise ValueError('Incomplete index generation')
        if c.execute("SELECT 1 FROM index_jobs WHERE generation_id=? AND state!='done'",(generation_id,)).fetchone():raise ValueError('Incomplete index generation')
        missing=c.execute('''SELECT 1 FROM memory_chunks c JOIN occurrences o ON o.id=c.occurrence_id
            JOIN sources s ON s.id=o.source_id JOIN project_bindings p ON p.project_id=s.project_id
            WHERE p.active=1 AND s.at>=p.enrolled_at AND (s.origin IS NULL OR EXISTS(SELECT 1 FROM source_details sd WHERE sd.source_id=s.id AND sd.kind IN ('browser_page','browser_selection'))) AND NOT EXISTS
            (SELECT 1 FROM chunk_vectors v WHERE v.chunk_id=c.id AND v.generation_id=?) LIMIT 1''',(generation_id,)).fetchone()
        if missing:raise ValueError('Incomplete index generation')
        c.execute("UPDATE index_generations SET state='active' WHERE id=?",(generation_id,))
        c.execute('DELETE FROM index_generations WHERE id!=?',(generation_id,))


def vector_candidates(store,ctx,query,query_vector,limit=50):
    if type(limit) is not int or not 1<=limit<=50:raise ValueError('Invalid candidate limit')
    with store.lock:
        where,args=scope_filter(store,ctx,query)
        generation=active_generation(store)
        if generation is None:return []
        manifest=ModelManifest(**json.loads(generation['manifest']))
        q=np.asarray(query_vector,dtype=np.float32)
        if q.shape!=(manifest.dimension,) or not np.isfinite(q).all() or np.linalg.norm(q)<=0:raise ValueError('Invalid query vector')
        q=q/np.linalg.norm(q)
        cursor=store.connection.execute('''SELECT c.*,s.artifact_id,a.locator,s.at,s.origin_type,o.truncated,v.vector
            FROM memory_chunks c '''+JOINS+''' JOIN chunk_vectors v ON v.chunk_id=c.id
            WHERE v.generation_id=? AND '''+where+' ORDER BY c.id',[generation['id'],*args])
        top=[]
        while rows:=cursor.fetchmany(128):
            valid=[];vectors=[]
            for row in rows:
                v=np.frombuffer(row['vector'],dtype=np.float32)
                if v.shape!=(manifest.dimension,) or not np.isfinite(v).all() or not np.isclose(np.linalg.norm(v),1,atol=1e-4):
                    raise ValueError('Corrupt index vector')
                valid.append(row);vectors.append(v)
            scores=np.asarray(vectors,dtype=np.float32)@q
            for row,score in zip(valid,scores):
                item=(float(score),row['at'],row['id'],row)
                if len(top)<limit:heapq.heappush(top,item)
                elif item[:3]>top[0][:3]:heapq.heapreplace(top,item)
        current_grant(store,ctx,query.project_id)
        return [hit(row,score) for score,_,_,row in sorted(top,reverse=True)]
