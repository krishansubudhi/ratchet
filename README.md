# ratchet

**A code-size budget that only goes down.**

Coding agents are good at adding code and bad at deciding not to. Each change
looks reasonable on its own: a helper next to one that already exists, a
defensive branch nobody needs, a 900-line file that keeps getting a little
longer. A month later the repo is twice the size and no better.

`ratchet` gives the repo a line budget. Growth past the recorded ceiling is
refused, an oversized file has to be split, and only a human can raise a
ceiling, with a logged reason. When the code shrinks, `ratchet tighten` lowers
the ceilings, and they never go back up on their own. It works with any agent
harness, has no dependencies, and tells the agent in plain words what to do
next.

## Quickstart

```sh
pip install -e .            # from a clone, or `pip install ratchet-size` once published
ratchet init                # records today's totals in .ratchet.json; commit it
ratchet check               # exit 0 = within budget, 1 = refused, 2 = setup error
```

Then wire `ratchet check` into your agent (see [Integrations](#integrations)).
`python -m ratchet` works too.

## What the agent sees when refused

```
ratchet: REFUSED -- 2 problems (source 10,412/10,300, tests 4,980/5,000)

1. source is 10,412 lines, ceiling 10,300: 112 over
   grew vs HEAD: app/api.py +80, app/store.py +40
   fix: remove at least 112 lines of source: delete dead code, reuse what
   exists instead of adding a parallel version, simplify.
2. app/api.py is 431 lines, limit 400
   seams near the middle: line 198 `def upload`, line 230 `class Session`
   fix: split it at a seam: move a cohesive group of definitions into a new
   file, so each piece is under 400 lines.

Do not edit .ratchet.json or .ratchet-grants.jsonl to get past this.
If the growth is truly needed, stop and ask a human to run:
  ratchet grant +112 --group source --reason "<why>" --by <name>
  ratchet grant +31 --file app/api.py --reason "<why>" --by <name>
```

Every refusal says what grew, by how much, and which fix applies: shrink,
split, or ask a human. For a harness, `ratchet check --json` gives the same
result as data.

## The four rules

| Rule | What it does |
|------|--------------|
| **Budget** | Each group (`source`, `tests` by default) has a ceiling. A total over it is refused. |
| **Seams** | A file over `max_file_lines` (default 400) is refused, with the top-level definitions nearest the middle offered as places to cut. A file already over the limit at `init` is recorded at its size: it may shrink, never grow. |
| **Grants** | Only `ratchet grant` raises a limit, and every grant is appended to `.ratchet-grants.jsonl` with who and why. |
| **Tighten** | `ratchet tighten` lowers every ceiling to the measured size (plus optional `slack`). Nothing ever raises it automatically. |

Lines are counted without blanks. Docs, data, and fixtures don't count: only
files whose extensions you list in `.ratchet.json` do.

## How grants work

Sometimes the growth is the point: a real feature, a new integration. Then a
human runs:

```sh
ratchet grant +300 --group source --reason "CSV export (issue 41)" --by alice
ratchet grant +60 --file app/api.py --reason "until the router split lands" --by alice
```

That raises the ceiling in `.ratchet.json` and appends a line to
`.ratchet-grants.jsonl`:

```json
{"after": 10600, "before": 10300, "by": "alice", "lines": 300, "reason": "CSV export (issue 41)", "target": "source", "ts": "2026-01-15T09:30:00Z"}
```

Commit both files. Here is what keeps grants honest:

- **In CI, run `ratchet check --base <target branch>`.** It refuses any ceiling
  that is higher than the base's unless grants appended since the base pay for
  it. An agent that edits `.ratchet.json` by hand passes locally and fails
  review. The check also refuses a grants log that was rewritten rather than
  appended to.
- Grants are one-line diffs in the pull request, so a reviewer sees them.
- Tell your agent never to run `ratchet grant`. The Claude Code integration
  also puts it on the permission deny list.

Run `ratchet tighten` after a cleanup and commit the result. The room you
freed is now the new ceiling.

## Integrations

| Harness | How |
|---------|-----|
| Claude Code | Stop hook `ratchet check --hook`: [integrations/claude-code](integrations/claude-code/README.md) |
| Cursor, Codex CLI, aider | instruction file + git hook / test-cmd: [integrations/other-agents.md](integrations/other-agents.md) |
| pre-commit | `.pre-commit-hooks.yaml`, hook id `ratchet` |
| GitHub Actions | `uses: krishansubudhi/ratchet@v0`: [integrations/github](integrations/github/README.md) |
| Anything else | prompt snippet: [integrations/any-agent.md](integrations/any-agent.md) |

## Configuration

`ratchet init` writes `.ratchet.json`. It is JSON because ratchet must write
the file, and Python's standard library reads TOML but cannot write it.

```json
{
  "version": 1,
  "max_file_lines": 400,
  "slack": 0,
  "groups": {
    "source": {"include": ["**"], "exclude": ["**/tests/**", "**/test_*"], "extensions": [".py", ".ts"]},
    "tests":  {"include": ["**/tests/**", "**/test_*"], "extensions": [".py", ".ts"]}
  },
  "ceilings": {"source": 10300, "tests": 5000},
  "file_ceilings": {"app/legacy.py": 1210}
}
```

- Globs work like gitignore: `**/` means any number of directories.
- Each file belongs to the first group that matches it.
- `slack` keeps some headroom above the measured size after `init` and
  `tighten`, if you would rather not require a delete for every add.
- Files are listed with `git ls-files`, so ignored files never count.
  Outside git, ratchet walks the tree and skips the usual build and vendor
  directories.

`ratchet init --max-file-lines 300 --slack 50` sets both at creation.

## Requirements

Python 3.10+, git (optional, needed for `--base` and the "grew vs" lines). No
dependencies. Tests: `pip install pytest && python -m pytest -q`.

## License

Apache-2.0. Copyright 2026 Krishan Subudhi.
