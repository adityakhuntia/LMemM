# Lighter capture: fewer, cheaper frames; thumbnails only

**Date:** 7 October 2026 · **Branch:** `perf/lighter-capture` (from `main`)

## Problem

A 15-minute session took 137 captures, and an hour of use made the laptop slow. Measured on
the target Mac (real frames from archived sessions):

| Per capture | Cost |
|---|---|
| `screencapture` + `sips` subprocesses | 257 + 121 ms |
| browser URL via AppleScript | 77 ms (once 9.6 s) |
| accurate OCR (when pixels changed) | 630 ms wall, 720 ms CPU, bursts of 94–193 % CPU |
| `save()` of all memory, every frame | 6 ms at 17 things, 123 ms at 1,000 |

About 145 CPU-seconds per 15 minutes plus 270 subprocess launches. Disk was not the problem
(17 files kept of 137), but every kept thing keeps a full screenshot forever. No memory
leak was found (240 OCRs flat at 145–225 MB).

## Decisions (approved by Aditya)

1. Keep **thumbnails** for kept screenshots; expire them after 7 days unless pinned or an open note.
2. Use **fast OCR** for continuation frames; accurate for the first look.
3. Also: back the timer off when nothing changes; capture in memory; batch saves; measure.

## Scope

In: A timer back-off · B in-memory capture, write only kept frames as thumbnails · C fast OCR
on continuation frames (redo accurate if thin) · D thumbnail retention · E batched saves,
drop the unused scene-classification request · F cost report in `status` and the summary.
Out: event-log/SQLite persistence, reading the browser URL off the main thread (the back-off
already cuts those calls ~4×), cropping OCR to changed regions.

## Acceptance criteria

1. A redundant frame writes nothing to disk; a kept frame writes one thumbnail ≤ 480 px and its metadata.
2. A pixel-identical frame runs no OCR; a changed later frame of the same window uses fast OCR;
   first look / note / pin use accurate; a thin fast result is redone accurately.
3. Timer interval doubles per unchanged frame to the cap (30 s; 15 s for chats); input or a switch resets it.
4. Thumbnails older than 7 days are deleted unless the thing is pinned or has an open note; text memory is untouched.
5. Running, memory files are written at most every 5 s; notes, ticks and shutdown write immediately.
6. `status` and the session summary report CPU, memory, capture/OCR counts and timings; sustained
   high CPU or memory prints a warning (not during startup).
7. Existing tests pass; new tests cover 1–6.

## Result

See the PR description (live numbers).
