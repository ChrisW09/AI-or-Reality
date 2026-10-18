#!/bin/bash
# Put a known-good app (checked 18 Oct 2026) into live-coding-start/:
#   a = result of Prompt A (generator)      b = result of Prompt B (generator + Detect & compare)
# Use it if a live build ever comes out different or broken. The running Streamlit app reloads by itself
# and keeps its rows.
set -euo pipefail
STAGE="${1:-}"
case "$STAGE" in
  a|A) SRC_NAME=app_after_prompt_a.py ;;
  b|B) SRC_NAME=app_after_prompt_b.py ;;
  *) echo "usage: $0 a|b   (a = after Prompt A, b = after Prompt B)" >&2; exit 2 ;;
esac
PKG="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$PKG/reference-apps/$SRC_NAME"
DST="$PKG/live-coding-start/app.py"
if [ -f "$DST" ]; then cp "$DST" "$DST.live-build.bak"; echo "Kept the live build as app.py.live-build.bak"; fi
cp "$SRC" "$DST"
(cd "$PKG/live-coding-start" && .venv/bin/python smoke_test.py | head -1)
echo "Start (if not running): cd live-coding-start && .venv/bin/python -m streamlit run app.py"
