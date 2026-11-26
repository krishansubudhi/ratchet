# ratchet

[![CI](https://github.com/krishansubudhi/ratchet/actions/workflows/ci.yml/badge.svg)](https://github.com/krishansubudhi/ratchet/actions/workflows/ci.yml) [![code size](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/krishansubudhi/ratchet/main/.ratchet/badge.json)](https://github.com/krishansubudhi/ratchet)

**A code-size budget for your repo that only goes down.**

![ratchet refusing a duplicated-code change on pallets/click, then passing once the duplicate is removed](docs/demo.gif)

A real run on [pallets/click](https://github.com/pallets/click); the bloated
change is a scripted patch standing in for an agent. Full commands and output:
[docs/examples.md](docs/examples.md).

**Try it in 30 seconds** (nothing is enforced until you wire up a hook or CI):

```sh
pip install ratchet-size
ratchet init      # records today's size as the ceiling
ratchet check     # passes now; refuses once code grows past it
```

## Why

Coding agents are good at adding code and bad at deciding not to. Ratchet
gives the repo a line budget that can only shrink. When a change would go over
it, the agent is refused in plain words: it trims the code, or stops and asks
you, since only a human can raise the budget.

## Quickstart

Remove it any time: [uninstall](docs/uninstall.md).

1. **Install:** `pip install ratchet-size` (or `pipx install ratchet-size`)
2. **Baseline:** run `ratchet init` anywhere in the repo, and commit the
   `.ratchet.json` it writes.
3. **Wire up your agent:** tell it: *"Set up ratchet in /path/to/repo
   by following
   https://raw.githubusercontent.com/krishansubudhi/ratchet/main/SETUP-FOR-AGENTS.md"*
   Or install the agent plugin, which adds the hooks and `/ratchet:setup`.
   In Claude Code, run these two commands:
   `/plugin marketplace add krishansubudhi/ratchet`, then
   `/plugin install ratchet@ratchet`.
   In Gemini CLI:
   `gemini extensions install https://github.com/krishansubudhi/ratchet`.

![Gemini CLI implements a feature, is refused by ratchet check, asks for a grant and will not commit when told to; after the human runs ratchet grant it commits and the check passes](docs/gemini-demo.gif)

*A real Gemini CLI run after step 3, sped up: refused, it asks for a grant
instead of cutting code, declines "commit it", and commits once granted
([cast](docs/gemini-demo.cast)).*

Only code files count, split into `source` and `tests` groups; docs never
do. Your own commits are not blocked.

**Gate pull requests (optional):** copy
[`integrations/github/ratchet.yml`](integrations/github/ratchet.yml) to
`.github/workflows/ratchet.yml`; it runs `uses: krishansubudhi/ratchet@v0`.
Using it? Add the badge:
`[![ratchet](https://img.shields.io/badge/code%20size-ratcheted-green)](https://github.com/krishansubudhi/ratchet)`

**Strict mode (optional):** to block your own commits too, install the
[git pre-commit hook](docs/integrations.md#strict-mode-the-git-hook).

**Badge (optional):** `ratchet badge` writes `.ratchet/badge.json`; commit it
(rerun to refresh) and paste the snippet from `ratchet badge --print-markdown`
into your README.

## What a refusal looks like

![A coding agent asked to commit a change is blocked by ratchet's git hook for one line over the ceiling; it stops and asks the human, who runs ratchet grant, and the commit then passes](docs/agent-demo.gif)

*A real headless Claude Code run, replayed: the commit is blocked by 1 line, the agent stops and asks instead of cutting code, and commits once a human grants it ([`docs/agent-demo.sh`](docs/agent-demo.sh)).*

```
ratchet: refused -- source grew 56 lines past its limit (556 / 500)

  app/api.py  +40
  app/store.py  +16

Fix it one of two ways:
  1. remove 56 lines of code (dead code, duplicates), or
  2. stop and ask a human to allow the growth (humans only -- never run this yourself):
     ratchet grant +56 --group source --reason "why"

Do not edit .ratchet.json or .ratchet-grants.jsonl to get past this.
Refused again on the same change? Stop here: report these numbers to a human instead of cutting more and resubmitting.
```

Humans see the same facts with "allow the growth" instead of "ask a human".
Other wordings: [How it works](docs/how-it-works.md#refusal-wording).

## More

- [Code growth, 2023 to 2026](docs/code-growth.md): line counts for 24 open-source repos; mature projects grew faster in 2026 than in 2023 to 2025.
- [How it works / FAQ](docs/how-it-works.md): what counts, the four rules,
  `ratchet budget`, grants, refusal wording, exit codes, requirements
- [Configuration](docs/configuration.md): `.ratchet.json`, groups, slack
- [Integrations](docs/integrations.md): Claude Code plugin, Cursor, Codex,
  aider, pre-commit, GitHub Actions, strict mode, CI
- [Uninstall](docs/uninstall.md)

## License

Apache-2.0. Copyright 2026 Krishan Subudhi.
