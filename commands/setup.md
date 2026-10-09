---
description: Install ratchet and wire it into this repo by following SETUP-FOR-AGENTS.md
---

Follow the step-by-step instructions at
https://raw.githubusercontent.com/krishansubudhi/ratchet/main/SETUP-FOR-AGENTS.md exactly,
treating the current repository root (`git rev-parse --show-toplevel`) as
`<path>`.

Fetch that file now and follow it from step 1. Don't skip the verify after
each numbered step, and print the summary template at the end exactly as
that document specifies.

Hard rules, repeated here because they matter: never run `ratchet grant`,
never hand-edit `.ratchet.json` or `.ratchet-grants.jsonl` to make a check
pass, and never `git push` unless explicitly asked.
