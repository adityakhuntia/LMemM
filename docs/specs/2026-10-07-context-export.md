# Clean context export for an AI

**Date:** 7 October 2026 · **Branch:** `main`

## Problem

`memory.json` and the session timeline files are the tracker's own working data:
per-visit timing, triggers, activity-category seconds, screenshots, internal ids —
kept because the tracker needs them to decide identity and when to capture. Aditya's
ask: if memory is ever exposed to an AI, it should see only the content and intent,
not the operational detail, and the output should be small because the real task
("45 different things") is small — the files are big because of redundant
per-frame/per-visit bookkeeping, not because the content is large.

## Decision

A separate, derived export (`context.py`, `lmemm.py context`) rather than changing
`memory.json` itself — the tracker still needs its own full data to function.

Per thing, kept: app, title, one-line status (`doing`), a plain-English `when` (span +
visit count, not a timeline), notes with open/done, deduplicated real content (UI chrome
stripped), and any state field that isn't just a repeat of the title. Dropped entirely:
screenshot, internal id, trigger, per-visit timeline entries, activity-category seconds,
ref/content hash. A thing with neither a note nor kept content is left out — there's
nothing to tell an AI about it.

Grouped by project (reusing `notes.project_of`), newest first. Scoped to one session
(`for_session`, via that session's timeline), a day range (`since`), or everything
(`by_project`); default is the latest session.

## Result

On Aditya's own archived data: 9 things in `memory.json` (9.4 KB) plus that session's
10 KB timeline → 6 things worth telling an AI about, 1.7 KB.

## Files

`context.py` (new), `lmemm.py` (`context` command), `tests/test_context.py` (15 tests).
142/142 total.
