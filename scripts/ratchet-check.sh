#!/bin/sh
# Claude Code Stop hook: run ratchet's budget check before the agent
# finishes its turn. Mirrors integrations/claude-code/README.md, but works
# even when `ratchet` isn't already on PATH, by running it on the fly with
# uvx -- from the ratchet-size package on PyPI, or from source if that
# package isn't resolvable yet.
#
# Exit codes (see `ratchet check --hook`): 0 = under budget or a repeated
# refusal Claude Code should let through; 2 = over budget, block the turn.
# A missing `ratchet` and no `uvx` exits 0 so a broken setup never blocks
# the agent -- see SETUP-FOR-AGENTS.md to install ratchet properly.

if command -v ratchet >/dev/null 2>&1; then
  exec ratchet check --hook
fi

if command -v uvx >/dev/null 2>&1; then
  if uvx --from ratchet-size==0.2.1 ratchet check --hook; then
    exit 0
  fi
  exec uvx --from "git+https://github.com/krishansubudhi/ratchet@2da1918bdba6716208d75107a339495c9adf02ff" ratchet check --hook
fi

echo "ratchet: not found on PATH and uvx is unavailable; run 'pipx install ratchet-size' (or see SETUP-FOR-AGENTS.md) to enable the size-budget check" >&2
exit 0
