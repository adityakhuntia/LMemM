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

import lmemm  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("start")
    lmemm.main()
