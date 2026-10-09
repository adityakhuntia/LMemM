#!/usr/bin/env bash
# Run the test suite: ./scripts/test.sh [unittest args]
set -eu
cd "$(dirname "$0")/.."
PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" exec "${PYTHON:-python3}" -m unittest discover -s tests "$@"
