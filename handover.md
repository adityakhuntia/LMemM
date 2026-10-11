# LMemM — continuation handover

Updated 2026-10-10. Read [current context](docs/current-context.md), [runbook](docs/hybrid-memory-runbook.md), and [acceptance](docs/benchmarks/project-memory/hybrid-mvp/acceptance.md).

Work in the root checkout on **main**, per the user's explicit request. The latest fetched origin/main (`42d7f0e`) is included. No push performed. Preserve untracked user `context.md` and its integration safety stash. The feature worktree is a retained checkpoint with ignored model assets and an untracked .env canary; never read/stage that canary or force-clean the worktree.

The hybrid MVP backend, private supervised service, durable native-note sync, native Overview/Memory UI and official SDK MCP adapter are implemented. Pre-review: 790 Python tests and 6 Node tests pass. Synthetic native screenshots, held-out retrieval (20/20 Recall@5), fresh assertion precision (8/8 supported), 10k full-search probe (0.251s p95), and an actual synthetic-only hosted Codex resume are recorded.

Next: fresh independent whole-implementation review, one TDD fix pass for material findings, then final checks/commits on main. Physical crash/sleep/lock, paired 30-minute resources, real extension setup and three external testers remain pending; do not claim launch acceptance.

Start from the root with `.venv/bin/python lmemm.py start`, only when no other tracker is running. Follow the runbook to enable a project explicitly; no personal sources were enrolled by implementation tests.
