# Live project-memory pilot

This is an explicitly experimental loop across approved local VS Code projects:

```
visible editor ranges → private per-window bridge → native focus + root checks
  → SQLite source evidence → bounded episodes → optional local model
  → project context with original quotes, recorded tasks and tentative interpretations
```

The ordinary screenshot/input tracker is independent. Start this pilot separately.
No screenshots, full-file reads, background editors, typed keys, browser pages,
terminal/chat buffers or hosted inference feed this pilot. Unsaved changes in an
existing local file can be shared; untitled/remote/untrusted files cannot.

## Start and connect

Run from `.worktrees/semantic-project-memory`. Use the repository's existing venv:

```bash
PY=../../.venv/bin/python
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" start \
  --workspace "$PWD" --workspace /absolute/path/to/another/project
```

Approve only roots you intend to share. Do not use your entire home directory.
The CLI prints the absolute path to `bridge/grant.json`. That file contains a
run-scoped private token. Do not commit or share it.

Load the extension in VS Code using **Run → Start Debugging** from an extension
workspace, or launch a development host using the `code` CLI:

```bash
code --new-window --extensionDevelopmentPath="$PWD/extensions/lmemm-source" "$PWD"
```

Connect briefly opens a random challenge tab so Python can verify the exact native window. It closes after acknowledgement; if it stays open, native identity is not yet verified.

In that development window's command palette run **LMemM: Connect Experimental
Project Memory**, and paste the printed grant path. Connect separately in each
approved project window. At most eight clients can register; one verified focused
window supplies source text at a time. **LMemM: Disconnect Source Sharing** stops
that window. Re-run Connect to resume after the extension's own Pause command.

Accessibility permission is required for the terminal launching Python. Electron
accessibility must expose focused elements/windows; if unavailable, intake stays
closed. The status bar distinguishes native-focus waiting, excluded content and
source sharing. A sharing label indicates publication; the Python source count
confirms acceptance. Live native acceptance is still pending.

## Optional experimental model

Evidence-only mode works without a model. For tentative model interpretations,
explicitly start your cloud-disabled local service in another terminal:

```bash
OLLAMA_HOST=127.0.0.1:11455 OLLAMA_MODELS="$PWD/data/model-cache" \
  OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  /usr/local/bin/ollama serve
```

Then add both flags to the pilot start command:

```bash
--runtime-config "$PWD/data/runtime-1.5b.json" --experimental-model
```

The runtime config and weights must already exist locally. The pilot does not
start/download them, use cloud aliases or fall back to hosting. The latest tested
1.5B candidate achieved 83.3% assertion precision, below the 95% acceptance gate.
Live experimentation is allowed; default agent/MCP consumption remains disabled.
See [reviewed benchmarks](benchmarks/project-memory/README.md).

## Inspect and control

In another terminal, from the same worktree:

```bash
PY=../../.venv/bin/python
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" status
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" flush
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" context --project "$PWD" --days 2
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" pause
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" resume
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" stop
```

Ctrl-C also stops. Context requires retained evidence for that exact workspace root.
Use `--json` for structured inspection. Source snapshots show observed content;
they do not prove authorship, changes completed or decisions made. Intentional
notes through **LMemM: Record Intentional Project Note** are user-authored sources.
Noncanonical/symlink document aliases are denied; open canonical paths. No manual project linking is required: canonical roots anchor project identity.

Pause cancels queued/in-flight results and advances the policy revision. If a
cancelled runtime request is still finishing, Resume asks you to retry once it
finishes (up to the request timeout). Lock/sleep/display-off pause the process;
resume explicitly after returning.

After stop, identify the session from `status` and preview/delete its evidence:

```bash
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" delete-session --session SESSION
$PY scripts/live_project_memory.py --data-dir "$PWD/data/live-pilot" delete-session --session SESSION --confirm
```

Deletion removes dependent source quotes/claims. It does not delete ordinary
tracker data. Pilot evidence is retained for 30 days. The total 250MiB budget
reserves SQLite journal/reclaim and bridge space, leaving roughly a third for the
main database. Cached weights are separate. Physical SQLite page limits apply to
all writes, with one inference worker, eight queued episodes and 128KiB queued text.

## Live validation checklist

Use harmless sample files in two approved project roots for 5–10 minutes:

1. Connect both project windows. Type/scroll in each; Ctrl+Tab between files,
   Cmd+Tab to another app, and click between project windows.
2. Confirm source counts rise for changed approved visible content. Leave a
   document unchanged: heartbeats must not add sources indefinitely.
3. Open a harmless `.env` canary and an unapproved project: their contents must
   not appear in project context. Do not use real secrets for this check.
4. Flush, wait for queued/running jobs to finish in status if using a model, then inspect each project's context. Quotes and file identity must
   match the project; tentative interpretations should be assessed against them.
5. Pause, edit, inspect unchanged counts; resume and check fresh intake. Test
   lock/unlock and explicit resume.
6. Stop/restart/connect again. The same project/file retains its structural ID.
   Preview and delete the earlier session; its quotes must disappear.

Unit tests cover protocol, lifecycle and recall. Actual VS Code/native end-to-end
acceptance, long-session RAM/power and the usefulness of live model output remain
pending. Confirm this run before handover/push. Future work: improve automatic
semantic recall from live failure examples, then add browser adapters and scoped
MCP access once accuracy/privacy/resource gates are met.
