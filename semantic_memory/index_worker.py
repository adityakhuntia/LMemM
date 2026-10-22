"""ID-only durable indexing backlog; one model worker, bounded source payloads."""
import json
import sys
import numpy as np
from .api_contracts import ModelManifest
from .chunks import index_source
from .grants import revision
from .retention import semantic_bytes


def paused(store):
    return any(row[0] for row in store.connection.execute("SELECT value FROM meta WHERE key IN ('paused','memory_paused')"))


def schedule_source(store,source_id):
    index_source(store,source_id)
    with store.transaction() as c:
        generation=c.execute("SELECT id FROM index_generations WHERE state IN ('building','active') ORDER BY created_at DESC LIMIT 1").fetchone()
        if generation:
            c.execute("INSERT OR IGNORE INTO index_jobs(source_id,generation_id,state) VALUES(?,?,'queued')",(source_id,generation[0]))


class IndexWorker:
    def __init__(self,store,backend):self.store=store;self.backend=backend

    def run_one(self):
        with self.store.lock:
            if self.store.query_waiters:return False
        if not self.store.model_lock.acquire(blocking=False):return False
        try:return self._run()
        finally:self.store.model_lock.release()

    def _run(self):
        store=self.store
        with store.lock:
            if paused(store):return False
            c=store.connection
            job=c.execute("SELECT j.*,g.manifest FROM index_jobs j JOIN index_generations g ON g.id=j.generation_id WHERE j.state IN ('queued','running') AND g.state IN ('building','active') ORDER BY j.rowid LIMIT 1").fetchone()
            if not job:return False
            manifest=ModelManifest(**json.loads(job['manifest']))
            if manifest!=self.backend.manifest:raise ValueError('Embedding generation mismatch')
            source=c.execute('''SELECT s.* FROM sources s JOIN project_bindings p ON p.project_id=s.project_id
                WHERE s.id=? AND p.active=1 AND (s.at>=p.enrolled_at OR EXISTS(SELECT 1 FROM source_details d WHERE d.source_id=s.id)) AND (s.origin IS NULL OR EXISTS(SELECT 1 FROM source_details sd WHERE sd.source_id=s.id AND sd.kind IN ('browser_page','browser_selection'))) AND NOT EXISTS(SELECT 1 FROM tombstones t WHERE t.source_id=s.id)''',(job['source_id'],)).fetchone()
            if not source:
                with store.transaction() as tx:tx.execute('DELETE FROM index_jobs WHERE source_id=?',(job['source_id'],))
                return True
            index_source(store,job['source_id'])
            policy=revision(c);digest=source['digest']
            rows=c.execute('''SELECT ch.* FROM memory_chunks ch JOIN occurrences o ON o.id=ch.occurrence_id WHERE o.source_id=?
                AND NOT EXISTS(SELECT 1 FROM chunk_vectors v WHERE v.chunk_id=ch.id AND v.generation_id=?)
                ORDER BY ch.start_char,ch.id LIMIT 8''',(job['source_id'],job['generation_id'])).fetchall()
            if not rows:
                with store.transaction() as tx:tx.execute("UPDATE index_jobs SET state='done' WHERE source_id=?",(job['source_id'],))
                return True
            vectors={};needed={}
            for row in rows:
                cached=c.execute('''SELECT v.vector FROM chunk_vectors v JOIN memory_chunks ch ON ch.id=v.chunk_id
                    WHERE v.generation_id=? AND ch.text=? LIMIT 1''',(job['generation_id'],row['text'])).fetchone()
                if cached:vectors[row['text']]=np.frombuffer(cached[0],dtype=np.float32)
                else:needed[row['text']]=None
            with store.transaction() as tx:tx.execute("UPDATE index_jobs SET state='running',attempts=attempts+1 WHERE source_id=?",(job['source_id'],))
        try:
            if needed:
                matrix=self.backend.embed(tuple(needed),query=False)
                if matrix.shape!=(len(needed),manifest.dimension) or not np.isfinite(matrix).all() or not np.allclose(np.linalg.norm(matrix,axis=1),1,atol=1e-4):
                    raise ValueError('Invalid worker embedding')
                vectors.update(zip(needed,matrix))
            with store.transaction() as c:
                current=c.execute('SELECT digest FROM sources WHERE id=?',(job['source_id'],)).fetchone()
                still_current=c.execute("SELECT 1 FROM index_generations WHERE id=? AND state IN ('building','active')",(job['generation_id'],)).fetchone()
                if not current or current[0]!=digest or revision(c)!=policy or paused(store) or not still_current or c.execute('SELECT 1 FROM tombstones WHERE source_id=?',(job['source_id'],)).fetchone():
                    c.execute("UPDATE index_jobs SET state='queued' WHERE source_id=?",(job['source_id'],))
                    return True
                limit=c.execute("SELECT value FROM meta WHERE key='semantic_limit'").fetchone()
                if semantic_bytes(store)+65536+len(rows)*manifest.dimension*4>(int(limit[0]) if limit else 250*1024*1024):
                    raise ValueError('Semantic index quota')
                for row in rows:
                    vector=np.asarray(vectors[row['text']],dtype=np.float32).tobytes()
                    c.execute('INSERT OR REPLACE INTO chunk_vectors VALUES(?,?,?)',(row['id'],job['generation_id'],vector))
                c.execute("UPDATE index_jobs SET state='queued',error=NULL WHERE source_id=?",(job['source_id'],))
        except Exception as error:
            # Reason goes to the service's private log only; messages here are fixed strings, never source text.
            print('index job failed: %s: %s'%(type(error).__name__,str(error)[:200]),file=sys.stderr,flush=True)
            with store.transaction() as c:c.execute("UPDATE index_jobs SET state='failed',error='Local embedding failed' WHERE source_id=?",(job['source_id'],))
        return True
