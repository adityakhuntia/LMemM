# Project-memory direction

Updated 2026-10-10. Active design:
[Hybrid project-memory MVP](specs/2026-10-10-hybrid-project-memory-mvp.md), approved by the user; the
[implementation plan](plans/2026-10-10-hybrid-project-memory-mvp.md) is ready for review. The October 7 automatic-memory specification records
the earlier extraction-first scope and is superseded for future implementation.

The product outcome is project continuity: a developer and their connected agent
can recover relevant evidence, supported decisions/reasons and open tasks without
manually rebuilding context. Automatic workspace association remains the default;
manual artifact filing is not required.

The selected approach combines exact identity and metadata, keyword search, local
vector retrieval and a small supported graph. Evidence remains searchable even if
claim extraction fails. Similarity finds candidate relevance; it does not prove
project membership, authorship, adopted decisions or completion.

Initial sources are approved VS Code visible excerpts and intentional project notes.
The existing project window gains Overview / Memory tabs, retained-source inspection,
coverage states and a preview of the same scoped context delivered through read-only
MCP. Local inference is retained; hosted agents require separate disclosure authorization.
Browser ingestion, arbitrary project discovery and a visual graph are deferred.

The written spec contains proposed runtime, identity, UI, retrieval, lifecycle and
acceptance contracts. No vector/MCP implementation is claimed by this direction note.
