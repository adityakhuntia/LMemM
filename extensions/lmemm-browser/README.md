# LMemM browser connector — Launch 1 pilot

1. Run LMemM, create a project, enable Memory. No folder is necessary.
2. In project Memory → Settings, press **Connect Chrome**.
3. Open `chrome://extensions`, enable Developer mode, choose Load unpacked and
   select this directory. Pin LMemM in the toolbar. The pilot extension ID is
   `ieicfnnnmgighnijggfffeeclagbkfkn` (the manifest contains only a public key).
4. On an ordinary web page, click LMemM and choose a project once. Save the page
   from that first-use window, or return to the page and use the extension again.
5. Subsequently click the extension to save selected text or visible page text.
   For a selection, right-click → Save selection to LMemM or use Control+Shift+S.
   Adjust conflicts at `chrome://extensions/shortcuts`.
6. The confirmation names the project and offers Undo/Change project. If the page
   cannot show a confirmation, right-click the extension → Undo/change project.

Only explicit gestures capture text. No background history or offline text queue.
Incognito, restricted browser pages and form fields are excluded. Text-only
capture does not promise PDFs, images or inaccessible embedded frames. Page
text is bounded to 128 KiB; inspect historical text through Memory → View source.
Opening its URL separately displays the current site, not the saved snapshot.

Disconnect in LMemM Settings stops saves but keeps retained sources. Deleting a
source removes its derived search/graph evidence. The connector cannot retrieve
project memory or run owner commands. Private host credentials stay on disk in
the OS account, not in page scripts. Native messaging/extension IDs do not defend
against other software already able to read that account's private files.

Protocol follows [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
and [activeTab access](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab).
Chrome/Chromium pilot installation only; Safari and store publication are not included.

CLI alternative while LMemM runs: `.venv/bin/python scripts/install_browser_host.py`.
Use `--browser Chromium` or `--browser ChromeForTesting` for those browsers.
