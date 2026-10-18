#!/bin/bash
# Put the known-good generator app (the result of Prompt A, checked 18 Oct 2026) into live-coding-start/.
# Use it if a live build ever comes out different or broken. The running Streamlit app reloads by itself.
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$PKG/reference-apps/app_after_prompt_a.py"
DST="$PKG/live-coding-start/app.py"
[ -f "$DST" ] && cp "$DST" "$DST.live-build.bak" && echo "Kept the live build as app.py.live-build.bak"
cp "$SRC" "$DST"
(cd "$PKG/live-coding-start" && .venv/bin/python smoke_test.py | head -1)
echo "Start (if not running): cd live-coding-start && .venv/bin/python -m streamlit run app.py"
