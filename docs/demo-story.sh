#!/usr/bin/env bash
# The narrated part of docs/demo.gif.
#
# Run by docs/demo.sh inside an asciinema recording. Expects:
#   CLICK_DIR  - a clone of pallets/click, with docs/agent_change.patch
#                copied in as agent_change.patch
#   PATH       - already has a ratchet install on it
#
# The "agent bloats the code" step is a scripted patch, not a live agent
# run -- see the caption in README.md and docs/examples.md for why.
set -euo pipefail
cd "$CLICK_DIR"

say() { printf '\033[1;36m$\033[0m %s\n' "$1"; sleep 0.5; }
note() { printf '\n\033[2m%s\033[0m\n' "$1"; }
pause() { sleep "$1"; }

clear
printf '\033[1mratchet on pallets/click (github.com/pallets/click)\033[0m\n\n'
pause 3

say "ratchet init"
ratchet init
pause 4

note "# feature request: print an option-like list outside the help"
note "# formatter. an agent takes it, and instead of reusing"
note "# HelpFormatter.write_dl it pastes a new implementation (twice)."
pause 3

say "git apply agent_change.patch   # simulated agent edit, see README"
git apply agent_change.patch
pause 2

say "ratchet check"
set +e
ratchet check
set -e
pause 8

note "# fix: delete the duplicate, call write_dl like everything else does"
pause 2

say "git checkout -- src/click/formatting.py"
git checkout -- src/click/formatting.py
pause 2

say "ratchet check"
ratchet check
pause 6
