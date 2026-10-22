# Launch 1 final review and decisions

October 22, 2026. Independent Astra review identified seven actionable issues;
all were reproduced or covered by targeted regressions and fixed. No minor
finding is deferred.

| Finding | Resolution |
| --- | --- |
| Queued Undo could target a newer save | Pin source ID before queueing; move and popup controls do likewise. |
| Old snapshot moved to new project became invisible | Explicit source ownership bypasses passive enrollment-time filtering, preserving original timestamp. |
| Large claims overflowed Resume IPC | Bounded statement/reason/citation previews and total UTF-8 response; full source stays inspectable. |
| Invalid migration backup accepted | Validate private SQLite recovery, schema/version/integrity; publish atomically without overwrite. Invalid existing copies require moving aside. |
| Delete left orphan artifacts/references | Remove unsupported orphan graph artifacts and incident edges, retain shared supported artifacts. |
| Durable delete unavailable after disconnect | Confirmed per-source forget and project purge, retained-count project deletion gate, stale reply fencing. Forget suppresses same-revision note mirroring; original notes/files remain, later explicit edits can return. |
| Selection crossed editable/private content | Range-aware text-node extraction applies form/editable/textbox/hidden exclusions; real Chromium old/new regression failed then passed. |

Verification: 923 Python tests, 15 extension tests; 19 synthetic native states
rendered. Screenshot harness now waits wall-clock time and fronts its own window
before capture. Native source and disconnected deletion controls inspected.
Real browser save/move/Undo testing preceded final concurrency fixes; the final
exact-source behavior is additionally covered by Node regressions. Final app
rebuilt and copied outside checkout: service/citations, browser host, MiniLM,
three MCP tools, permission probe and owned shutdown passed.

Implementation decisions: main was used at the user's direction, preserving
private untracked context.md. Schema v4 adds metadata/receipts after optional-root
v3; legacy quota test fixture grew to accommodate schema without changing the
production budget. Pairing controls shipped with a usable installer. Legacy data
import is an explicit offline action; no checkout guessing. AnyIO is bundled for
its dynamically imported backend. Isolated Chromium uses its own host manifest.
Receipts/tombstones intentionally prevent replay resurrection. Optional Ollama
remains external. Browser sources never automatically assert user commitments.

Review found no further actionable defects in scoped service retry, destination,
pause/lock/revocation, old grants, URL or UTF-8 handling. This does not claim
accessibility conformance or protection from a compromised OS account.
Developer ID/notarization, a second Mac, physical crash/sleep/lock, sustained
resource measurements and real pilots remain external release gates; see
[acceptance](launch-one-acceptance.md). No hosted AI or personal capture was used
in synthetic qualification.
