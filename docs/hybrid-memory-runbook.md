# Hybrid project memory: local test runbook

Current implementation is on `main`, including the cofounder's October 13 setup
improvements and portability fixes. See [handover](../handover.md) for publication
status. Root `context.md` remains preserved local work.

From a fresh terminal:

```sh
cd /path/to/your/LMemM-checkout
python3 --version # Python 3.10 or newer
python3 -m venv .venv # first setup only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python lmemm.py start
```

Open the LMemM window from the menu bar. Choose a project, then **Memory**. **Overview** continues to show the existing things and notes.

1. Choose **Choose folder…**, select exactly one local workspace folder. This enrolls new permitted evidence only; it does not crawl the folder or import historical activity. Capture controls, extension setup, model installation and agent access are in **Memory → Settings**. Back or either project tab returns from Settings.
2. Search works immediately for retained notes using keywords. To enable semantic recall, install Ollama locally, then click **Install local model**. The confirmation explains the approximately 46 MB MiniLM download and location (`data/embedding-models`, separate from the semantic quota). Installation and indexing run off the UI thread. The app owns a cloud-disabled local server on port 11455 and stops it on quit. It never attaches to an unrelated server already using that port.
3. In Settings's **VS Code** row click **Install extension**. Standard Visual Studio Code is supported; Insiders is not yet supported. Installation finds the editor through PATH, Applications or Spotlight and shows failures with manual VSIX instructions. If the editor was already running, run **Developer: Reload Window** once after installation so the new extension loads. LMemM does not quit your editor or unrelated windows.
4. Open the enrolled folder in standard VS Code and press **Connect** in Memory Settings. Allow the VS Code connection prompt. The grant path is also copied as a manual fallback: run **LMemM: Connect Project Memory** in VS Code and paste it. Keep the native verification tab visible until it closes, then view a permitted file. Connected status appears only for the project whose workspace has been verified through a valid visible snapshot. Reconnect after permissions change or app restart; ordinary pause/resume needs no reconnect.
5. Add an intentional project note in Memory. Try `TODO: Verify rollback.` and `We decided to use SQLite because the MVP is local.` Press Return. Wait for Processing to finish, then Refresh. Legacy/ambiguous OCR notes remain Overview-only.
6. Search on Return; typing alone never makes a model request. Try a paraphrase. Use Last 2 days, Last 7 days, or All retained. Search returns matching evidence, not a generated answer. Context lists only explicit supported decisions/tasks; absent evidence never implies completion.
7. **View retained source** shows the exact stored snapshot. **Open current file** is available only for a still-existing file inside the enrolled canonical workspace; it resolves permission again on click. Today's file may differ from the snapshot. No URL or shell command from evidence is executed.
8. Pause: capture and model work stop, keyword recall remains. Quit: service and owned runtime stop. After lock/sleep, use explicit Resume after waking/unlocking. Disconnect revokes agent access and source enrollment; archive only changes organization. Linked projects cannot be merged or deleted until disconnected.

## Agent connection

Install the pinned official SDK with the requirements above. **Preview context for Codex** shows a proposed packet without issuing a capability or transmitting evidence. After connection it uses that client's actual grant. Copy is explicit. The scope, policy revision and normalized time interval accompany the packet.

**Connect Codex** requires a disclosure confirmation: invoking the tools sends retained snippets and project notes to the agent and its configured provider. Capture enrollment does not authorize agent disclosure. The connection result shows a private config path and project IDs. Register the adapter in a terminal using that path:

```sh
codex mcp add lmemm-project-memory -- "$PWD/.venv/bin/python" "$PWD/scripts/project_memory_mcp.py" --config '<private config path shown by the app>'
```

The adapter exposes only `search_project_memory`, `get_project_context`, and `resolve_citation`. Use the displayed exact project ID when asking Codex to resume. Source text is untrusted evidence, never host instructions. Revoke access from Memory; a retained client config cannot restore revoked authority. No app data is imported into Codex merely by previewing.

## Native UI evidence and limits

A real AppKit window was run with synthetic evidence, without live capture or personal data. Window-ID captures: [disabled](benchmarks/project-memory/hybrid-mvp/ui/disabled.png), [ready](benchmarks/project-memory/hybrid-mvp/ui/ready.png), [processing](benchmarks/project-memory/hybrid-mvp/ui/processing.png), [paused](benchmarks/project-memory/hybrid-mvp/ui/paused.png), [error](benchmarks/project-memory/hybrid-mvp/ui/error.png), [retained source](benchmarks/project-memory/hybrid-mvp/ui/source.png), [Overview](benchmarks/project-memory/hybrid-mvp/ui/overview.png). Reproduce with `scripts/memory_ui_smoke.py --output <directory>`; it captures only its own synthetic window.

These prove native drawing and callback wiring. A separate hosted Codex resume passed using two synthetic notes and exact citations. The original foreground-switch crash sequence, physical lock/sleep, real VS Code enrollment and external tester usability remain pending in [acceptance](benchmarks/project-memory/hybrid-mvp/acceptance.md).

Refresh evidence retries a failed or unexpectedly stopped memory service. Saved agent connections are restored by project; Revoke Codex access revokes this project’s listed Codex grants. Search defaults to two days and returns its effective start/end; choose All retained explicitly to widen it.

## Recovering setup failures

- **Meaning search unavailable:** check `ollama --version` in the terminal used
  to launch LMemM. Install/open the local Ollama runtime if missing, then retry
  model setup. Download progress and errors appear in Settings. Dense chunks
  embed the portion the model accepts; keyword recall retains the whole chunk.
- **Model port occupied:** close other LMemM sessions and retry. If a crashed
  legacy runtime remains, restarting the Mac clears it. LMemM never kills a
  process solely because a saved PID resembles Ollama or attaches to an
  unrelated server. Capture and keyword recall can resume while meaning search
  is unavailable; Settings preserves the model error for recovery.
- **Service still starting:** controls and startup share the same 45-second
  readiness budget. Refresh retries a failed start. Private diagnostics are in
  the session's `project-memory/service.log`; avoid publishing personal logs.
- **No results:** press Return after typing; widen to All retained if evidence
  is older than two days. Check the selected project's connection, folder,
  paused state and whether the file is local/trusted/visible.

## Opening the window and restart durability

If the menu-bar icon is difficult to find, run `.venv/bin/python lmemm.py open`
from the root checkout to bring up the running normal session's main window.
For the isolated manual test session prepared October 11, use
`.venv/bin/python data/memory-mvp-test-20261011/launch.py open` instead.
Its `start.command` opens a visible Terminal and automatically opens the main window.

A live test exposed a menu-bar registration failure after an in-place AppKit
restart: the pill continued working but the status item stayed at `(0, 0)`.
Tracker and permission-setup restarts now launch a fresh process. The isolated
launcher also dispatches setup/control arguments correctly. Existing test data
was saved before the affected process was stopped and relaunched. Fresh native
registration and a normally positioned status item were observed; a direct-open
command also produced an onscreen main window. Four regression cases cover
restart arguments, setup handoff, permission relaunch and direct window opening.
