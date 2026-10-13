# Project Memory portability and lifecycle audit — 2026-10-13

## Scope and evidence

Audited root main `66bcd65` and an isolated archive of cofounder branch
`origin/claude/project-thread-1wwhgq` at `b84f6db`. Fetch confirmed the branch's
setup fixes are not on main. The unrelated resume-project branch was not merged.
User had no specific cofounder logs; his actual four-hour sequence cannot be
reconstructed. This audit combines source tracing, deterministic failure probes
and whole-suite runs on the current Mac. It is not a fresh second-Mac GUI run.

Initial main: 815 tests, one error. Cofounder branch: 834 tests, same error.
After correcting the fixed-date test only, the cofounder snapshot passes all
834 tests and 6 Node tests. Audited main with new regressions/fixes passes
817 Python tests and 6 Node tests. Full logs from this session are in
`/tmp/lmemm-audit-final-suite.log` and
`/tmp/lmemm-cofounder-fixed-fixture-suite.log` (temporary, not repository assets).

## Reproduced and fixed on main

1. **High: failed owned runtime startup left the backend enabled.**
   `MemoryService.__init__` assigned an embedding backend before calling
   `runtime.ensure()`, then recorded the startup error without clearing it.
   A port-conflict/startup failure could report the model available and leave
   embedding attempts enabled without a verified owned runtime. A mocked
   runtime failure reproduced this with a non-null backend. Startup now clears
   the backend; resume must ensure runtime availability before enabling it.
   The new regression checks failure on both startup and resume. This code path
   also exists in the cofounder snapshot; carry this fix into his branch.
2. **Low: failed subprocess spawn leaked a control-pipe descriptor.**
   `OwnedEmbeddingRuntime.ensure()` closed the read end but left the write end
   assigned on Popen failure. Repeated retries could overwrite/leak it.
   Reproduced with a failing Popen and mocked port probe. The exception path now
   closes/reset the write end. The cofounder version needs the equivalent change
   around its different Popen arguments.
3. **Test reliability: calendar-dependent note-sync failure.**
   An October 10 fixture queried the default rolling two-day window. On October
   13 it legitimately returned no result. The regression now requests its
   intended explicit October range. Product time filtering was not changed.
4. **Setup documentation gap.** README omitted Python's minimum version and the
   separate Ollama/editor prerequisites. Installed MCP 2.3.0 metadata declares
   Python >=3.10. README now states this and links the Project Memory runbook.

## Setup faults already addressed by the cofounder, absent from main

- Newer Ollama manifest layout was rejected by main's hard-coded legacy path.
  His branch supports both layouts while preserving the digest check (`e4d217c`).
- VS Code discovery assumed PATH or `/Applications`; his branch adds user
  Applications and Spotlight discovery (`1ee3905`).
- Install failures were swallowed into generic IPC errors, with no useful
  progress. His branch adds visible install feedback and diagnostics.
- Reinstalling the same extension version in an already-running editor did not
  ensure new code loaded. His branch versions the extension and reconnects via
  a URI; its chosen full-editor restart has the separate concern below.
- Main's strict embedding request could fail on token-dense chunks despite
  byte limits. His branch retries with truncation (`b84f6db`), retaining full
  keyword evidence. Retrieval benchmarks should be rerun for this new behavior;
  the previous frozen results describe the previous embedding policy.
- His branch adds model retry handling, longer startup allowance and a service
  log. These are useful changes but do not by themselves prove fresh-Mac setup.

## Remaining issues in the cofounder snapshot

1. **High: orphan cleanup cannot reliably identify ownership.**
   `_reap_orphan` reads a PID, accepts any command containing `ollama` and `serve`,
   and signals the process group. A stale PID reused by an unrelated Ollama
   process satisfies this check. A deterministic mocked probe confirmed
   `killpg` is invoked for a generic `/usr/local/bin/ollama serve` command.
   No real process was signalled. Require stronger instance identity (including
   creation identity) or fail with explicit port-conflict recovery rather than
   automatically killing a process whose ownership is uncertain.
2. **Medium: Insiders is discoverable/installable but not capturable.**
   `_vscode_cli` and `extension_installed` accept VS Code Insiders; native focus
   requires exactly `com.microsoft.VSCode`, and Connect launches `vscode://`.
   An Insiders-only user can pass installation then fail connection/capture.
   Either support its bundle/URI end to end or explicitly restrict installation
   to standard VS Code. This is a source-confirmed mismatch, not a physical
   Insiders acceptance run.
3. **Medium: Connect quits the entire standard VS Code application every time.**
   The controller unconditionally calls quit for a running editor, even if the
   current extension is already loaded. This interrupts unrelated windows and
   can stall on save prompts. Reload only when required and make a necessary
   restart explicit. Existing tests deliberately enforce the current behavior.
4. **Medium: startup deadlines disagree.**
   `_start` allows 45 seconds, but control requests still wait only 10 seconds
   for readiness. Slow startup can produce early failed controls even while the
   service is still starting. Align readiness deadlines and surface starting
   state. Ordinary queued read requests share the startup executor and are less
   exposed than the separate control executor.
5. **Low: connection state is global, not per project/window.**
   Service status sets source_connected if any bridge client is live; the
   controller presents it for the selected binding. Beta can therefore look
   connected when only Alpha's source window has connected. This does not
   demonstrate an evidence leak, but the UI overstates project capture status.

## Limits and required next checks

No claim of a complete absence of faults is justified. Physical first-run
permissions, fresh Python/VS Code/Ollama installation, modal folder selection,
original crash sequence, Intel vs Apple Silicon, and sustained paired resource
measurements have not been independently replayed in this audit. Earlier local
user smoke tests remain valid for that configured machine, not portability.

Recommended integration order: carry the small main audit fixes into the
cofounder branch; resolve remaining ownership/editor/startup issues there;
then integrate that reviewed branch. Do not cherry-pick UI/controller changes
blindly: the extension URI, version, installer and view are coupled.

Finally test a genuinely clean user account/Mac using only tracked instructions,
without copied weights, installed extensions or the ignored demonstration data.
Verify install failure/retry, keyword-only mode, model download, source connect,
capture, pause/resume, isolation, note edits/deletion, citations, sleep/lock,
restart and approved agent access. A green mock-heavy suite cannot replace this.
