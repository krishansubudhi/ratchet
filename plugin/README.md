# Ratchet plugin for Claude Code

Ratchet gives a repo a line budget that only goes down. `ratchet init`
records today's code size as the ceiling in `.ratchet.json`. When an agent's
change pushes code past it, the turn is refused in plain words: the agent
trims what it wrote, or stops and asks you, since only a human can raise the
budget with `ratchet grant`. Only code files count, split into `source` and
`tests`; docs never do.

Install:

```text
/plugin install ratchet --marketplace krishansubudhi/ratchet
```

Then run `/ratchet:setup` in a repo to install the CLI and record the
baseline. Full docs: https://github.com/krishansubudhi/ratchet

## What it runs

Three hooks, each a short shell script in `scripts/`:

- **SessionStart** (`ratchet-budget.sh`) prints the current budget into
  context.
- **PostToolUse** on Edit, Write and MultiEdit (`ratchet-meter.sh`) warns once
  a bucket goes over.
- **Stop** (`ratchet-check.sh`) runs `ratchet check --hook` and blocks the
  turn while the repo is over budget.

Each script runs the `ratchet` CLI if it is on `PATH`. If not, it runs it
with `uvx`, pinned to `ratchet-size==0.2.3` from PyPI, falling back to a
pinned commit of this GitHub repo. That download is the only network access.
Ratchet counts lines in the local repo and reads and writes only
`.ratchet.json`, `.ratchet-grants.jsonl` and `.ratchet/` there. It collects no
personal data and sends nothing anywhere.

`/ratchet:setup` asks Claude to fetch and follow `SETUP-FOR-AGENTS.md` from
this repo: install the CLI, run `ratchet init`, and ask you before adding a
git pre-commit hook.

Apache-2.0.
