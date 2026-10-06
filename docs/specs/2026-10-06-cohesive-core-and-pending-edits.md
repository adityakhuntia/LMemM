# Cohesive core + pending edits (design)

**Date:** 6 October 2026 · **Branch:** `refactor/cohesive-core` (from `feat/input-timeline`) · **Target:** `main`

## 1. Why

`main` has Aditya's capture → activity → memory → dictation pipeline. `feat/input-timeline`
(Divyaansh) adds the opt-in input timeline, content excerpts, stable document identity,
provenance/deletion and 89 tests. Both are good, but after merging, the code has one
1,160-line `tracker.py` doing OS access, scheduling, identity, persistence, notes and
reporting; paths are module globals patched by tests; `input_store` imports `tracker`
for rendering; a legacy logger and summary tool from step 1 are still around; and the
docs describe three different eras of the product.

Goal: merge both lines into one product whose structure says what it does, with no
behaviour lost, then add the next feature on top.

## 2. Scope

**In**

1. Behaviour-preserving restructure into single-purpose modules (§3).
2. One configuration surface (`config.py`): tunables, privacy lists, data paths.
3. One CLI shape (`lmemm.py <command>`), every command documented in one place.
4. Notes become **pending edits**: they resurface when you reopen the thing, and a
   **project view** lists everything still open (§4).
5. Docs: one README for using it, one ARCHITECTURE for building on it; the
   handover/history moved under `docs/`.

**Out (unchanged, on purpose)**

- Capture/identity/activity heuristics and the input-timeline privacy rules.
- Storage format beyond additive fields (schema stays 2; no migration needed).
- Any model/backend, search, or recall UI.

## 3. Target structure

| Module | One job |
|---|---|
| `config.py` | Tunables, privacy skip-lists, data paths (`Paths`, overridable for tests) |
| `macos.py` | Everything that talks to macOS: front window, browser URL, displays, screenshot, idle/input counters, pointer, workspace notifications, log noise |
| `resolver.py` | Screenshot → OCR lines + layout (Apple Vision) |
| `understand.py` | Lines → what you're doing (per-app rules) |
| `activity.py` | Frame diff → typing / reading / receiving / focus |
| `memory_content.py` | Bounded excerpts + unverified decision quotes |
| `identity.py` | Which memory item a screen belongs to (same thing vs. new thing) |
| `notes.py` | Notes as pending edits: ids, status, attach, resurface, project view |
| `store.py` | Persistence: load/save `.index.json`, readable `memory.json`, session timelines |
| `tracker.py` | Orchestration only: schedule captures, run the resolver thread, keep the timeline, apply controls |
| `dictation.py` + `listen/` | ⌃⌥N hotkey, note window, on-device speech helper |
| `input_events.py`, `input_monitor.py`, `input_store.py` | Opt-in input timeline, privacy gate, provenance/deletion |
| `lmemm.py` | CLI |

Dependency direction: `lmemm → tracker → {identity, notes, store, activity, understand,
resolver, memory_content, macos, input_*} → config`. Nothing imports `tracker` or `lmemm`.

Removed: `logger.py`, `peek.py` and the `peek` command (step-1 fixed-interval logger,
superseded by the tracker; history is in git).

## 4. Feature: pending edits

**User story.** While working on something (a doc, an email, a file, a chat) I press ⌃⌥N
and say "add a pricing section". Later, when I open that doc again, LMemM reminds me.
At any time I can see every open edit, grouped by project, and tick them off.

**Model.** Every note on an item is a pending edit until marked done.

```json
"notes": [{"id": "n-3f9a1c", "at": "2026-10-06T10:12:03", "text": "add a pricing section",
           "while": "Working on \"Q3 plan\""}],
"notes_done": {"n-3f9a1c": "2026-10-06T15:40:11"}
```

- `id` is derived from the note (`sha1(at|text)`), so notes written before this change
  get the same id without migration.
- Done-state lives in `notes_done`, not inside the note, so the provenance store (which
  matches notes by value) never sees a changed note as a new one.
- **Project** of an item: code file → its project folder; Google Doc / Sheet → the document;
  email draft/email → `Email`; chat → `Chats`; web page → its site; anything else → the app.

**Resurface on reopen.** When a new visit to an item starts (not a continuation of the
current one) and it has open notes, LMemM shows a macOS notification
("2 pending edits on Q3 plan · add a pricing section") and a terminal line, and records
it on the timeline. At most once per item per `RESURFACE_COOLDOWN` (10 min); never for
the visit during which the note was written; never while paused.

**Project view.** `lmemm.py notes` prints open edits grouped project → item, newest first,
with each note's id and age. `--all` includes done ones. A readable `data/memory/pending.json`
is rewritten on every save, so the view also exists as a file.

**Marking done.** `lmemm.py notes done <id>…` / `notes reopen <id>…`. If the tracker is
running, the change is sent through the existing PID-scoped control file and applied under
the memory lock; otherwise it is applied to `.index.json` directly.

## 5. Acceptance criteria

1. All 89 existing tests pass after the restructure, adapted only where they named old
   module globals.
2. `tracker.py` contains no OS calls, no persistence formatting and no identity rules.
3. A note written on item A, then a visit to B, then back to A → exactly one resurfacing
   for A; a second return inside the cooldown → none; a done note → none.
4. Notes on two different items in one project appear under one project heading;
   done notes are hidden unless `--all`.
5. Old notes without `id` show and can be marked done.
6. Marking done while the tracker runs goes through the control file; stopped → direct.
7. Provenance checkpoint/rebuild keeps `notes_done` and does not duplicate notes.
8. Live smoke run: start, capture, status/pause/resume, stop; memory and pending view readable.

## 6. Test plan

Unit: `tests/test_notes.py` (ids, project_of, pending view, done/reopen, resurfacing rules,
legacy notes). Integration: tracker visit sequence A→B→A with fake frames (existing
pipeline fixtures), CLI `notes` both running and stopped, provenance rebuild with
`notes_done`. Regression: full suite. Manual: live run on macOS.

## 7. Rollout

Single PR `refactor/cohesive-core → main`, containing `feat/input-timeline` (merged as-is)
plus the restructure and feature as separate commits so each can be reviewed alone.
Rollback: `git revert` of the feature commit leaves the restructure; data stays compatible
because all new fields are additive.
