# Input timeline, privacy and deletion

Details for the opt-in keyboard/cursor timeline (`--input-events`) and for removing
sessions. The README has the short version.

## Keyboard and cursor timeline

Normal startup watches screens without starting an input listener. To enable the
first collector:

```bash
python3 lmemm.py --input-events --input-app com.microsoft.VSCode
# Optional: --input-retention-hours 4
```

Enable **Input Monitoring** and **Accessibility** for the launching app in macOS
Settings, then quit/reopen it. Input currently supports **VS Code only**; browser
documents and other apps are excluded from detailed input collection.

The listener records timestamped keyboard **bursts and counts**, coarse 3×3
cursor movement/drag regions, clicks and scroll buckets. Summaries link to an
older before-image (with its age), a settled after-image, and the memory item
resolved by OCR. Keyboard activity alone is not proof of authored text or intent.

```bash
python3 lmemm.py status
python3 lmemm.py memory 20 --events --content
python3 lmemm.py pause
python3 lmemm.py resume
```

Pause stops screenshot capture too and cancels an open note panel. Commands
request a PID-scoped change; `status` shows acknowledgement. Resume retries a
disabled/unavailable collector with fresh permission checks. Missing permission,
secure or uncertain focus, delayed input and listener failures produce visible
coverage gaps rather than being assigned to another app.

VS Code's Electron accessibility tree may be disabled even after permission is
granted. The collector enables its documented `AXManualAccessibility` flag only
for foreground allowed VS Code, and restores flags it changed on normal stop.
This can add processing cost; a crash may leave it enabled until VS Code quits.
Test inside an **editor file**, not the integrated terminal: unverified text-field
subroles remain blocked. Listener startup saying “recording” does not prove that
accepted events are flowing—inspect the event timeline.

### Tab and app shortcuts

| Shortcut | Recorded evidence |
|---|---|
| **Ctrl+Tab** | forward tab-switch step |
| **Ctrl+Shift+Tab** | backward tab-switch step |
| **Cmd+Tab** | forward app-switch step |
| **Cmd+Shift+Tab** | backward app-switch step |

Each accepted Tab key-down contributes one classified step. `memory --events`
shows forward/backward totals and source-matched observed context changes or
departures. Confirmation does not cross pause/security gaps or overwrite an
earlier result. A shortcut is evidence of a requested action, not proof that a
specific tab/window was selected; VS Code bindings can change its behavior.

Counts cover accepted permitted focus. macOS's app switcher can own focus or
event targets, so repeated Cmd+Tab events may be omitted. **Step count is not a
reliable count of windows passed.** Cmd+Tab switches apps; their order and windows
are not yet modeled. Browser tab identity and reliable window-close semantics
remain future work.

Characters, clipboard and editable accessibility values are never read by the
input collector. Only the requested shortcut families transiently inspect
modifiers and Tab identity; raw keycodes/modifiers are never stored. Other
keyboard input remains counts, not a key journal.

## Privacy and retention

Input observation is listen-only: it does not suppress, modify or synthesize your
input. Permission, secure-focus, context-boundary and target-process checks gate
detail collection. Event time is calibrated to the session's monotonic clock;
native ordering is separate from polling/gap time. Truly delayed events still
produce a gap at the 100ms guard instead of being attributed to new focus.

Detailed input is bounded to 30s of transient context and at most 24h on disk
(configurable shorter), with a 4,096-event cap and visible expiry/capacity-loss
counters. Startup, periodic maintenance and inactive event inspection prune all
sessions. While stopped, expiry is enforced on the next startup/read; there is no
separate background deletion scheduler. Ordinary memories, notes, excerpts and
contribution evidence have longer-lived retention.

New input/control/provenance files and input source-image copies use private
permissions, but **JSON/JPEG storage remains plaintext**. No encryption or
screenshot redaction has been added. Ordinary capture still saves whole displays
and samples pointer positions; the input allowlist does not scope screenshots.
Overlapping/background windows, imperfect foreground geometry, OCR, titles and
URLs can expose sensitive content even without a key journal. Cropping/masking,
stronger capture controls and encryption remain work to do.

## Delete a session

Stop tracking, then inspect the plan before deleting:

```bash
python3 lmemm.py delete-session SESSION --dry-run
python3 lmemm.py delete-session SESSION --confirm SESSION
```

The confirmation must match the exact session ID. Deletion rebuilds shared items
from the legacy baseline and surviving session-owned contributions, removes owned
input/capture/session evidence, and recovers interrupted operations on the next
memory load.

It blocks active tracking, legacy sessions without reconstructable provenance,
referenced replay copies, external memory changes, and source screenshots still
needed by retained evidence. These blockers preserve unrelated work; deletion
does not guess at missing ownership. Try it on disposable test data first.

