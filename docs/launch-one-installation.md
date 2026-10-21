# Launch 1 installation and recovery

This is a macOS early-access build. Standalone runtime qualification is separate
from Developer ID signing/notarization and second-Mac acceptance. See
`launch-one-acceptance.md` for the actual checks performed and remaining gates.

## Build and install

Developer machine: create `.venv`, install `requirements.txt`, then run
`./build_app.sh --standalone`. Xcode Command Line Tools compile the voice helper
at build time. The app bundles Python and its dependencies; recipients do not
need the repository or a Python environment. An alias build (`./build_app.sh`)
still depends on its checkout and must not be sent as the standalone release.

Copy `dist/LMemM.app` to Applications and open it. Grant the requested macOS
permissions to LMemM. Native notes, pasted excerpts and keyword recall do not
require Codex or a local embedding model. Meaning search is optional: install
Ollama, then use Memory Settings → Install meaning search. The selected MiniLM
weights download explicitly into LMemM's own data directory. Hosted AI access is
an independent optional disclosure and sign-in.

Installed data: `~/Library/Application Support/LMemM/data`. Alias/developer data
remain in the checkout's `data/`. No old data is silently imported or overwritten.

## Browser

1. Create a project, open Resume or Memory and enable Memory without a folder.
2. Memory → Settings → Connect Chrome. This installs the native host for the
   current OS account and pairs an ingestion-only credential.
3. Press Show extension folder. At `chrome://extensions`, enable Developer mode,
   click Load unpacked and choose that folder. Pin the LMemM extension.
4. On a normal web page, click LMemM, choose your project once and save.
5. Later highlight text and use Control+Shift+S or right-click → Save selection
   to LMemM. Clicking the icon saves the selection or visible page text.
6. Check Saved to [project]. Undo removes that save; Change project moves it.
   Right-click the extension → Undo/change project also opens the controls.

No automatic history, private tabs or hidden offline queue. Text capture excludes
form controls and does not promise PDFs/images/embedded frames. Browser saves
remain local until an explicitly authorized AI integration reads them. Disconnect
blocks new ingestion while keeping saved evidence; delete a source to remove its
search/graph evidence. Browser shortcuts can be changed at
`chrome://extensions/shortcuts`. Keep the installed app in its final location;
after moving it, Connect Chrome again to update its host launcher.

The pilot extension is unpacked, not a Chrome Web Store publication. Chrome for
Testing/Chromium need their corresponding host installation; the developer CLI
offers `scripts/install_browser_host.py --browser ChromeForTesting` or Chromium.
Custom browser profiles need a host manifest in their own NativeMessagingHosts
directory; ordinary default-profile Chrome setup is the supported UI path.

## Existing beta data

Stop the old app and keep a backup of its entire `data/` directory. Import is an
explicit offline operation and refuses an existing destination. Before opening a
fresh installed app, run its bundled importer, replacing OLD_DATA with the old
checkout's data directory:

```sh
"/Applications/LMemM.app/Contents/MacOS/LMemM" --lmemm-worker import-data OLD_DATA "$HOME/Library/Application Support/LMemM/data"
```

If the destination already exists, keep it and choose a separate fresh destination
for a trial import; do not delete current memory to force an import. The importer
makes a private sibling `legacy-backup-*` copy, preserves the original and only
publishes a completed copy atomically. Reconnect browser/editor/AI integrations;
running sockets and old source-sharing credentials are not reused. Database
upgrades make private `.pre-vN` recovery copies beside the database. Recovery
backups retain historical data; keep them private and remove them only when you
no longer need recovery. Do not restore a backup while a service is running.

## Signing and release

The build verifies its signature and bundled diagnostics. Default signing is
ad hoc for local testing. A distributable release requires an available Developer
ID identity (`LMEMM_SIGN_IDENTITY`), appropriate hardened-runtime entitlements,
notarization and stapling, then Gatekeeper verification on another Mac. A local
ad hoc signature does not establish those release properties.
