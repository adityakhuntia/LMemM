"""Native evidence pane using the existing Figtree drawing kit.

Layout (audit: the pane was one column of a dozen identical buttons and a raw JSON dump): what the person
came to do is on top, what they set up once is folded away.

    status      one line: a dot, the state, and the two actions that apply right now (Pause / Resume, Refresh)
    search      the workspace, the search box, the period, then the evidence as cards
    notes       add a project note
    setup       "Connections and setup", folded: the model, VS Code, Codex, each as a small group;
                stopping and disconnecting sit last, apart from the rest
"""

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


TONES = {"Ready": "good", "Processing": "accent", "Needs attention": "warn"}      # anything else is a quiet grey

# Connections and setup, in the order a person meets them: (title, line, [(button, action, kind)]).
# "outline" is the heavier look, kept for the things that cut something off.
ADMIN_GROUPS = [
    ("Search model", "Semantic recall uses a small local model (about 46 MB) kept in LMemM’s own folder. It is installed only when you say so.",
     [("Install local model…", "confirm_model", "quiet")]),
    ("VS Code", "Memory reads text you view in VS Code through its extension.",
     [("Install VS Code source extension…", "install_extension", "quiet"), ("Reconnect source sharing…", "reconnect_extension", "quiet")]),
    ("Codex", "Codex can read this project’s memory only after you connect it. Previewing sends nothing.",
     [("Preview context for Codex", "preview", "quiet"), ("Connect Codex…", "confirm_agent", "quiet"),
      ("Revoke Codex access", "revoke_agent", "outline")]),
    ("Stop", "Disconnecting stops capture and revokes every agent grant. What was retained stays on this Mac.",
     [("Disconnect project Memory…", "confirm_disconnect", "outline")]),
]


def admin_groups(status):
    """ADMIN_GROUPS for what is true now: once the search model is installed its group says so
    instead of offering to install it again."""
    groups = []
    for title, line, items in ADMIN_GROUPS:
        if title == "Search model" and (status or {}).get("model_state") == "available":
            line, items = "Installed. Semantic recall is on. It lives in LMemM’s own folder.", []
        groups.append((title, line, items))
    return groups


def admin_toggle_label(showing):
    """The folded section's button: words, not an arrow character."""
    return "Hide connections and setup" if showing else "Show connections and setup"


def state_tone(state):
    """good, accent, warn or quiet: the colour of the dot beside the state. Never red (red is for a permission that is off)."""
    return TONES.get(state, "quiet")


def pause_action(state):
    """(button label, action) for the one pause control that applies, or None while Memory is off."""
    if state == "Disabled":
        return None
    return ("Resume Memory", "resume") if state == "Paused" else ("Pause Memory", "pause")
