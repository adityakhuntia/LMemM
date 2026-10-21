# Launch 1: resume a project across notes, code and browser sources

Status: approved direction on October 20, including the low-friction explicit-save
flow. User authorized extending Project Resume with a useful knowledge graph and
browser connectivity. Implementation and release acceptance remain outstanding.

## Outcome and audience

A developer or knowledge worker returns to a named project and understands what
was saved recently, what was decided, why, and what remains unfinished. Every
statement about past work opens retained evidence. Users can carry this context
into another AI without requiring Codex or a coding workspace.

## Delivery boundary

Launch 1 means an installable, documented macOS early-access release for a small
pilot, with one Chrome/Chromium browser connector. It does not mean a public
App Store release. The current checkout-linked alias app is a development build,
not a distributable deliverable. Supply a standalone app build, bundled runtime
and a clean-machine installation procedure. Signing/notarization depends on
available Apple credentials; report it as blocked if unavailable rather than
claiming distribution is ready. An unpacked extension is acceptable for the pilot
with clear instructions; Chrome Web Store publication is a separate action.

## Projects and saved sources

- Create a project and enable Memory without choosing a folder. Optionally attach
  a workspace later and connect VS Code through the existing explicit flow.
- Use stable project IDs independent of paths or names. Migrate existing bindings
  atomically while preserving project IDs, sources, task state and citation IDs.
  Workspace associations remain optional and unique; never merge projects by name.
- Native notes and pasted excerpts become explicit intentional sources, never
  simulated VS Code captures. An excerpt accepts text, title and optional HTTP(S)
  URL. Label its provenance as user-supplied, not browser-observed.
- Preserve existing note authoring and task completion. Editing a note replaces
  its supported current claims; removed evidence cannot remain in search or graph.
- Each browser save is an immutable snapshot with a source ID, project ID, save
  timestamp, page title, URL, capture mode and retained text. Re-saving changed
  content makes another snapshot; duplicate submissions use idempotency keys.
  No live fetch on source viewing or search. Links open today's page separately.

## Browser connector: recommended first version

Use a Manifest V3 Chrome extension with explicit user gestures and activeTab,
scripting and nativeMessaging permissions; avoid persistent all-sites access.
Approved low-friction flow: choose a destination
project on first use, then remember it. Highlight text and use a configurable
keyboard shortcut or right-click Save to LMemM to save the selection. Clicking
the extension action saves the selection when present, otherwise bounded visible
page text. No mandatory preview or project picker after setup. The destination
is visible in the extension badge/title and every confirmation. An accessible
confirmation says Saved to [project], with Undo and Change project. Changing
project on that confirmation moves that exact saved snapshot atomically, removes
its old project support/index visibility and invalidates outstanding scoped
responses; failure leaves the original ownership intact and explains the result.
Undo deletes that exact save and its derived evidence, not previous snapshots.
Shortcut conflicts have a discoverable browser shortcut-settings fallback.
First use or a deleted/unavailable destination opens the project chooser and
requires confirmation before saving; never guess a project from page contents.
The user approved this flow after asking for an easier save interaction.
Do not collect background history, hidden form values, passwords, cookies or
private/incognito tabs. Unsupported browser pages and absent selections explain
what happened. Full-page extraction means bounded visible text, not a promise to
capture PDFs, images, inaccessible frames or an entire dynamic document.

Pair through the app and an OS native messaging host, using a private per-install
credential and an explicitly approved extension identity. The host must not trust
an arbitrary stdin caller as authority. Treat page content as untrusted data;
it cannot execute commands or change project/grant policy. No unauthenticated
localhost ingestion endpoint. Pairing, disconnect and reconnect are visible in
Settings. Installation must survive a normal app restart and not hard-code the
developer checkout. Exact host transport and packaging layout are builder calls.

App must acknowledge a durable save before the extension says Saved. If the app
is stopped, locked, paused, disconnected, or the project unavailable, show a clear
failure without retaining a hidden offline queue. Retry requires the user's
action. Disconnect stops new saves but retains previously saved evidence; offer
separate removal of saved browser sources. Source/project deletion removes their
derived chunks, vectors, graph support and subsequent AI context as well.
Revoking browser pairing stops future ingestion and leaves local retained sources
available. Revoking an AI grant blocks that integration's subsequent reads and
discards pending replies, without deleting local evidence. Project Memory pause
stops capture; its established read behavior must remain explicit in the UI.

## Useful knowledge graph

Use the existing SQLite graph, local vectors and keyword retrieval together.
Graph scope is project, source snapshot, explicit decision, task and supported
reference. Relations: source belongs to project; evidence supports a decision or
task; recorded reason belongs to its decision; source explicitly references
another source. Correct the existing supports direction if required by consumers
through an explicit migration/adapter, never silently reinterpret old edges.

Decisions and tasks come from explicit note intent or a user action that records
selected evidence as a decision/task. A saved web page's instructions are not the
user's commitments. Preserve exact supporting spans; reasons require explicit
support. Cross-source relationships require an explicit URL/file reference or
user confirmation. Similarity can rank related material but must be labelled
related, not factual dependency, contradiction or supersession.

Show a compact Related sources section and source links on decisions/tasks.
Users can inspect why an item belongs here and remove an explicit relationship.
No visual graph explorer, autonomous broad entity extraction or inferred decision
history. The graph is valuable because Resume and exported context follow the
same supported relationships, not because a graph database exists.

## UI built on the current app

Keep Overview and Memory. Add Resume as the first project tab, with:

1. Last saved activity, ordered by saved time and labelled as saved activity.
2. Recorded decisions with available reasons and View source.
3. Open tasks with complete/reopen and evidence links.
4. Recent/related sources, with provenance, title and timestamp.
5. Copy context, plus the existing optional AskCodex enhancement.

Memory keeps search and source inspection, adds Save excerpt and connector setup
entry points. Settings separates optional folder/VS Code connection from browser
pairing and project Memory controls. Empty Resume explains how to save the first
note or source. Do not call last saved content the user's current live activity.
Native notes have no Open file action; browser sources have Open original URL,
clearly separate from retained evidence. Keep paused/error/indexing states clear.

Copy context uses deterministic source-backed sections and citation IDs, with
bounded text and explicit omissions. Browser text is quoted untrusted evidence.
AskCodex remains opt-in and generated answers remain distinct from records.
Extend its existing grants to browser/native sources explicitly: old grants must
not silently gain new origins. Project isolation applies to all UI/API/MCP paths.

## Acceptance and release evidence

- Upgrade an existing data fixture without losing notes, IDs, citations or task
  state; test rollback on failed migration and restore from documented backup.
- Create a folder-free project, add a decision/task/excerpt, restart, resume and
  copy context. Repeat with a workspace project and existing VS Code capture.
- Install/pair connector, save selected text and a page, inspect exact retained
  text/URL/time, change the page and verify the snapshot stays historical.
- Test two projects, wrong/stale grants, revoked pairing, paused/locked app,
  unsupported pages, malformed/oversize input, duplicate retry, source deletion,
  project deletion and edit/task state consistency. Deleted evidence must not
  remain in results or graph; revoked integrations must not ingest/read through
  the revoked capability. Locally retained evidence survives a disconnect.
- Run isolated Python and extension tests; render actual native states for empty
  Resume, populated Resume, evidence/related sources, folder-free setup, pairing,
  pause, errors and successful browser save. Exercise the real browser-to-app
  flow, not just mocks, and retain screenshots/test commands in the handover.
- Build and install independently of the checkout; perform second-Mac onboarding
  and a sustained session including browser saves, sleep/lock, pause/resume and
  the original crash sequence. Record memory/CPU behavior. External hardware or
  credentials unavailable to the builder remain explicit release blockers.
- Pilot with two developers and two knowledge workers: first useful save within
  five minutes; recover next action plus evidence within two minutes after an
  interruption. User recruitment is not authorized by this design.

## Execution order

Source/project authority and migration; intentional source ingestion and graph;
Resume/context export; browser transport/extension and pairing UI; standalone
packaging; integrated regression and real-device release acceptance. Preserve
private context.md, existing personal data and unrelated work. Check main before
integration and follow the user's prior direct-to-main authorization once tested.

## Scope decisions

Explicit browser saves are the approved Launch 1 boundary. Automatic capture
of connected tabs changes permission, lifecycle, privacy and UI design and must
be designed separately if requested. Other technical details above are builder
choices within this scope, not capabilities already shipped.
