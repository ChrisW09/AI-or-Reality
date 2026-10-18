#!/bin/bash
# Restore live-coding-start/ from starter-kit/ before class.
# Deletes everything the assistant wrote (app.py, caches, anything new). Keeps .venv/ and .env.
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
KIT="$PKG/starter-kit"
LIVE="$PKG/live-coding-start"
[ -f "$KIT/lab.py" ] || { echo "starter kit not found at $KIT" >&2; exit 1; }
mkdir -p "$LIVE"
echo "Will remove from $LIVE:"
(cd "$LIVE" && find . -mindepth 1 -maxdepth 1 ! -name .venv ! -name .env | while read -r f; do
  [ -e "$KIT/$f" ] || echo "  $f"; done)
rsync -a --delete --exclude '.venv/' --exclude '.env' --exclude '__pycache__/' --exclude '.pytest_cache/' \
      "$KIT"/ "$LIVE"/
find "$LIVE" -name __pycache__ -type d -prune -not -path "$LIVE/.venv/*" -exec rm -rf {} +
rm -rf "$LIVE/.pytest_cache"
echo "Reset done. live-coding-start now holds:"
(cd "$LIVE" && ls -A)
[ -x "$LIVE/.venv/bin/python" ] || echo "NOTE: no .venv yet; create it (see starter-kit/README.md)."
