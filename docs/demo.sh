#!/usr/bin/env bash
# Regenerates docs/demo.gif: a ~30s terminal recording of ratchet running
# against a real open-source repo (pallets/click).
#
# Requires, on PATH, outside this repo's dependencies (neither becomes a
# ratchet dependency):
#   - asciinema   (pip install --user asciinema)
#   - agg         (https://github.com/asciinema/agg/releases)
#
# Usage: docs/demo.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "cloning pallets/click into $WORK ..."
git clone --quiet --depth 1 https://github.com/pallets/click "$WORK/click"
cp "$REPO_ROOT/docs/agent_change.patch" "$WORK/click/agent_change.patch"

echo "installing ratchet from this checkout into a scratch venv ..."
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet -e "$REPO_ROOT"

export CLICK_DIR="$WORK/click"
export PATH="$WORK/venv/bin:$PATH"
export TERM=xterm-256color

echo "recording ..."
asciinema rec --quiet --command "bash '$REPO_ROOT/docs/demo-story.sh'" -y "$WORK/demo.cast"

echo "rendering gif ..."
agg --font-size 22 --cols 80 --rows 24 --theme asciinema --idle-time-limit 8 \
    "$WORK/demo.cast" "$REPO_ROOT/docs/demo.gif"

ls -la "$REPO_ROOT/docs/demo.gif"
echo "done: docs/demo.gif"
