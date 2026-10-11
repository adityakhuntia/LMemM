# Hybrid project memory MVP — project tabs and agent resume

Date: 2026-10-10. Status: draft for user review; implementation not authorized by this document yet.

## 1. Outcome and agreed scope

A Mac developer returns to an approved coding workspace after a break, opens its
Memory tab or asks a connected agent to resume, and retrieves relevant retained
evidence, explicit decisions/reasons, and open tasks with inspectable citations.
The user does not manually file each source or construct a graph.

Agreed with the user: VS Code visible local-file excerpts plus intentional project
notes; keyword + local vector retrieval; a small evidence-backed graph; read-only
MCP for one agent client; build on the existing native UI using **Overview · Memory**
project tabs. No visual graph explorer. This is a focused developer beta with a
two-week target, contingent on acceptance, not a promise of broad public readiness.

This specification supersedes the launch scope in the October 7 automatic-memory
and live-pilot specifications/plans. Their implemented contracts, tests and historical
results remain reusable evidence, not proof of this increment's acceptance.

The detailed defaults below are author recommendations for review, not additional
user decisions. Existing source/privacy protections must not be weakened to meet
the deadline. The current native abort guard requires a successful live retest.

## 2. What exists and what changes

Reuse semantic_memory/ for evidence, canonical identity, episodes, extraction,
retention and citations; extensions/lmemm-source/ for visible-source intake; and
src/window.py + page_model.py for native navigation. Normal JSON notes/projects
and the experimental SQLite store currently operate separately. There is no
embedding index or MCP service. The current local extractor has not passed general
assertion-quality acceptance. A successful single-project note demonstration is
not acceptance for automatic everyday understanding.

The new retrieval path searches evidence even if extraction failed or never ran.
Graph claims enrich results; they are not a prerequisite for finding a passage.
Preserve the normal tracker/pill behavior and existing JSON data. Do not turn old
screen/OCR history, browser activity, or the new event trail into semantic input.

## 3. Source authorization and project identity

- Reuse trusted local VS Code visible-range capture, canonical root/file identity,
  native focus validation, exclusions, ordered private bridge messages and revocation
  barriers. No full-repository crawl, terminal output, remote buffers or hidden files.
- Per-workspace enrollment is explicit. Approving the normal app or a screen-capture
  permission does not enroll a semantic workspace or authorize an agent.
- Each enrolled root has one stable semantic project ID. Associate it with one UI
  project ID through a persisted mapping, never a title match. Multiple roots per UI
  project and semantic parent/child rollups are deferred.
- On enrollment, offer a new project named after the workspace (default) or an
  existing unlinked project. This one-time choice does not require per-artifact filing.
  Same-name workspaces remain distinct; show the canonical path in project settings.
- UI project rename preserves the mapping. Workspace relocation requires explicit
  relinking; do not merge paths or same-name projects heuristically.
- Ordinary item filing remains organization of normal-tracker items. It does not
  grant memory access, move semantic evidence, or silently enlarge the mapped root.
- Moving a linked UI project within the tree preserves its scope. Merging linked
  projects is blocked for this MVP with an explanation. Archive hides navigation
  without deleting memory or revoking a grant. Project deletion requires separate
  explicit memory deletion/unlink handling and invalidates agent access immediately.

Intentional notes from the editor adapter already carry workspace identity. For the
existing native note UI, enroll only notes deliberately saved to the selected mapped
project or an authoritatively mapped file; ambiguous foreground/OCR notes stay in
Overview with a link to choose a project. Do not infer a note's semantic project from
window titles. This increment indexes new eligible notes after enrollment. Historical
note import is deferred; the UI states the enrollment start time.

Existing note text and done/reopen status remain owned by the normal note store when
created there. Use stable note IDs, revision/content hashes and idempotent reconciliation
to mirror eligible notes/state into SQLite. Persist normal mutations before publishing;
reconcile on startup and after changes. Show pending synchronization, and omit stale
note-derived task state from resume packets until synchronization succeeds. Deletion
must tombstone/revoke the mirror before returning success. Adapter-created notes have
SQLite as authority. No bidirectional text-edit sync is added. Define explicit adapters
rather than silently merging normal and pilot schemas.

## 4. Runtime and lifecycle

One local memory service owns SQLite writes, ingestion, indexing and retrieval. The
normal app supervises it when Memory is enabled; manual pilot/model commands are not
the beta startup flow. The existing private VS Code file bridge remains the intake
transport. UI requests and the stdio MCP adapter use a versioned local Unix socket
with private directory/socket permissions and separate per-client capability grants.
MCP cannot write the database, alter policy, start capture or enroll projects.

The service must run native focus/event processing on its main thread as required;
workers never inspect the service/app's own UI. Explicitly exclude both service and
supervising app PIDs from self-observation. AppKit UI rendering stays on the UI thread.
IPC, indexing, inference and queries must not block the UI event loop.

One supported embedding runtime/model is packaged/configured for the beta. Memory
setup states the model download size and local disk location before installation.
Inference and embedding stay local with no cloud fallback; model downloads contain
no user evidence. Reuse the existing approved local-runtime validation where possible.
The exact model, embedding library and vector representation are builder choices,
selected and pinned through the benchmark below before default enablement. Prefer
reusing SQLite and avoid a separate vector server or new graph database.

One bounded background model job runs at a time; query embedding has priority between
jobs. Capture persists evidence without waiting for embeddings. Unavailable models
leave keyword search usable with an explicit degraded status. Pause stops intake and
background model jobs; existing permitted keyword recall remains available. Retrieval
while paused does not restart models. Revocation removes retrieval immediately. Quit
stops the supervised service; MCP then reports service unavailable. Restart reconciles
sources, resumes bounded queues and does not duplicate evidence. Lock/sleep requires
explicit resume for intake, matching the pilot's conservative behavior.

## 5. Evidence and hybrid retrieval

Retain immutable dated occurrences pointing to deduplicated text. Chunk by permitted
source spans/paragraph boundaries within the existing 4 KiB span and 16 KiB envelope
limits; a chunk never mixes projects, artifacts, authorship types or permission scopes.
Long spans may split into bounded overlapping chunks; offsets resolve to original text.
Exact chunk size/overlap is benchmarked and versioned. Edited content produces a new
occurrence/revision; old retained evidence is historical, not current file state.

Maintain FTS keyword and vector indexes for the same eligible chunks. Cache embeddings
by text hash + model/version + chunking version, while keeping occurrence ownership
separate. Shared embeddings do not share authorization. Revision changes cannot expose
stale content through metadata, snippets or cached result packets.

For a query:
1. Resolve the authorized project, source scope, time filter and policy revision.
2. Retrieve up to 50 permitted keyword candidates and 50 permitted vector candidates.
   Filter before candidate selection; global top-k followed only by filtering is invalid.
3. Fuse ranks (reciprocal rank fusion as the initial default), collapse duplicate text
   while retaining dated provenance, and select up to 10 primary results.
4. Expand one hop through supported relationships, at most 10 additional evidence
   entries, rechecking identical permissions, project boundaries and time rules.
5. Return deterministic structured results and source previews. Recheck policy revision
   before return; discard/recompute if access changed during the query.

Semantic similarity yields relevant evidence, not confirmed membership or a decision.
No cross-project search in the first release. Recency is a tie-breaker or explicit filter,
not permission to hide older highly relevant evidence. Each result has its original
source type, timestamp, artifact, citation ID and truncation status. Label observed
file excerpts as observed; do not claim the user authored or changed them.

## 6. Small graph and supported claims

Prioritize belongs_to (authoritative workspace containment), supports (exact retained
claim evidence), and references (explicit paths to known permitted artifacts). Resolve
relative paths against the source artifact/workspace; ambiguous or out-of-root paths
stay unlinked. Do not open referenced files that were not independently captured.

Keep existing correction/contradiction/supersession machinery, but broad inferred
relationships are not a launch dependency. Do not promote similarity links to facts.
Inference-derived relationships remain tentative and excluded from confident packets.

Resume decisions/reasons require explicit source support and attribution. Open tasks
require explicit user intent; completion/reopening comes from an explicit state action
or supported transition. Use existing deterministic intentional-TODO behavior. A code
TODO is searchable evidence, not automatically a user's commitment. Reasons absent
from evidence are shown as not recorded.

A local extractor may be enabled as an experimental feature, but default MCP/resume
claims must pass the assertion gate or come from deterministic explicit user intent.
This does not block evidence search. No additional generative answer model is needed
inside the Memory UI; the connected agent may compose a response from the same packet.

## 7. Project tabs and user-facing proof

Reuse the existing project sidebar, breadcrumbs, window and keyboard navigation.
Every project page has **Overview · Memory**. Overview keeps existing notes/items and
Pick up. Memory is the project-scoped view described below. Existing sidebar search
continues to find normal items/projects; a distinct search field inside Memory searches
retained project evidence. Never silently change search scope while the user types.

Memory includes:
- Project path/scope and a compact status: Disabled, Ready, Processing N updates,
  Paused, or Needs attention. Show last indexed time and enrollment start.
- Search placeholder: "Search this project's memory". Submit on Return (no model call
  on each keystroke); show query progress/cancel and preserve previous results on error.
- Time choices: Last 2 days (default), Last 7 days, All retained. Open tasks may predate
  the chosen period and are marked with their original date; search obeys the filter.
- Without a query, a deterministic resume view with Supported decisions, Open tasks,
  and Recent evidence. Do not label observed evidence as completed work. Empty claims
  sections say no recorded decisions/tasks, not that nothing happened or all work is done.
- With a query, ranked evidence cards plus supported claims where available. Every card
  shows source/file, timestamp and a short passage; relevant unclassified evidence is visible.
- "View source" opens a detail drawer with the exact retained passage, original capture
  time, source type, path/note origin and truncation. "Open file" is available only for an
  existing permitted local file, and states that today's file may differ from the snapshot.
- Simple labels: Observed content, Your note, Tentative interpretation. Tentative material
  is collapsed by default and never presented as a confirmed decision or task.
- Coverage line: retained period, pending/failed indexing, unprocessed extraction and
  truncated inputs. No numeric confidence score or claim of complete work history.

For an unenrolled project, Memory offers "Enable project memory" and workspace mapping;
it does not display remembered activity as semantic evidence. If the model is missing,
show setup plus keyword-only availability. Distinguish no captured evidence, no query
matches, source revoked/deleted, paused collection and service unavailable. Failed
indexing must not appear as "no results" without explanation.

Secondary action: **Preview agent context**. Select the configured agent grant and
show its exact scope/time and normalized packet; UI content outside that grant is not
included. When no client is connected, preview a clearly labelled proposed grant,
without creating or transmitting it. Copying/exporting is explicit. The preview and
MCP call use the same backend function and revision. A selected citation opens the
same source drawer. Private fields/tokens never appear in the preview.

Put "Connect an agent" in Memory setup/settings, not on every card. Target one stdio
MCP client for acceptance (author default: Codex). Use existing native visual styles;
no new design system, graph visualization, chatbot page or keyword/vector mode switch.
The UI must make the backend observable: enrolling yields evidence; a paraphrased query
finds it; a source click verifies it; context preview shows what an agent can receive.

## 8. MCP and scope contract

Three read-only tools:
- search_project_memory(project_id, query, optional start/end, limit<=10)
- get_project_context(project_id, optional start/end)
- resolve_citation(project_id, citation_id)

Absent time bounds default to the last two days; explicit All retained is normalized
by the UI/adapter to the retained interval. Query length capped at 2 KiB UTF-8. Packets
are capped at 16 KiB, include schema/policy revision, time scope, omissions and coverage;
citation text is fetched separately, at most one retained span per resolution.

The configured per-client grant fixes allowed project IDs and source scopes. Tool
arguments can narrow, never widen it. Validate project ownership again during citation
resolution: a permitted app ID alone is insufficient. Unauthorized and nonexistent
projects/citations return the same unavailable response, without leaking existence.
Agent connection is separate opt-in authorization; explain that a hosted agent may
transmit retrieved material even though memory processing is local. Retrieved text is
untrusted evidence, never instructions to the service. No write/proposal tools this release.

## 9. Retention, deletion, quotas and model changes

Use the existing 30-day evidence policy and 250 MiB semantic budget, now INCLUDING
vectors, FTS, SQLite side files, bridge buffers and durable job metadata. Model weights
are separate and disclosed. One indexing/inference worker, bounded pending payload
(8 episodes/128 KiB as the initial limit); persistent backlog references source IDs,
not unbounded copies of source text. At pressure, expire unpinned evidence and its
indexes; preserve pinned notes, otherwise pause intake and explain why.

Deletion/revocation invalidates sources, graph support, both indexes, caches and queued
jobs. Query-time authorization blocks access before asynchronous physical cleanup.
Reconciliation must not resurrect a tombstoned source. Jobs commit only if their source
and policy revisions remain valid. Deleting one occurrence of shared text does not
remove another allowed occurrence, or retain the deleted occurrence's provenance.

Persist embedding dimension/model digest/chunk version. A change creates a new index
generation; never compare vectors from different models. Rebuild only permitted retained
text within quota, use keyword-only while rebuilding, and atomically switch generations.
Interrupted rebuilds resume or discard safely. No silent model download/upgrade.

## 10. Acceptance gates and measured product benefit

Software regression passes are necessary but not sufficient. Use disposable approved
fixtures and consented external testing; do not tune on held-out results.

A. Retrieval: prepare at least 40 labelled queries over two projects and two sessions,
including exact identifiers, paraphrases, older decisions, ambiguous same-name files,
unrelated content, stale/deleted sources and questions with no evidence. Freeze at least
20 queries as held-out with at least 10 paraphrases. Compare identical authorized corpora
and chunking under keyword-only, vector-only and hybrid retrieval. Target hybrid Recall@5
>=80% overall, paraphrase Recall@5 at least 10 percentage points above keyword-only,
and exact-identifier Recall@5 no worse than keyword-only. Report counts and ranking
quality (MRR), not just aggregate percentages. No-evidence queries show matched sources
as such and never fabricate answers; low-relevance handling is calibrated on development
queries and checked on held-out examples.

B. Claims: default supported claims achieve >=95% precision and zero unsupported decision,
reason or completion assertions on a fresh labelled suite. Tentative/model-disabled paths
must remain useful through evidence retrieval. Report recall and omissions; an empty
extractor cannot be presented as semantic success.

C. Scope: zero cross-project, denied, revoked or deleted evidence leaks through results,
expansion, snippets, citations, previews or MCP. Test concurrent revocation/indexing/query,
shared text ownership and hostile source instructions.

D. End-to-end: enroll two workspaces, capture visible content and intentional notes, record
and complete/reopen a task, quit/restart, then resume through UI AND the chosen agent.
Verify paraphrase retrieval, correct project identity, exact citations, source inspection,
preview parity and deletion. Real native test includes repeatedly opening/closing project
windows, switching apps, pause/resume and lock/sleep recovery. The crash guard remains
unaccepted until that sequence succeeds.

E. Resources: on the target M2 Pro/32 GiB Mac, compare baseline and Memory-enabled runs
for at least 30 minutes of representative work plus 60 seconds idle. Proposed targets:
additional runtime peak <=3 GiB (embedding plus any enabled extractor), non-model semantic
overhead <=150 MiB, idle additional CPU <=2% of one core, warm search p95 <=2 seconds on
10,000 permitted chunks, and evidence searchable within 30 seconds when queue is not
backlogged. Measure cold start, energy where available and disk growth separately. Show
index progress rather than freezing UI. Failures require explicit scope/budget revision.

F. Usability: at least three consented testers outside implementation can enroll, search,
inspect a citation and connect the chosen agent from the runbook. Compare resume time
and recap effort with their normal workflow; record failures and qualitative usefulness.
Do not claim measured time savings before running this comparison.

## 11. Delivery and non-goals

Sequence, to be expanded into an implementation plan after approval:
1. Native stability retest, source/project contracts, safe lifecycle and resource baseline.
2. Incremental chunks/embeddings + FTS + authorized hybrid retrieval and benchmark.
3. Native project-note synchronization and Overview/Memory/source-detail UI.
4. Read-only MCP, grant-specific preview and one actual agent-resume demonstration.
5. Fresh quality/privacy evaluation, restart/lifecycle testing and small external beta.

Work can be scheduled within two weeks only after estimating the implementation plan.
If time slips, defer experimental claim extraction and cosmetic polish first. Keep
hybrid retrieval, evidence inspection, authorization/deletion and the complete resume
workflow; do not ship unrelated modules as if the promised loop were complete.

Not in this increment: browser semantic ingestion, universal app memory, background
repository crawling, historical OCR imports, arbitrary project discovery, a visual
graph, broad automatic graph inference, multi-root rollups, agent writes, proactive
recommendations, cloud inference or general-purpose chat. Normal app features already
present remain usable without becoming new semantic sources.

## 12. Review and decisions still delegated

User approved the scope direction and project tabs, not yet this full written design.
Builder choices: embedding model/runtime and vector storage representation after measured
comparison; internal module boundaries, bounded chunking parameters, schema migrations,
IPC framing and native drawer implementation. These cannot alter scope/privacy/acceptance
contracts. Existing module layout and docs/specs + docs/plans conventions are retained.
