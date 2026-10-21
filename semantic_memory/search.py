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
    from .intentional_sources import BROWSER_SCOPE, BROWSER_APP
    origins=sorted(grant.source_scope.origins-{BROWSER_SCOPE})
    origin_clause='s.origin IS NULL'
    origin_args=[]
    if origins:
        origin_clause+=' OR s.origin IN ('+','.join('?' for _ in origins)+')'
        origin_args.extend(origins)
    if BROWSER_SCOPE in grant.source_scope.origins:
        origin_clause+=' OR (s.app_id=? AND EXISTS(SELECT 1 FROM source_details sd WHERE sd.source_id=s.id))'
        origin_args.append(BROWSER_APP)
    clauses=['s.project_id=?','pb.active=1','s.at>=pb.enrolled_at','('+origin_clause+')',
             's.app_id IN ('+','.join('?' for _ in apps)+')',
             'NOT EXISTS(SELECT 1 FROM tombstones t WHERE t.source_id=s.id)',
             "NOT (s.origin_type='user_note' AND EXISTS(SELECT 1 FROM note_fences nf WHERE nf.project_id=s.project_id))"]
    args=[query.project_id,*origin_args,*apps]
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
        row=store.connection.execute('''SELECT o.id,b.text,a.locator,s.at,s.origin_type,o.truncated,pb.workspace_root,
            (SELECT title FROM source_details WHERE source_id=s.id) AS title,
            (SELECT url FROM source_details WHERE source_id=s.id) AS url
            FROM occurrences o JOIN blobs b ON b.id=o.blob_id JOIN sources s ON s.id=o.source_id
            JOIN artifacts a ON a.id=s.artifact_id JOIN project_bindings pb ON pb.project_id=s.project_id
            WHERE o.id=? AND '''+where,[citation_id,*args]).fetchone()
        if not row:return None
        path=Path(row['locator']);root=Path(row['workspace_root']) if row['workspace_root'] else None
        # No content is read; current symlink ownership is checked again on UI click.
        can_open=bool(root and path.is_absolute() and path.is_file() and path.resolve().is_relative_to(root))
        current_grant(store,ctx,project_id)
        return SourceDetail(project_id,citation_id,row['text'],row['locator'],row['at'],row['origin_type'],bool(row['truncated']),can_open,row['title'] or '',row['url'])


def search_project(store,backend,ctx,query):
    import dataclasses
    import json
    from .api_contracts import SearchResult
    from .index_worker import paused
    from .vector_index import active_generation,vector_candidates
    keywords=keyword_candidates(store,ctx,query)
    vectors=[];mode='keyword-only'
    with store.lock:
        generation=active_generation(store)
        use_vectors=backend is not None and generation is not None and not paused(store)
        if use_vectors:
            use_vectors=json.loads(generation['manifest'])['digest']==backend.manifest.digest
    if use_vectors:
        # Same lock as background indexing; UI calls this off its event loop.
        with store.lock:store.query_waiters+=1
        try:
            store.model_lock.acquire()
        finally:
            with store.lock:store.query_waiters-=1
        try:
            with store.lock:
                current_grant(store,ctx,query.project_id)
                use_vectors=not paused(store) and active_generation(store)==generation
            if use_vectors:
                try:
                    qv=backend.embed((query.text,),query=True)[0]
                    vectors=vector_candidates(store,ctx,query,qv)
                    mode='hybrid'
                except (RuntimeError,ValueError,OSError):
                    # Evidence remains useful when a local model is unavailable.
                    current_grant(store,ctx,query.project_id)
        finally:store.model_lock.release()
    with store.lock:
        current_grant(store,ctx,query.project_id)
        scores={};by_chunk={}
        words=[w.lower() for w in re.findall(r'\w+',query.text) if len(w)>2]
        phrase=query.text.strip().lower()
        for ranking in (keywords,vectors):
            for rank,item in enumerate(ranking,1):
                scores[item.chunk_id]=scores.get(item.chunk_id,0)+1/(60+rank)
                by_chunk[item.chunk_id]=item
        for chunk_id,item in by_chunk.items():
            # Asking for a file by name should put that file first, whatever its text says (a name is the strongest signal there is).
            name=Path(item.locator).name.lower() if item.locator else ''
            if name and (phrase==name or phrase and len(phrase)>3 and phrase in name or any(w==Path(name).stem for w in words)):scores[chunk_id]+=1
        ordered=sorted(by_chunk.values(),key=lambda h:(scores[h.chunk_id],h.at,h.chunk_id),reverse=True)
        primary=[];texts=set()
        for item in ordered:
            if item.text in texts:continue
            # Deleted evidence can disappear while query embedding ran.
            if resolve_source(store,ctx,query.project_id,item.citation_id) is None:continue
            texts.add(item.text);primary.append(dataclasses.replace(item,score=scores[item.chunk_id]))
            if len(primary)>=query.limit:break
        related=_expand_references(store,ctx,query,primary)
        current_grant(store,ctx,query.project_id)
        return SearchResult(query.project_id,ctx.policy_revision,tuple(primary),tuple(related),
                            {'matching_is_not_an_answer':True,'primary_count':len(primary),'related_count':len(related)},mode,query.start,query.end)


def _expand_references(store,ctx,query,primary):
    import dataclasses
    where,args=scope_filter(store,ctx,query)
    related=[];seen={h.citation_id for h in primary}
    for parent in primary:
        edges=store.connection.execute("SELECT * FROM edges WHERE subject_id=? AND kind='references' AND status IN ('supported','user_asserted') ORDER BY id",(parent.artifact_id,)).fetchall()
        for edge in edges:
            support=store.connection.execute('SELECT occurrence_id FROM support WHERE entity_id=?',(edge['id'],)).fetchall()
            if not support or any(resolve_source(store,ctx,query.project_id,s[0]) is None for s in support):continue
            rows=store.connection.execute('''SELECT c.*,s.artifact_id,a.locator,s.at,s.origin_type,o.truncated FROM memory_chunks c '''+JOINS+'''
                WHERE s.artifact_id=? AND '''+where+' ORDER BY s.at DESC,c.id LIMIT 10',[edge['object_id'],*args]).fetchall()
            for row in rows:
                if row['occurrence_id'] in seen:continue
                seen.add(row['occurrence_id']);related.append(dataclasses.replace(hit(row),related_to=parent.citation_id))
                if len(related)>=10:return related
    return related
