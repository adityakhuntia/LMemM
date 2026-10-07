# Knowledge graph understanding — discussion brief

2026-10-07. [Written spec](specs/2026-10-07-automatic-project-memory-design.md) approved; [semantic-core plan](plans/2026-10-07-automatic-project-memory.md) written and awaiting review. No graph code exists.

## Agreed purpose

The MVP serves AI agents: accurate project knowledge, retrieved through MCP,
with explicit user app/site access controls and benchmarked resource use.
Automatic semantic understanding and relationship building are required.
Manual association is optional correction, not a prerequisite. Observed
switching/content alone cannot prove a relationship or user intent.

The user selected **resume work on a project**: what changed, why, and open tasks,
each backed by dated sources. The user selected automatically connecting
activity to projects inferred from workspace folders and document context first.
Discovering arbitrary new projects comes later. No manual attachment step is
required; ambiguous relationships remain proposed or unassigned.

## Approaches to compare

1. **Evidence-first automatic linking (selected direction):** stable workspace
   and document identities anchor candidate projects. A model interprets bounded
   work episodes and proposes typed relationships/claims with source spans.
   Identity, repeated context and semantic support govern automatic association;
   weak links remain tentative. Manual confirmation is not required for every
   supported link. Automatic does not mean every model guess becomes a fact.
2. **Automatic model-built graph:** infer entities/relationships from every
   capture. Less manual work, but ambiguous context, authorship, duplicate
   identities and resource/privacy cost make a useful accuracy baseline harder.
3. **Manual graph only (rejected as the product workflow):** reliable baseline,
   but creates the curation burden the user explicitly wants to avoid.

## Proposed understanding and storage flow

Meaningful content changes plus app/tab/input boundaries create work episodes.
Local deduplication removes repeated OCR and interface noise. Inference runs on
bounded episode evidence, not every screenshot. Output contains source-backed
topics, artifact/project links, claim candidates, decisions and tasks with their
epistemic status. Switching patterns contribute weak context; semantic similarity
alone is insufficient to establish membership or intent.

Separate short-lived raw captures from durable deduplicated text, compact episode
summaries, entities/edges and selected search embeddings. Use content hashes and
incremental changes to avoid repeating unchanged content. Bound inference queues,
raw disk usage and embedding growth; preserve enough evidence to check summaries.
Deleting/revoking evidence must remove or invalidate dependent claims and indexes.
SQLite is a persistence candidate, not a finalized implementation decision.
Exact retention and resource budgets require measurement and user policy.

## What sensible understanding must distinguish

- Artifact identity versus an OCR fragment or changing title.
- Observation versus a claim, inference, explicit user decision or open task.
- Project membership versus merely switching between two windows.
- Current state versus historical, superseded or contradicted statements.
- Author/source versus the user's own intent. AI output is not a user decision.
- Retrieval relevance versus permission to disclose evidence to an agent.

Potential minimal model: projects, artifacts, dated episodes, source evidence,
and typed claims/tasks/decisions. Each relationship needs provenance and a
status such as observed, proposed or confirmed. Confidence must reflect measured
support, not just a model's numerical self-report. Keep corrections and deletion
traceable through dependent claims and exports.

## Agent output and evaluation

### Proposed first acceptance scenario

Use a consented, synthetic coding-project fixture (not a claim about actual
captured work): edit a local project's storage code, consult a relevant database
reference tab, observe an AI suggestion, record an explicit decision and an open
test task, then visit an unrelated site. Resume the project two days later.

The agent should retrieve the code artifact and supporting reference, distinguish
the AI suggestion from the explicit decision, return the still-open task, and
exclude the unrelated site. Every asserted change/reason/task links to its dated
source. If the decision reason was never captured, report it as unknown.

First proposed implementation boundary: workspace/project and artifact identity;
deduplicated episode evidence; on-device typed extraction; conservative automatic
relationship proposals; persisted evidence/status; project context retrieval.
Do not add unrestricted project discovery or proactive companion features.
MCP should expose the same tested retrieval contract rather than introduce a
second interpretation path.

Graph edges should describe a specific supported relationship (`belongs_to`,
`references`, `supports`, `supersedes`) rather than merely "related". Model output
must reference supplied evidence IDs; application validation rejects unknown
references and unsupported structured fields. Those checks alone do not prove
semantic accuracy, so fixture evaluation remains required.

Source scope for the first scenario is agreed: VS Code plus explicitly
permitted browser sites. Current screen capture is not sufficiently isolated to
treat its entire image as authorized foreground evidence; fix that boundary
before collecting new semantic training/evaluation examples from real use.

For a project-resume request, return a compact context packet: scope/time range,
recent work, decisions with reasons when explicit, open tasks, conflicts/unknowns,
and citations to permitted sources. Absence of evidence must stay visible.

Build a small consented fixture set before automatic inference: related and
unrelated tabs interleaved, identical titles on different projects, renamed
artifacts, AI suggestions not adopted, completed/reopened tasks, contradictory
notes, and revoked/deleted sources. Evaluate relationship precision, unsupported
claims, retrieval usefulness, permission leakage, latency and resource cost.

## Open design decisions

- A concrete project-resume example and the minimum reliable artifact identities.
- **Decided: inference stays on-device for the current MVP.** Hosted inference
  remains a future privacy discussion, not an enabled fallback. No captured
  content, embeddings or summaries may be sent to a hosted model.
- Which claim classes can be inferred and how corrections/confirmations work.
- MCP scopes, tool contracts, citations and permission revocation semantics.
- Capture/inference budgets and benchmark acceptance thresholds.

Do not select a graph database merely because the product is called a graph.
Choose persistence after the entity/relationship, evidence and query contracts
are defined. Transactional relational storage may represent the initial graph.
