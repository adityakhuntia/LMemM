# Knowledge graph understanding — discussion brief

2026-10-07. Brainstorming only; no approved implementation design or graph code.

## Agreed purpose

The MVP serves AI agents: accurate project knowledge, retrieved through MCP,
with explicit user app/site access controls and benchmarked resource use.
Users may assign artifacts to projects manually. Automatic linking is desirable,
but observed switching/content alone cannot prove a relationship or user intent.

The user selected **resume work on a project**: what changed, why, and open tasks,
each backed by dated sources. Project identity/association scope is the next
open question. Recommended first anchor: a selected workspace folder with
explicitly attached documents/tabs; inferred links remain proposals.

## Approaches to compare

1. **Evidence-first hybrid (recommended):** explicit projects/artifact links and
   user notes form the trusted core. A model proposes typed relationships and
   claim candidates with source spans; only supported/confirmed material feeds
   confident agent answers. More incremental, easier to evaluate and correct.
2. **Automatic model-built graph:** infer entities/relationships from every
   capture. Less manual work, but ambiguous context, authorship, duplicate
   identities and resource/privacy cost make a useful accuracy baseline harder.
3. **Manual graph only:** deterministic project associations and user facts,
   exposed through MCP. Reliable baseline, but misses contextual understanding
   and creates ongoing curation work.

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

For a project-resume request, return a compact context packet: scope/time range,
recent work, decisions with reasons when explicit, open tasks, conflicts/unknowns,
and citations to permitted sources. Absence of evidence must stay visible.

Build a small consented fixture set before automatic inference: related and
unrelated tabs interleaved, identical titles on different projects, renamed
artifacts, AI suggestions not adopted, completed/reopened tasks, contradictory
notes, and revoked/deleted sources. Evaluate relationship precision, unsupported
claims, retrieval usefulness, permission leakage, latency and resource cost.

## Open design decisions

- First agent workflow and a concrete example of a useful answer.
- Project association UI/CLI and the minimum reliable artifact identities.
- Local model, hosted opt-in model, or explicit-only initial extraction.
- Which claim classes can be inferred and how corrections/confirmations work.
- MCP scopes, tool contracts, citations and permission revocation semantics.
- Capture/inference budgets and benchmark acceptance thresholds.

Do not select a graph database merely because the product is called a graph.
Choose persistence after the entity/relationship, evidence and query contracts
are defined. Transactional relational storage may represent the initial graph.
