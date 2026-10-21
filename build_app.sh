#!/usr/bin/env bash
# Build LMemM.app into dist/. Alias mode: the app runs this repo's code and keeps data/ here,
# so `git pull` updates it. Usage: ./build_app.sh [--standalone]
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" -m pip install -q py2app
if [ "${1:-}" = "--standalone" ]; then
  PYTHONPATH=src "$PY" -c 'import dictation; assert dictation.ensure_listener(), "Build the voice helper before packaging"'
fi
rm -rf build dist
if [ "${1:-}" = "--standalone" ]; then
  "$PY" setup.py py2app
else
  "$PY" setup.py py2app -A
fi
codesign -s "${LMEMM_SIGN_IDENTITY:--}" --force --deep dist/LMemM.app
codesign --verify --deep --strict dist/LMemM.app
if [ "${1:-}" = "--standalone" ]; then
  test -f dist/LMemM.app/Contents/Resources/standalone.json
  dist/LMemM.app/Contents/MacOS/LMemM --lmemm-worker diagnostics
fi
echo "built dist/LMemM.app — ad hoc signing is for local testing; distribution needs Developer ID and notarization"
