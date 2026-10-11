"""Occurrence-owned chunks with exact character offsets into retained spans."""
import re
from .policy import identifier

CHUNK_VERSION = 1
CHUNK_BYTES = 1024
OVERLAP_BYTES = 128


def split_text(text):
    start=0
    while start<len(text):
        end=start;size=0
        while end<len(text) and size+len(text[end].encode())<=CHUNK_BYTES:
            size+=len(text[end].encode());end+=1
        if end<len(text):
            boundaries=[m.end() for m in re.finditer(r'\s+',text[start:end])]
            if boundaries and boundaries[-1]>=max(1,(end-start)//2):
                end=start+boundaries[-1]
        yield start,end,text[start:end]
        if end==len(text):break
        next_start=end;overlap=0
        while next_start>start+1 and overlap+len(text[next_start-1].encode())<=OVERLAP_BYTES:
            next_start-=1;overlap+=len(text[next_start].encode())
        start=next_start


def index_source(store, source_id):
    ids=[]
    with store.transaction() as c:
        if not c.execute('SELECT 1 FROM sources WHERE id=?',(source_id,)).fetchone():
            raise ValueError('unavailable')
        rows=c.execute('SELECT o.id,b.text FROM occurrences o JOIN blobs b ON b.id=o.blob_id WHERE o.source_id=? ORDER BY o.id',(source_id,)).fetchall()
        for row in rows:
            for start,end,text in split_text(row['text']):
                cid=identifier('chunk',f"{row['id']}|{CHUNK_VERSION}|{start}|{end}")
                ids.append(cid)
                if c.execute('INSERT OR IGNORE INTO memory_chunks VALUES(?,?,?,?,?,?)',(cid,row['id'],CHUNK_VERSION,start,end,text)).rowcount:
                    c.execute('INSERT INTO chunk_search VALUES(?,?)',(cid,text))
    return tuple(ids)
