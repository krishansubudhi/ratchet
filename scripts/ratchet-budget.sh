#!/bin/sh
# Claude Code SessionStart hook: print the current size budget so the agent
# knows the ceiling before it writes a line, instead of discovering it only
# at the end via a Stop-hook refusal. Mirrors ratchet-check.sh's
# ratchet-or-uvx fallback. A SessionStart hook's stdout is added to the
# agent's context automatically.
#
# Never blocks: a missing `ratchet`, no `uvx`, or no .ratchet.json here just
# means no budget line gets injected.

if command -v ratchet >/dev/null 2>&1; then
  ratchet budget 2>/dev/null
  exit 0
fi

if command -v uvx >/dev/null 2>&1; then
  uvx --from ratchet-size==0.1.0 ratchet budget 2>/dev/null && exit 0
  uvx --from "git+https://github.com/krishansubudhi/ratchet@2da1918bdba6716208d75107a339495c9adf02ff" ratchet budget 2>/dev/null
fi

exit 0
