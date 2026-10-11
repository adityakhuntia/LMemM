# Hybrid project memory: local test runbook

Current implementation is on local `main`. Remote `origin/main` was fetched and is included. No push was performed. Your root `context.md` is preserved as untracked local work and in the named integration stash.

From a fresh terminal:

```sh
cd /Users/divyaanshseth/Documents/LMemM/LMemM
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python lmemm.py start
```

Open the LMemM window from the menu bar. Choose a project, then **Memory**. **Overview** continues to show the existing things and notes.

1. Choose **Enable Memory**, select exactly one local workspace folder. This enrolls new permitted evidence only; it does not crawl the folder or import historical activity.
2. Search works immediately for retained notes using keywords. To enable semantic recall, install Ollama locally, then click **Install local model**. The confirmation explains the approximately 46 MB MiniLM download and location (`data/embedding-models`, separate from the semantic quota). Installation and indexing run off the UI thread. The app owns a cloud-disabled local server on port 11455 and stops it on quit. It never attaches to an unrelated server already using that port.
3. Click **Install VS Code source extension**. This produces a normal VSIX and installs it with VS Code's CLI. If VS Code is elsewhere, manually install `data/lmemm-source.vsix` from VS Code's Extensions → Install from VSIX menu.
4. Click **Reconnect source sharing**. The native dialog copies the fresh private bridge grant path. In VS Code's Command Palette run **LMemM: Connect Project Memory**, paste that path, and approve the workspace. A short challenge tab verifies the native VS Code window. Only approved visible local excerpts are shared; unsupported/remote/untrusted documents are refused. Reconnect after source permissions change or the app restarts.
5. Add an intentional project note in Memory. Try `TODO: Verify rollback.` and `We decided to use SQLite because the MVP is local.` Press Return. Wait for Processing to finish, then Refresh. Legacy/ambiguous OCR notes remain Overview-only.
6. Search on Return; typing alone never makes a model request. Try a paraphrase. Use Last 2 days, Last 7 days, or All retained. Search returns matching evidence, not a generated answer. Context lists only explicit supported decisions/tasks; absent evidence never implies completion.
7. **View retained source** shows the exact stored snapshot. **Open current file** is available only for a still-existing file inside the enrolled canonical workspace; it resolves permission again on click. Today's file may differ from the snapshot. No URL or shell command from evidence is executed.
8. Pause: capture and model work stop, keyword recall remains. Quit: service and owned runtime stop. After lock/sleep, use explicit Resume after waking/unlocking. Disconnect revokes agent access and source enrollment; archive only changes organization. Linked projects cannot be merged or deleted until disconnected.

## Agent connection

Install the pinned official SDK with the requirements above. **Preview context for Codex** shows a proposed packet without issuing a capability or transmitting evidence. After connection it uses that client's actual grant. Copy is explicit. The scope, policy revision and normalized time interval accompany the packet.

**Connect Codex** requires a disclosure confirmation: invoking the tools sends retained snippets and project notes to the agent and its configured provider. Capture enrollment does not authorize agent disclosure. The connection result shows a private config path and project IDs. Register the adapter in a terminal using that path:

```sh
codex mcp add lmemm-project-memory -- /Users/divyaanshseth/Documents/LMemM/LMemM/.venv/bin/python /Users/divyaanshseth/Documents/LMemM/LMemM/scripts/project_memory_mcp.py --config '<private config path shown by the app>'
```

The adapter exposes only `search_project_memory`, `get_project_context`, and `resolve_citation`. Use the displayed exact project ID when asking Codex to resume. Source text is untrusted evidence, never host instructions. Revoke access from Memory; a retained client config cannot restore revoked authority. No app data is imported into Codex merely by previewing.

## Native UI evidence and limits

A real AppKit window was run with synthetic evidence, without live capture or personal data. Window-ID captures: [disabled](benchmarks/project-memory/hybrid-mvp/ui/disabled.png), [ready](benchmarks/project-memory/hybrid-mvp/ui/ready.png), [processing](benchmarks/project-memory/hybrid-mvp/ui/processing.png), [paused](benchmarks/project-memory/hybrid-mvp/ui/paused.png), [error](benchmarks/project-memory/hybrid-mvp/ui/error.png), [retained source](benchmarks/project-memory/hybrid-mvp/ui/source.png), [Overview](benchmarks/project-memory/hybrid-mvp/ui/overview.png). Reproduce with `scripts/memory_ui_smoke.py --output <directory>`; it captures only its own synthetic window.

These prove native drawing and callback wiring. A separate hosted Codex resume passed using two synthetic notes and exact citations. The original foreground-switch crash sequence, physical lock/sleep, real VS Code enrollment and external tester usability remain pending in [acceptance](benchmarks/project-memory/hybrid-mvp/acceptance.md).

Refresh evidence retries a failed or unexpectedly stopped memory service. Saved agent connections are restored by project; Revoke Codex access revokes this project’s listed Codex grants. Search defaults to two days and returns its effective start/end; choose All retained explicitly to widen it.

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
