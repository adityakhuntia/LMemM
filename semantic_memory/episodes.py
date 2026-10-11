"""Persisted episode boundaries; unchanging content does not schedule inference."""
import json
from datetime import datetime
from .contracts import EpisodeRequest
from .policy import identifier, utc

class EpisodeBuilder:
    def __init__(self, store):
        self.store = store

    def _active(self):
        return self.store.connection.execute("SELECT * FROM episodes WHERE status='active' ORDER BY started DESC LIMIT 1").fetchone()

    def _close(self, c, row, reason):
        c.execute("UPDATE episodes SET status='unprocessed',reason=? WHERE id=?", (reason,row['id']))
        return row['id']

    def accept(self, source_id):
        s = self.store.connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if s is None:
            raise ValueError("Unknown source")
        closed=[]
        with self.store.transaction() as c:
            key = "accepted:" + source_id
            if c.execute("SELECT 1 FROM meta WHERE key=?", (key,)).fetchone():
                return []
            active = self._active()
            if active:
                delta=(datetime.fromisoformat(s['at'])-datetime.fromisoformat(active['ended'])).total_seconds()
                if delta < 0:
                    raise ValueError("Out of order source")
                if active['artifact_id'] != s['artifact_id'] or s['artifact_id'] is None or active['revision'] != s['revision'] or delta >= 300:
                    closed.append(self._close(c,active,'context_boundary'))
                    active=None
                elif (datetime.fromisoformat(s['at'])-datetime.fromisoformat(active['started'])).total_seconds() >= 120:
                    closed.append(self._close(c,active,'duration'))
                    active=None
            rows=c.execute("SELECT o.id,b.text,b.normalized_hash,o.truncated FROM occurrences o JOIN blobs b ON o.blob_id=b.id WHERE o.source_id=? ORDER BY o.rowid",(source_id,)).fetchall()
            for row in rows:
                # Repeated content is deduplicated only within an artifact episode.
                if active and c.execute("SELECT 1 FROM episode_evidence e JOIN occurrences o ON o.id=e.occurrence_id JOIN blobs b ON b.id=o.blob_id WHERE e.episode_id=? AND b.normalized_hash=?",(active['id'],row['normalized_hash'])).fetchone():
                    continue
                if active is None:
                    eid=identifier('episode',source_id+'|'+row['id'])
                    c.execute("INSERT INTO episodes(id,artifact_id,started,ended,status,revision) VALUES(?,?,?,?,?,?)",(eid,s['artifact_id'],s['at'],s['at'],'active',s['revision']))
                    active=c.execute("SELECT * FROM episodes WHERE id=?",(eid,)).fetchone()
                c.execute("INSERT INTO episode_evidence VALUES(?,?)",(active['id'],row['id']))
                c.execute("UPDATE episodes SET ended=?,truncated=max(truncated,?) WHERE id=?",(s['at'],row['truncated'],active['id']))
                size=c.execute("SELECT coalesce(sum(length(CAST(b.text AS BLOB))),0) FROM episode_evidence e JOIN occurrences o ON o.id=e.occurrence_id JOIN blobs b ON b.id=o.blob_id WHERE e.episode_id=?",(active['id'],)).fetchone()[0]
                if size >= 16384:
                    closed.append(self._close(c,active,'bytes'))
                    active=None
            if active:
                c.execute("UPDATE episodes SET ended=? WHERE id=?",(s['at'],active['id']))
            c.execute("INSERT INTO meta VALUES(?,?)",(key,'1'))
        return closed

    def boundary(self, reason, at):
        utc(at)
        with self.store.transaction() as c:
            active=self._active()
            return [self._close(c,active,reason)] if active else []

    def flush(self, at):
        now=datetime.fromisoformat(utc(at))
        active=self._active()
        if active and (now-datetime.fromisoformat(active['started'])).total_seconds()>=120:
            return self.boundary('duration',at)
        return []

def build_request(store, episode_id, candidate_limit=8):
    if not 0 <= candidate_limit <= 8:
        raise ValueError("Invalid candidate bound")
    row=store.connection.execute("SELECT * FROM episodes WHERE id=?",(episode_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown episode")
    ids=[r[0] for r in store.connection.execute("SELECT occurrence_id FROM episode_evidence WHERE episode_id=? ORDER BY rowid",(episode_id,))]
    evidence=[]; used=0; truncated=bool(row['truncated'])
    for e in store.evidence(ids):
        remaining=16384-used
        if remaining<=0:
            truncated=True
            break
        raw=e['text'].encode()
        text=raw[:remaining].decode('utf-8',errors='ignore')
        evidence.append(dict(e,text=text,truncated=bool(e['truncated']) or len(raw)>remaining))
        used+=len(text.encode())
    # Anchored local projects nearest this episode, then retained project records.
    projects=store.connection.execute("SELECT p.id,p.locator,max(s.at) latest FROM projects p LEFT JOIN sources s ON s.project_id=p.id GROUP BY p.id ORDER BY latest DESC LIMIT ?",(candidate_limit,)).fetchall()
    candidates=tuple({'id':p['id'],'locator':p['locator'][:512],
                      'claims':[dict(r,statement=r['statement'][:160]) for r in store.connection.execute('SELECT id,kind,statement FROM claims WHERE project_id=? AND at<=? ORDER BY at DESC LIMIT 4',(p['id'],row['ended']))]}
                     for p in projects)
    revision=store.connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
    return EpisodeRequest(episode_id,tuple(evidence),candidates,int(revision[0]) if revision else row['revision'],truncated)
