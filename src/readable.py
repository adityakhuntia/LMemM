"""LMemM - titles a person can read. Plain functions.

A thing's title comes from what was read off the screen (a window title, a heading, a search box). Sometimes that is
debris: spoken words from a dictated note, a terminal line, text read wrong ('now. Uh, I'm not 8vre if it18 ...',
'. $v$Slurt"" kn2sl'). Anything shown to a person goes through show(), which keeps a readable title and otherwise
falls back to what was being done, then to the app's name.
"""

FILLER = {"uh", "um", "uhm", "hmm", "erm"}
SYMBOLS = set('$"#@^*_\\|<>{}~=`')


def readable(text):
    """False for spoken-word debris and text read wrong; True for an ordinary title."""
    text = (text or "").strip()
    if not text:
        return False
    words = [w.strip(".,!?").lower() for w in text.split()]
    if any(w in FILLER for w in words):
        return False
    if sum(1 for c in text if c in SYMBOLS) >= 2:
        return False
    garbled = [w for w in text.split() if any(c.isdigit() for c in w) and any(c.islower() for c in w)]
    return len(garbled) < 2                                   # '8vre', 'it18': letters and digits mixed, in lower case


def show(item):
    """The title to show for a thing: its title if readable, else what was being done, else the app, else 'Untitled'."""
    for text in (item.get("title"), item.get("doing")):
        if readable(text):
            return text.strip()
    return item.get("app") or "Untitled"
