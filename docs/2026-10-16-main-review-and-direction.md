# October 16 main integration, review and proposed direction

## Integration

Fetched remote main `9b8efb3` and merged it with local readiness head `82fc2b5`.
Ten conflicted files required resolution: preserve the new UI/controller and
focus diagnostics, while retaining safe runtime cleanup, private logging,
project-specific connection status, startup deadlines and non-disruptive editor
Connect. The earlier readiness fixes had not been pushed, so the cofounder was
not necessarily testing the same code as this local machine.

The supplied Claude artifact URL could not be fetched; review used the tracked
implementation, screenshots supplied by the user and actual native rendering.
Untracked user `context.md` remains untouched. No reset or forced overwrite.

## What the cofounder added

- A consistent blue palette and Figtree across window, pill and note card;
  extracted native `memory_pane.py` with testable presentation helpers.
- Grouped observed snapshots by file, clearer excerpts, explicit Enter-to-search
  state, calmer status presentation and Settings with installation feedback.
- Folder/confirmation sheets and UI sizing/contrast/focus fixes.
- Better VS Code accessibility activation and capture-blocker diagnostics.
  A window can verify a handshake without exposing a focused element, while
  actual text intake still requires a verified readable element.
- Alias `.app` packaging, UTF-8 launch handling and venv PyObjC import priority.
- Explicit consent to register a project-memory MCP connection in Codex;
  AskCodex generates a short explanation from retained project evidence.

The explanatory layer is useful, but generated interpretation is distinct from
the retained evidence and conservative backend decision/task extraction.

## Reproduced faults fixed during review

1. A late AskCodex response from Alpha appeared after selecting Beta. Answers
   now carry project/grant/request identity and are discarded after a switch,
   close, revoke or time-filter change. The selected period is passed to Codex.
2. Every project used one `lmemm_memory` Codex entry: connecting Beta replaced
   Alpha, and revoking Alpha removed Beta. Each grant now gets a stable unique
   MCP entry. AskCodex explicitly supplies its selected grant per invocation,
   including restored or legacy connections. Add/remove operations are serialized
   and revocation fences delayed registration. Regression tests cover the race.
3. The py2app alias's bundled `python` resolves to the base interpreter, where
   MCP was missing on this Mac. Child services/model runtime now explicitly use
   the repo venv without resolving away its `pyvenv.cfg`. Permission probes use
   that environment too; app restart/setup handoff preserves the native launcher
   so it does not silently change identity to a plain Python process.
4. A batching test's October 7 screenshots expired as the real date advanced,
   causing a legitimate extra retention save. The fixture now excludes unrelated
   retention housekeeping; product retention and batching were not changed.
5. Answer UI claimed its visible search cards were the generated answer's exact
   sources, though Codex may retrieve different evidence. It now identifies the
   output as generated, requests exact citation IDs and avoids that false claim.

## Verification and limits

`./build_app.sh` built and signed the alias app. Built app command startup ran
successfully (`status` correctly reported no tracker running). The bundled
Python environment discrepancy was directly reproduced before the worker fix.
Native synthetic drawing covers Memory, sources, Settings and AskCodex states.
The final test counts/results are recorded in current context and acceptance.

The live synthetic AskCodex test uses the same command builder as the UI, with
two newly generated notes, an ephemeral Codex request and explicit scoped MCP
configuration. It passed with one context call and both exact expected citation
IDs. It did not mutate global Codex configuration or send personal memories.
See [hosted evidence](benchmarks/project-memory/hybrid-mvp/codex-oct16.json).

This is a checkout-linked alias app. Moving `dist/LMemM.app` to another Mac does
not ship its repo, venv, model assets or data. Standalone distribution, signing/
notarization, fresh permission onboarding on another Mac, formal sustained
resource/crash acceptance and external users remain unverified launch work.

## Direction — proposal, not a scope change already implemented

The user wants developers **and** general knowledge workers. Unify them around
one workflow: **pick up a project where I left off, across code, documents and
browser work**. Keep one project-memory engine and one resume experience, rather
than separate products for two professions.

Current reality: source-backed hybrid recall is strongest for approved visible
VS Code files and intentional project notes. Broader app tracking exists, but
browser/Docs/email observations are not yet equivalent scoped semantic sources.
AskCodex also depends on Codex setup and provider access; it is not fully local
inference and is not an effortless general-user prerequisite.

Recommended order:

1. Make the common resume flow the product's front door: what I was doing,
   recorded decisions, unfinished actions and supporting sources. Existing
   snippets/search stay available for inspection. This is a UX proposal, not a
   claim that a complete automatic resume brief is already shipped.
2. Make notes/context useful without requiring a coding workspace or Codex.
   Preserve copyable project context for the AI the user already uses; keep
   provider disclosure explicit. Optional direct AI explanations can sit on top.
3. Add one controlled browser/document source path, with project assignment and
   provenance, before broad passive cross-app ingestion. It should benefit both
   developers reading docs and knowledge workers doing research.
4. Test the same job with both groups: two developers and two research/operations
   users. Ask each to resume a real interrupted project and measure setup time,
   time to a useful correct answer, missing sources and whether they return.
   These people have not been contacted or results fabricated.

Do not pivot away from the memory infrastructure solely because setup was hard.
First test whether this narrower shared outcome earns repeat use. If users do
not resume projects with it even after setup friction falls, reconsider the job
and positioning before building more connectors or graph features.

The immediate USP to validate is continuity with provenance and controlled agent
handoff, not a knowledge graph visualization or another generic chat box.
