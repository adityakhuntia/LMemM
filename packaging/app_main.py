"""Entry point of LMemM.app: the same as `python3 lmemm.py start`, with no terminal menu."""
import locale
import os
import sys

# An app starts with the "C" locale, so open() would read memory.json as ASCII (and the launcher
# ignores PYTHONUTF8). Switching the character locale makes the default encoding UTF-8 again.
for _loc in ("en_US.UTF-8", "UTF-8", "C.UTF-8"):
    try:
        locale.setlocale(locale.LC_CTYPE, _loc)
        break
    except locale.Error:
        continue

HERE = os.path.dirname(os.path.abspath(__file__))
# alias build: the app points back at this repo (…/LMemM/packaging); a standalone build keeps lmemm.py beside it
for root in (os.path.dirname(HERE), HERE):
    if os.path.exists(os.path.join(root, "lmemm.py")):
        sys.path.insert(0, root)
        os.chdir(root)
        break

# py2app's bootstrap puts the base interpreter's site-packages first; an older PyObjC there
# (e.g. Anaconda's) shadows the one in .venv and fails with "no attribute registerNewKeywordsFromSelector"
import glob  # noqa: E402

for site in glob.glob(os.path.join(os.getcwd(), ".venv", "lib", "python*", "site-packages")):
    sys.path.insert(0, site)

import lmemm  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("start")
    lmemm.main()
