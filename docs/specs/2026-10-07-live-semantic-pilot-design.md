# Opt-in live semantic project-memory pilot

2026-10-07. Status: revised direction approved after spec discussion; user requested
real work across approved projects and inspectable tentative recall. Extends the approved automatic project-memory design.
Implementation stays on `feat/semantic-project-memory` in its existing worktree.

## Intended outcome

After the missing live-source integration and precision work, the user should be
able to run a short real VS Code session and inspect project context with dated
source quotes, tentative interpretations and explicit coverage gaps. Successful
pilot operation is not model/MVP acceptance. Confirmed live results will be recorded
in handover/context docs before pushing this feature branch; no automatic main merge.

The pilot supports multiple explicitly approved local VS Code projects and windows.
Each window registers its own client; only the uniquely focused, freshly verified
client can publish accepted content. Browser support remains the next source-adapter
increment. Switching projects requires no manual artifact attachment. No hosted inference or expansion of the existing runtime budget.

## Chosen approach and alternatives

Use a small local VS Code extension to supply active-editor document/workspace URIs,
document versions and bounded visible-buffer excerpts. The Python pilot supplies
independent macOS foreground verification and the existing evidence/episode/store
pipeline. No manual artifact attachment is required.

Alternative: derive identities from screenshots/window titles. Rejected here because
OCR/title heuristics cannot establish authoritative file/workspace identity, and the
legacy tracker currently captures entire displays. Existing foreground-window work
remains useful but does not by itself solve editor identity.

Alternative: add a general Accessibility text scraper. Rejected for this pilot because
it expands content access and relies on inconsistent Electron accessibility text.
Accessibility is used only to verify focus/geometry and reject secure/unknown context.

## Source bridge and permission boundary

The pilot starts only through an explicit experimental command, with explicit absolute
workspace paths, dedicated semantic data directory and cached runtime configuration.
It generates a random per-run grant in a private local bridge directory. A VS Code
command explicitly connects the extension to that grant and shows the approved workspaces
and capture status. Installing/loading the extension alone never captures content.
No network bridge or third-party extension dependency is needed; bounded atomic local
files carry messages. The bridge is not a security boundary against malicious programs
already running as the same OS user; OS account/file permissions are its trust boundary.

The backend accepts only the configured grant and registered clients, local desktop file URIs,
trusted local workspaces, and documents canonically contained within an approved
workspace. Reject remote/virtual workspaces, untitled buffers, untrusted workspaces,
symlink escapes, unknown identity and excluded paths. Multi-root workspaces may expose
only explicitly approved roots. Extension configuration cannot silently widen Python's grant.
Private bridge files use 0600 and directories 0700; reject symlinked ingress paths and
oversized/malformed messages before parsing or text persistence. Bound ingress to 32 KiB,
each source span to 4 KiB and each source envelope's retained text to 16 KiB.

Default exclusions cover hidden paths, `.env*`, credentials/keys and generated/vendor
folders. User-specified exclusion patterns may tighten capture. Workspace permission
allows source content to be retained locally; it does not guarantee allowed files
contain no secrets. The pilot displays the actual scope and retained-content behavior.

Capture only the active editor's visible ranges while its VS Code window reports
focus. Read those ranges through the editor API; do not read whole files from disk,
background editors, terminal content, chat panes, password fields or keyboard values.
Unsaved edits of an existing local file use its authoritative URI and document version;
untitled editors remain unsupported. A visible-buffer snapshot proves visible source
content, not authorship, a completed edit or a user's decision.

## Independent foreground verification and lifecycle

Verify foreground bundle ID `com.microsoft.VSCode`, native focused-window geometry and
unique matching window-server identity. Register clients while focused and bind them to the verified native window ID.
Reject unregistered/mismatched windows, two clients claiming the same active window,
absent Accessibility permission, ambiguous focus, secure input,
lock/sleep, stale heartbeat and changed context. Do not reuse the legacy first-eligible
window heuristic as verification. No native editable values are read. Verify context
before and after accepting a bridge snapshot; discard changed/unknown context.

Bridge events have per-run client IDs, increasing sequence numbers, document versions,
capture timestamps and heartbeats. Consume each event once. Accept only fresh events
(within 2 seconds), cap event publication to once per 2 seconds and keep at most one
pending snapshot per source. Heartbeats update focus/state without repeatedly storing
unchanged content. Focus loss/stop clears pending source text; disconnect/timeout closes
an episode and cancels pending inference. One freshly focused client at a time is required; other connected project windows
remain idle. Unknown window/client associations fail closed rather than guessing.

Pause, lock/sleep, exclusion changes, secure input, permission loss and Ctrl+C stop
new intake and invalidate pending/in-flight results before a worker can commit them.
Resume establishes a new generation/revision. Retained permitted evidence is not
silently erased merely by pause; explicit revocation/deletion removes its dependencies.
Rejected messages produce bounded status counters, never source text in error logs.

## Semantic pipeline and output

Accepted snapshots become `trusted_artifact_snapshot` envelopes with canonical
workspace/file identities, source timestamps, session IDs, policy revisions and
bounded original text. Reuse the existing SQLite evidence and episode APIs. Unchanged
content does not trigger another model extraction. No implicit import of legacy
screenshots, OCR history, input logs or notes into this experimental database.

Inference uses an explicitly chosen cached, vetted on-device runtime. Experimental
opt-in may exercise a nonaccepted model for observation/debugging. Normal tracker
startup never enables it. Runtime queue remains 8 episodes/128 KiB with one worker,
at most one retry and 30 seconds per attempt. One native worker failure must not stall
source intake or conceal unprocessed evidence. Cancellation must block stale commits.

Editor snapshots are not `user_note` evidence. Decisions/tasks lacking explicit user
provenance remain tentative, even if a quote looks like an instruction or an AI choice.
An optional explicit pilot-note action may create user-note evidence only while a
verified current source is available; this is intentional thought capture, not manual
artifact association. No automatic completion from a passing test or a disappearing TODO.

A pilot context command answers “what happened here and what is left?” using recent source-backed content, explicit decisions/reasons
when available, open tasks, tentative claims and coverage, with original citations.
An inspection mode shows unassigned/inferred proposals without presenting them as
reliable agent answers. Do not label arbitrary source code as a verified completed
change. No MCP or agent consumption is enabled by this increment.

Use a separate pilot directory/database, independent of ordinary capture memories.
Bridge snapshots are transient and cleared on stop; retained source quotes remain
subject to the semantic 30-day/250 MiB budget. No screenshot/raw-image collector is added.
Before live intake, enforce the total write budget across claims/jobs/evidence/corrections,
schedule retention, and expose budget/resource pause reasons. Existing capture continues
independently if the pilot cannot reclaim space. Model weights remain outside this budget.

## Precision and acceptance work

Create broader labelled development examples and a new heldout split before tuning;
the v2 heldout has already been inspected. Include source-code versus completed-work
statements, mixed passages, observed/AI/user-note provenance, ambiguous references,
similarly named projects, noisy/unrelated content and unknown reasons. Evaluate actual
stored claims and the project-context output separately so unassigned content cannot
be confused with a reliable project answer. Report semantic browser-association recall
separately from deterministic workspace containment when browser fixtures are used.

Keep 95% assertion/association precision, 80% claim/relevant-artifact recall and zero
unsupported decision/completion/citation/privacy failures. Preserve all misses/errors.
No claimed release acceptance if a candidate fails. RAM target stays 3 GiB runtime,
150 MiB other semantic overhead; measure enabled-worker versus baseline, 30-second p95
and 60-second idle CPU at most 2%. Measure longer-session power separately.

Model quality and source/privacy correctness are separate gates. A live experimental
pilot can reveal real-world errors without qualifying the model for default tracking
or AI-agent use. Failure to meet precision must stay visible in UI/docs.

## Verification and user test

Test-first implementation covers extension scope/visible text bounds/focus/disconnect,
bridge permissions/ownership/sequence/timestamp/path validation, native focused-window
ambiguity and secure/unknown context, changed-source discard, dedup/restart/episode
boundaries, all-writer quota/pins/retention, worker timeout/cancel/stale completion and
scoped context/deletion. Preserve the existing 163 tests without weakening privacy gates.
Use controlled extension-host/native smoke only after automated checks; report it
separately from the user's real session. No background live capture starts unrequested.

Then provide reproducible extension/pilot start/inspect/stop commands. The user opens
files across two approved projects, edits/scrolls/switches, briefly leaves
VS Code, exercises pause/resume and verifies excluded files are skipped. Inspect retained
quotes, file/project identity, timestamps, tentative interpretations and coverage after
Ctrl+C. Returning to the same file in a new session must reuse artifact/project identity.
Test source revocation/deletion in the disposable pilot store and retrieve again.

After confirmation, update context, architecture, README, benchmark limitations and a
cofounder handover with actual pass/fail evidence, then push only the feature branch.

## References and next increments

- [Approved semantic design](2026-10-07-automatic-project-memory-design.md).
- [Existing foreground evidence design](2026-10-05-foreground-evidence-design.md).
- [Current semantic status](../semantic-project-memory-status.md).
- [Reviewed model benchmarks](../benchmarks/project-memory/README.md).
- [VS Code API](https://code.visualstudio.com/api/references/vscode-api): active editors,
  visible ranges, document/workspace URIs and window-state events.
- [Workspace Trust API](https://code.visualstudio.com/api/extension-guides/workspace-trust).

Later: permission-checked browser adapters, broader workspace discovery, stronger
semantic relationship corroboration and scoped read-only MCP. Hosted inference remains
an explicit future privacy discussion, with no fallback in this pilot.

## Scope/execution clarification

The approved revision removes the one-project/one-window restriction. It does not
remove permission gates, reliable source identity, quotas or attribution. Existing
inline execution preference persists. Build the end-to-end pilot now and use live
feedback to improve understanding; do not require a passing model before an explicitly
experimental pilot can start. Keep automatic agent consumption disabled. The existing
precision benchmark and any future broader benchmark retain honest failure status.

## Implementation privacy rulings

Registration now uses a transient VS Code tab carrying the random client challenge;
AX focused-window title must match that challenge before and after registration.
Binding cannot silently move to another native PID/window. Events also carry the
current grant revision, preventing pre-pause sources from being relabelled after
resume. Any noncanonical/symlink document URI is rejected, including benign aliases.
These are stricter safeguards within the approved project/workflow direction; actual
extension-host title/accessibility behavior remains pending the user live test.
