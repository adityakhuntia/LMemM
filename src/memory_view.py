"""LMemM - what the Memory tab says: the words, rows and dates it shows. Plain Python, no UI, so it is tested on any
machine. The drawing is in memory_pane.py."""
from datetime import datetime, timezone

def friendly(at,now=None):
    """'2026-10-12T08:38:03+00:00' as 'Today, 08:38', 'Yesterday, 14:02' or '9 Oct, 10:00' in local time."""
    try:
        when=datetime.fromisoformat(str(at).replace('Z','+00:00'))
        if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
        when=when.astimezone();now=(now or datetime.now(timezone.utc)).astimezone()
    except (ValueError,TypeError):return str(at or '')
    days=(now.date()-when.date()).days;clock=when.strftime('%H:%M')
    if days==0:return 'Today, '+clock
    if days==1:return 'Yesterday, '+clock
    return '%d %s, %s'%(when.day,when.strftime('%b'),clock)

def short_name(locator,limit=26):
    """The file name of a source, cut in the middle when long."""
    name=str(locator or '').replace('\\','/').rstrip('/').rsplit('/',1)[-1]
    if len(name)<=limit:return name
    keep=(limit-1)//2;return name[:keep]+'…'+name[-keep:]

PERIOD_LABELS={'Last 2 days':'2 days','Last 7 days':'7 days','All retained':'All'}
STATE_LABELS={'Ready':'Remembering','Processing':'Processing','Paused':'Paused · nothing new is kept','Needs attention':'Needs attention'}
CONFIRMS={'confirm_model':('Install meaning search?','Downloads about 46 MB (the MiniLM model) to LMemM’s own folder on this Mac. Needs Ollama installed. No notes or text are sent anywhere.','Install'),
          'confirm_agent':('Let Codex read this project’s memory?','Codex can search saved notes and sources and read the cited text. Using these tools sends that text to Codex and its provider. LMemM also adds itself to Codex’s settings on this Mac. You can turn it off at any time.','Allow and add to Codex'),
          'confirm_disconnect':('Disconnect Memory for this project?','Stops capture and revokes agent access. Saved notes stay on this Mac but can’t be searched until you enable Memory again.','Disconnect')}

def provenance(row):
    return 'Your note' if row.get('origin_type')=='user_note' else 'Observed content' if row.get('origin_type') else 'Supported by cited sources'

def evidence_rows(result):
    rows=[]
    for key,title in [('primary','Search results'),('related','Related evidence'),('decisions','Decisions'),('open_tasks','Open tasks'),('recent_evidence','Recent evidence')]:
        for row in result.get(key,[]):
            rows.append(dict(section=title,text=row.get('text',row.get('statement','')),at=row.get('at',''),
                citation_id=row.get('citation_id') or next(iter(row.get('citations',[])),None),reason=row.get('reason'),locator=row.get('locator',''),
                provenance=provenance(row),truncated=row.get('truncated',False)))
    return rows

def source_presentation(source):
    return dict(text=source['text'],locator=source['locator'],at=source['at'],open_enabled=source.get('can_open_file',False),
                provenance=provenance(source),truncated=source.get('truncated',False),
                open_explanation='This is the retained snapshot. Open file shows the file as it exists today.')
