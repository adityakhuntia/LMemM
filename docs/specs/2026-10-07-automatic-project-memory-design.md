# Automatic project memory for AI agents

Date: 2026-10-07. Status: proposed written spec for user review; no graph implementation started.

## 1. Product contract

The first useful outcome is **resume work on a coding project**: an AI agent can
retrieve what changed, explicit decisions/reasons, and open tasks from two days
ago, with dated source evidence and visible uncertainty. Users do not manually
build a graph or attach every tab. Projects are initially anchored by workspace
folders and document context; arbitrary project discovery comes later.

Initial live scope is VS Code and user-permitted browser sites. Semantic inference
is strictly on-device. Hosted inference is a future privacy discussion, not a
fallback. No captured text, image, embedding or summary goes to a hosted model.
All performance and storage numbers below are proposed MVP defaults/acceptance
targets for review, not measurements of the current implementation.

## 2. Approach and delivery boundaries

Choose automatic linking grounded in source evidence. A local model interprets
bounded work episodes, while application code controls identity, permission,
provenance, relationship validation and retrieval. Automatic association does
not require repeated user confirmation; uncertain associations stay tentative.
Optional corrections override inference and are retained as user assertions.

Rejected primary approaches: a manually curated graph creates unwanted work;
asking a model to rebuild a graph from every screenshot repeats content, raises
resource use and obscures identity/provenance mistakes.

Deliver in three separately reviewable increments:

1. **Trusted live sources:** app/site access policy, verified foreground capture,
   authoritative workspace/file identity and browser context. Adapt the existing
   foreground-evidence spec to `macos.py` and add the source contract below.
2. **Automatic semantic-memory core (specified here):** source ingestion,
   deduplicated evidence, episodes, local extraction, automatic relationships,
   bounded persistence and source-backed project retrieval. Validate through
   controlled fixtures before enabling the live source adapter.
3. **MCP adapter:** expose that retrieval contract with explicit project/evidence
   scopes. The transport must not implement another semantic interpretation path.
   Agent access is local; a connected hosted agent may send retrieved material
   elsewhere, so users must separately authorize that consumer.

Do not describe fixture success as a live-ready MVP. MCP and automatic live
collection are not part of increment 2's initial acceptance.

## 3. Source and identity contract

Each source envelope contains an immutable source ID, timestamp, session ID,
app ID, artifact locator, optional authoritative workspace locator, permitted
text spans, origin type, and permission-policy revision. Origin types are user
note, observed screen text, or trusted artifact snapshot; screen text has unknown
authorship unless separately established. Text spans have stable IDs and explicit
truncation flags. Only envelopes passing the current access policy may enter.

Canonical workspace paths anchor coding projects. Canonical file paths within
that workspace anchor code artifacts; titles/basenames alone are insufficient.
Browser artifacts use canonical URLs and document IDs where available. Strip
fragments and known tracking parameters, but retain query parameters that may
identify distinct documents. Never merge two workspaces because names match.

The current OCR/window-title rules do not provide authoritative VS Code file
paths. The live-source increment must obtain structured workspace/file metadata
through an explicitly enabled editor adapter; it must not read arbitrary files
or treat a parsed window title as an authoritative path. Until then, unsupported
identities remain tentative/unassigned. Fixtures provide explicit locators.

Access is deny-by-default for the new semantic flow: allowlisted apps and browser
origins, with exclusions/private/unknown-browser context overriding permission.
VS Code input permission does not itself authorize screen/content ingestion.
Granting access to an app does not silently authorize all browser sites.

## 4. Evidence and episodes

Normalize whitespace for content deduplication, keeping original retained text
for citations. Store unique text blobs by content hash, with separate source
occurrences so repeats retain distinct timestamps, artifact and permission scope.
Deduplication must not collapse ownership or deletion relationships.

Use changed content and context boundaries to form an episode. A new artifact,
five-minute gap or permission/pause boundary ends the prior episode; flush an
active episode after two minutes or 16 KiB of retained text, whichever comes
first. A new task after a boundary never inherits an old typing association.
These are adjustable initial constants, not claims about cognitive boundaries.

Retain up to 4 KiB per text span and 16 KiB of evidence per extraction request.
Truncation remains explicit. Append changed blocks; do not store full duplicated
OCR on every capture. Queue completed episodes rather than repeated frames.
Raw input remains existing bounded summaries, never typed characters.

## 5. On-device understanding

An inference adapter consumes a bounded episode, evidence spans and at most eight
candidate project/artifact summaries. It returns structured claim and relationship
candidates referencing supplied evidence IDs. Its contract is independent of a
particular model runtime. Runtime must have no hosted endpoint or network fallback.

Required candidate fields: type, subject/object IDs or source-local proposed
entities, evidence span IDs, paraphrased statement, and extraction status. Reject
unknown evidence references, invalid types, oversized fields or malformed output;
one bounded retry is allowed, then retain the episode as unprocessed. Model failure
must not erase evidence or halt capture.

Distinguish observations, suggestions, inferred tasks, explicit decision quotes
and explicit user notes. A model cannot promote an AI suggestion into a user
decision or infer completion from a tab/window disappearing. Reasons exist only
when supported by a cited span. Quoted third-party decisions remain attributed
to their source. Conflicts are retained; later explicit evidence can supersede
earlier claims without overwriting history.

Model selection is a **benchmark deliverable before live inference**, not an
unspecified coding choice. Compare locally runnable candidates on the fixtures
and resource targets in section 10; select the smallest passing configuration.
If none passes, report the failed criteria and revise scope/model budget with the
user. Do not silently use hosted inference or call lexical rules semantic success.
Downloading model weights, if needed, is distinct from sending user content.

## 6. Automatic relationships

Entities: project, artifact, episode and claim. Claim subtypes: observation,
task, decision and suggestion. Edges: `belongs_to`, `references`, `supports`,
`supersedes` and `contradicts`. Each edge records evidence occurrence IDs,
first/last support times, method and status (`inferred`, `supported`, `user_asserted`).

Deterministic workspace containment supplies supported code membership. Browser
membership uses a local semantic assessment with candidate projects derived from
nearby workspace episodes and content search. Switching patterns contribute
context but cannot establish membership by themselves.

Promote inferred browser membership to supported only with cited semantic
support plus either an explicit artifact/project reference or repeated support
in separate episodes with the same project anchor. General documentation may
support multiple projects; membership is many-to-many. A second weak guess is
not independent corroboration. Ambiguous candidates remain inferred/unassigned
and are excluded from confident project summaries.

Confidence is an evidence/status policy measured against fixtures, not an LLM's
self-reported probability. Optional corrections can assign, reject or remove an
association; a rejected association is not immediately recreated by inference.

## 7. Lightweight persistence

Use a separate versioned SQLite store for the semantic core. Keep the current
JSON index/timeline as the capture layer during the first increment; no silent
rewrite of legacy memories. Idempotent ingestion records source IDs and schema
versions. Tables cover projects, artifacts, text blobs, occurrences, episodes,
claims, edges, support references and corrections. Foreign keys and transactions
make source ownership explicit.

Start with SQLite FTS5 for candidate search; do not embed every frame or require
a graph database. Semantic interpretation comes from local episode extraction,
not from calling keyword similarity understanding. Add a bounded embedding index
only if evaluation demonstrates a retrieval gap. One serialized writer and one
inference worker; no unbounded background work or continuous inference stream.

Proposed defaults: new raw semantic-source images expire within 24 hours and a
500 MiB raw budget; semantic storage budget 250 MiB including SQLite side files
and indexes, excluding model weights. Retain durable evidence for 30 days by
default; user-authored notes/corrections may be pinned, but still count toward
the budget. Raw images are optional citations; text evidence is retained with
claims so raw expiry does not silently destroy all support.

At budget pressure prune expired/unpinned source evidence and dependent graph
state, then old unpinned episodes. Never retain an apparently supported claim
after deleting its last support. Never discard pinned material silently: if
space cannot be reclaimed, pause semantic ingestion and show a visible reason.
Capture has its own budget/status; do not imply this bounds legacy JSON/JPEG
files. Default retention is a tradeoff to review, not guaranteed permanent recall.

## 8. Deletion and permission revocation

Deleting a source/session or revoking an app/site scope immediately removes it
from retrieval. In one transaction remove its occurrences/support and recompute
affected claim/edge support. Remove unreferenced text blobs and FTS entries;
invalidate cached summaries and unfinished extraction work. Shared content
retained for another allowed source remains owned by that other occurrence.

Deletion must integrate with existing capture provenance rather than leave two
independent notions of source ownership. Retention never overrides explicit
deletion. Local plaintext storage and operating-system backups remain disclosed;
logical deletion does not promise forensic erasure of SSDs or backups.

## 9. Project resume output

The retrieval API consumes project ID, requested time interval and authorized
source scope. Return bounded sections: recent changes, explicit decisions/reasons,
open tasks, relevant artifacts, conflicts/unknowns, evidence citations and
coverage/truncation information. Citation IDs resolve only within that same scope.

Infer a task as a candidate, not a verified commitment. Task state begins open
only for explicit user/source commitments; other proposed tasks are labelled
inferred. Completion/reopening needs explicit evidence or a correction. Display
uncertain associations separately. When evidence expired or a model failed, say
the period has incomplete coverage instead of inventing a coherent story.

MVP output is structured context, with a deterministic readable rendering. An
agent may formulate its own response from that packet; the memory layer need
not run another generative summarization model on every retrieval.

## 10. Acceptance and benchmark gates

Create at least 20 synthetic/consented labelled episodes spanning two projects,
related references, unrelated interleaving, same-title artifacts, project rename,
AI suggestions not adopted, explicit decisions, unsupported reasons, task done/
reopen, contradictory notes, ambiguous membership and deleted/revoked evidence.
Hold out at least one-third for evaluation; label accepted relationships and
claims before comparing models.

Proposed release thresholds: at least 95% precision on supported associations,
at least 80% recall on labelled relevant artifacts, zero unsupported decision or
completion assertions in this suite, and zero excluded/deleted-source leakage.
Report denominators, unresolved episodes and errors; a small passing fixture set
does not prove universal accuracy. Never tune thresholds on held-out examples.

On the actual target Mac, measure baseline versus semantic-enabled runs:
resident/peak RAM, average CPU, extraction latency, disk growth and energy metrics
where available. Proposed budgets: one concurrent inference, queue at most eight
episodes/128 KiB, model/runtime peak additional RAM at most 3 GiB, non-inference
semantic overhead at most 150 MiB, idle average CPU at most 2% over 60 seconds,
and 95th-percentile episode extraction at most 30 seconds. CPU and energy under
active inference are measured/reported rather than claimed constrained by queue
size. Resource suitability remains open until the hardware benchmark passes.

On overload apply backpressure and report deferred/unprocessed coverage; do not
discard evidence silently or block the main capture thread. Pause/lock/revocation
cancels pending inference for newly forbidden sources. Restart resumes idempotently.

## 11. Implementation handoff

After written-spec review, prepare a plan for **increment 2**: storage/source
contract, episodes, inference benchmark/adapter, relationship policy, retrieval
and evaluation. Treat live sources and MCP as separate follow-up plans. Pin a
model/runtime only after the benchmark gate; the plan must include that decision
and specify how a failed benchmark stops live enablement.

Existing foreground-capture work remains a prerequisite, not cancelled. Broader
companion UI, automatic new-project discovery, hosted inference, global keyboard
logging and general-purpose agent write access are out of scope.
