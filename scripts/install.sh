#!/usr/bin/env bash
# macOS / Linux: install QuoteSight into .venv, then ask the setup questions.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is needed"'
echo "Installing (a few minutes, about 2 GB)..."
"$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e .
chmod +x Start.command
.venv/bin/quotesight setup
echo
echo "Done. Double-click Start.command in this folder to build the index and open the board."
