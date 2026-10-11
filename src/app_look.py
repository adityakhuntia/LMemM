"""LMemM - how a web app looks when it has no app of its own on this Mac. Plain data, no UI.

Gmail, Google Docs and ChatGPT run in a browser, so there is no application icon to borrow. Each gets a small
rounded square in its own colour with a plain symbol, drawn by us (no logos are copied). Anything not listed falls
back to the kind of thing, as before.
"""

WEB = {
    "Gmail": ("envelope.fill", (0.92, 0.26, 0.21)),
    "Google Docs": ("doc.text.fill", (0.26, 0.52, 0.96)),
    "Google Sheets": ("tablecells.fill", (0.06, 0.62, 0.35)),
    "Google Slides": ("play.rectangle.fill", (0.96, 0.71, 0.0)),
    "Google Calendar": ("calendar", (0.26, 0.52, 0.96)),
    "Google Meet": ("video.fill", (0.0, 0.59, 0.53)),
    "Google Drive": ("externaldrive.fill", (0.98, 0.74, 0.02)),
    "Google Search": ("magnifyingglass", (0.26, 0.52, 0.96)),
    "YouTube": ("play.fill", (0.95, 0.1, 0.1)),
    "GitHub": ("chevron.left.forwardslash.chevron.right", (0.14, 0.16, 0.18)),
    "LinkedIn": ("person.2.fill", (0.04, 0.4, 0.76)),
    "Notion": ("doc.plaintext.fill", (0.2, 0.2, 0.22)),
    "Slack": ("number", (0.38, 0.12, 0.4)),
    "WhatsApp": ("bubble.left.fill", (0.15, 0.78, 0.4)),
    "ChatGPT": ("bubble.left.fill", (0.06, 0.64, 0.5)),
    "Claude": ("sparkle", (0.85, 0.47, 0.34)),
    "Gemini": ("sparkle", (0.27, 0.4, 0.9)),
}


def look(app):
    """(SF Symbol name, (r, g, b)) for a known web app, else None."""
    return WEB.get(app)
