# ratchet

[![CI](https://github.com/krishansubudhi/ratchet/actions/workflows/ci.yml/badge.svg)](https://github.com/krishansubudhi/ratchet/actions/workflows/ci.yml)

**A code-size budget that only goes down.** Coding agents are good at adding
code and bad at deciding not to. `ratchet` gives the repo a line budget:
growth past the ceiling is refused, in plain words the agent can act on, and
only a human can raise it.

![ratchet refusing a duplicated-code change on pallets/click, then passing once the duplicate is removed](docs/demo.gif)

Real run, on [pallets/click](https://github.com/pallets/click): `ratchet init`
records today's size; an agent asked for a feature pastes a near-duplicate of
existing code instead of reusing it; `ratchet check` refuses the growth and
says exactly why; the duplicate goes, and the check passes again. Real
commands and output: [docs/examples.md](docs/examples.md). (The bloat step
is a scripted patch standing in for the agent, honestly -- see the caption
there.)

## Quickstart

1. **Install:** `pipx install ratchet-size` (or `pip install ratchet-size`,
   or `pip install -e .` from a clone).
2. **Record today's size:** `ratchet init` -- writes `.ratchet.json`; commit it.
3. **Wire up your agent:** paste this sentence to it: *"Set up ratchet in
   /path/to/repo by following
   https://github.com/krishansubudhi/ratchet/blob/main/SETUP-FOR-AGENTS.md"*

That's it. Everything past this point is detail you can come back to: what
counts as a line, the four rules, grants, config, and per-harness
integrations.

## Claude Code plugin

Prefer a plugin over the manual setup above? Ratchet ships as a Claude Code
plugin, with this repo doubling as its own marketplace:

```text
/plugin marketplace add krishansubudhi/ratchet
/plugin install ratchet@ratchet
```

That installs a **SessionStart** hook that prints the budget into context, a
**PostToolUse** meter that warns the moment an edit pushes a bucket over, and
a **Stop** hook (`ratchet check --hook`, falling back to `uvx` if `ratchet`
isn't on `PATH` yet) so Claude Code can't end a turn with the repo over
budget -- plus a `/ratchet:setup` command that runs the
[agent setup](SETUP-FOR-AGENTS.md) -- install, `ratchet init`, detect your
harness, `ratchet check` -- in the repo you're in. See
[`.claude-plugin/`](.claude-plugin) and [`hooks/hooks.json`](hooks/hooks.json)
for the manifests, or `claude plugin validate .` to check them yourself.

## What it counts

**Scope:** the one git repository you run it in (`git rev-parse
--show-toplevel`). Other repos on the machine are never touched, and each
repo gets its own `.ratchet.json`.

**Which files:** git-tracked files, plus untracked files that aren't
gitignored, whose extension is one of the code extensions present at
`init` (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.rb`, `.c`, `.sh`, and
more -- see `CODE_EXTS` in `ratchet/measure.py`). Blank lines don't count.

**Source vs tests:** a file matching a test glob (`test_*`, `*_test.*`,
`*_tests.*`, `*.test.*`, `*.spec.*`, or living under `tests/`, `test/`,
`__tests__/`, `spec/`) is `tests`; everything else is `source`. Both groups
are plain config in `.ratchet.json` -- edit `include`/`exclude`/`extensions`
to carve out a different split, e.g. `"exclude": ["vendor/**", "**/*.gen.*"]`
to stop counting vendored or generated code.

**Existing repo:** `ratchet init` measures today's totals and sets the
ceilings there (plus optional `--slack`). A file already over
`max_file_lines` is frozen at its current size, so nothing is refused on
day one -- you start where you are. From then on a ceiling may only shrink,
unless a human runs `ratchet grant`.

## Budget

The usual failure mode for an agent is to write the whole change, run the
check at the end, get refused, cut some lines, get refused again, and repeat
-- burning a turn each time on something it could have seen coming.
`ratchet budget` is the fix: it prints current vs ceiling, and remaining
headroom, per group, plus any file that's near its own per-file cap, without
running a single test:

```
$ ratchet budget
ratchet budget -- source 10,188/10,300 (112 left), tests 4,950/5,000 (50 left)
near the per-file cap:
  app/api.py is 390/400 (10 left)
```

`ratchet budget --json` gives the same numbers as data, for a harness.

Two hooks put it in front of the agent without it having to ask:

- A **SessionStart** hook prints it into the agent's context at the start of
  a session, so the ceiling is known before the first line is written.
- A **PostToolUse** hook (`ratchet budget --hook`) runs after every edit and
  stays silent until a bucket's remaining headroom goes negative, then
  prints one short warning with the overage -- mid-work, not only at the end.

Both ship with the Claude Code plugin; see [`hooks/hooks.json`](hooks/hooks.json)
and [integrations/claude-code](integrations/claude-code/README.md) to wire
them up by hand elsewhere.

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
Refused again on the same change? Stop here: report these numbers to a
human instead of cutting more and resubmitting.
```

Every refusal says what grew, by how much, and which fix applies: shrink,
split, or ask a human -- and, if this is the second time in a row, to stop
asking the agent and ask a human instead. For a harness, `ratchet check
--json` gives the same result as data.

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

## Running it by hand

`ratchet check` exits `0` when the repo is within budget, `1` when refused,
`2` on a setup error (bad config, not a git repo when `--base` is used, and
so on). `ratchet budget` always exits `0` -- it's a report, not a gate --
except in `--hook` mode (see above), which exits `2` the moment headroom
goes negative. `python -m ratchet` works the same as the `ratchet` entry
point, if you don't have it on `PATH`.

## Integrations

| Harness | How |
|---------|-----|
| Claude Code | Stop hook `ratchet check --hook`: [integrations/claude-code](integrations/claude-code/README.md) |
| Cursor, Codex CLI, aider | instruction file + git hook / test-cmd: [integrations/other-agents.md](integrations/other-agents.md) |
| pre-commit | framework hook, or a plain git hook: [integrations/pre-commit](integrations/pre-commit/README.md) |
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
