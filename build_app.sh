#!/usr/bin/env bash
# Build LMemM.app into dist/. Alias mode: the app runs this repo's code and keeps data/ here,
# so `git pull` updates it. Usage: ./build_app.sh [--standalone]
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" -m pip install -q py2app
rm -rf build dist
if [ "${1:-}" = "--standalone" ]; then
  "$PY" setup.py py2app
else
  "$PY" setup.py py2app -A
fi
codesign -s - --force --deep dist/LMemM.app 2>/dev/null || true
echo "built dist/LMemM.app — open it, then grant Screen Recording etc. to LMemM in System Settings"
