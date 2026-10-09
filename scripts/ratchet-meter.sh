#!/bin/sh
# Claude Code PostToolUse hook: a live meter. Runs after every Edit/Write and
# stays silent while there is headroom; the moment a bucket's remaining
# headroom goes negative it prints one short warning with the overage, so
# the agent learns mid-edit instead of only at Stop. Mirrors
# ratchet-check.sh's ratchet-or-uvx fallback.
#
# Exit codes (see `ratchet budget --hook`): 0 = silent, within budget; 2 =
# over budget -- the edit already happened, so Claude just sees the warning.
# A missing `ratchet` and no `uvx` exits 0: this is a nice-to-have, the Stop
# hook is still the real gate.

if command -v ratchet >/dev/null 2>&1; then
  exec ratchet budget --hook
fi

if command -v uvx >/dev/null 2>&1; then
  if uvx --from ratchet-size==0.2.0 ratchet budget --hook; then
    exit 0
  fi
  exec uvx --from "git+https://github.com/krishansubudhi/ratchet@2da1918bdba6716208d75107a339495c9adf02ff" ratchet budget --hook
fi

exit 0
