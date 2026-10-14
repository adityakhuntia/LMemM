"""Entry point of LMemM.app: the same as `python3 lmemm.py start`, with no terminal menu."""
import os
import sys

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
