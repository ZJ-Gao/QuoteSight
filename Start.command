#!/usr/bin/env bash
# macOS: double-click to update the index and open the board. Close this window to stop.
cd "$(dirname "$0")"
.venv/bin/quotesight update
.venv/bin/quotesight-app
