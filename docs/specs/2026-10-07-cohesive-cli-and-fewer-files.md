# Fewer files, one menu

**Date:** 7 October 2026 · **Branch:** `main`

## Problem

Aditya: too many memory files (`.index.json`, `memory.json`, `pending.json`, plus
`sessions/`), and too many isolated commands to remember - wants one command that
opens a menu of what's available.

## File audit

| File | Who reads it | Verdict |
|---|---|---|
| `.index.json` | `store.load_items` (fallback) | kept, but merged into `memory.json` |
| `memory.json` | people, `lmemm.py memory` | kept, now the one file |
| `pending.json` | **nothing** - `lmemm.py notes` already computed its view live from `load_items()` | removed; computed on demand (`notes.pending_view`), same as always for the CLI and the pill |
| `sessions/<id>.json` | `lmemm.py memory`, `context.py` | kept (per Aditya's own list) |
| `context/<id>.json` | written on request, for handing to an AI | kept (per Aditya's own list), new this week |
| `inputs/`, `contributions/` | the opt-in input timeline and session deletion | left alone - only appear if that feature is turned on, and deletion already has its own test suite built around them |

## Decision

1. `memory.json` carries both views in one file (`"things"`: readable; `"items"`: full,
   including bookkeeping like refs and content hashes the tracker needs to resume
   identity). One source of truth, one write.
2. `pending.json` is removed. Every place that showed it (`notes` CLI, the pill,
   session-deletion's rebuild) already called `notes.pending_view(items)` live; only the
   unread on-disk copy goes away.
3. Old `data/` folders migrate automatically: `load_items()` reads a legacy `.index.json`
   if `memory.json` lacks `"items"`; the next `save_memory()` writes the merged file and
   deletes both stale files. Verified against Aditya's own `data/` and an older archive.
4. `lmemm.py` with no arguments opens an interactive menu instead of starting the
   tracker. Every item reuses the existing `cmd_*` function - one implementation of each
   command, shared by the CLI and the menu - so there's no second code path to drift.
   An explicit subcommand (`lmemm.py start`, `lmemm.py status`, ...) is unaffected.

## Result

`data/memory/` goes from 4 file-shapes (`.index.json`, `memory.json`, `pending.json`,
`sessions/`) to 3 (`memory.json`, `sessions/`, `context/` - written on request). 17 new
tests for the menu (menu shape, every item runs without crashing the loop, Ctrl-C/Ctrl-D,
bare vs. explicit invocation); schema bumped to 3 with an automatic migration path,
covered by updated existing tests. 159/159 total.
