"""Authorized evidence retrieval: filter ownership before ranking or LIMIT."""
import re
from pathlib import Path
from .api_contracts import EvidenceHit, SourceDetail
from .grants import current_grant

# Shared query fragment, used by keyword and vector paths. Caller holds store.lock.
JOINS = '''JOIN occurrences o ON o.id=c.occurrence_id
           JOIN sources s ON s.id=o.source_id
           JOIN artifacts a ON a.id=s.artifact_id
           JOIN project_bindings pb ON pb.project_id=s.project_id'''


def scope_filter(store,ctx,query):
    grant=current_grant(store,ctx,query.project_id)
    apps=sorted(grant.source_scope.app_ids)
    # MVP has local-file origins only, regardless of older experimental data.
    clauses=['s.project_id=?','pb.active=1','s.at>=pb.enrolled_at','s.origin IS NULL',
             's.app_id IN ('+','.join('?' for _ in apps)+')',
             'NOT EXISTS(SELECT 1 FROM tombstones t WHERE t.source_id=s.id)',
             "NOT (s.origin_type='user_note' AND EXISTS(SELECT 1 FROM note_fences nf WHERE nf.project_id=s.project_id))"]
    args=[query.project_id,*apps]
    if query.start is not None:clauses.append('s.at>=?');args.append(query.start)
    if query.end is not None:clauses.append('s.at<=?');args.append(query.end)
    return ' AND '.join(clauses),args


def hit(row,score=0.0):
    return EvidenceHit(row['id'],row['occurrence_id'],row['artifact_id'],row['locator'],row['at'],row['origin_type'],row['text'],bool(row['truncated']),float(score))


def keyword_candidates(store,ctx,query,limit=50):
    if type(limit) is not int or not 1<=limit<=50:raise ValueError('Invalid candidate limit')
    tokens=list(dict.fromkeys(re.findall(r'\w+',query.text,flags=re.UNICODE)))
    if not tokens:raise ValueError('Enter searchable words')
    expression=' OR '.join('"'+token.replace('"','""')+'"' for token in tokens)
    with store.lock:
        where,args=scope_filter(store,ctx,query)
        # Materialize FTS rank before windowing, then choose one permitted occurrence
        # per exact chunk text. Repeated private matches never consume public slots.
        rows=store.connection.execute('''WITH matches AS MATERIALIZED (
            SELECT c.*,s.artifact_id,a.locator,s.at,s.origin_type,o.truncated,chunk_search.rank AS score
            FROM chunk_search JOIN memory_chunks c ON c.id=chunk_search.chunk_id '''+JOINS+'''
            WHERE chunk_search MATCH ? AND '''+where+'''),
            chosen AS (SELECT *,row_number() OVER(PARTITION BY text ORDER BY score,at DESC,occurrence_id) AS duplicate_rank FROM matches)
            SELECT * FROM chosen WHERE duplicate_rank=1 ORDER BY score,at DESC,id LIMIT ?''',[expression,*args,limit]).fetchall()
        current_grant(store,ctx,query.project_id)
        return [hit(row,-row['score']) for row in rows]


def resolve_source(store,ctx,project_id,citation_id):
    from .api_contracts import Query
    with store.lock:
        where,args=scope_filter(store,ctx,Query(project_id,''))
        row=store.connection.execute('''SELECT o.id,b.text,a.locator,s.at,s.origin_type,o.truncated,pb.workspace_root
            FROM occurrences o JOIN blobs b ON b.id=o.blob_id JOIN sources s ON s.id=o.source_id
            JOIN artifacts a ON a.id=s.artifact_id JOIN project_bindings pb ON pb.project_id=s.project_id
            WHERE o.id=? AND '''+where,[citation_id,*args]).fetchone()
        if not row:return None
        path=Path(row['locator']);root=Path(row['workspace_root'])
        # No content is read; current symlink ownership is checked again on UI click.
        can_open=path.is_absolute() and path.resolve().is_relative_to(root)
        current_grant(store,ctx,project_id)
        return SourceDetail(project_id,citation_id,row['text'],row['locator'],row['at'],row['origin_type'],bool(row['truncated']),can_open)
