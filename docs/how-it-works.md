# How it works

Back to the [README](../README.md). See also [Configuration](configuration.md),
[Integrations](integrations.md), [Uninstall](uninstall.md).

## What it counts

**Scope:** the one git repository you run it in (`git rev-parse
--show-toplevel`). Other repos on the machine are never touched, and each
repo gets its own `.ratchet.json`.

**Which files:** git-tracked files, plus untracked files that aren't
gitignored, whose extension is one of the code extensions present at
`init` (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.rb`, `.c`, `.sh`, and
more -- see `CODE_EXTS` in `ratchet/measure.py`). Blank lines don't count.
README and docs edits never count.

**Source vs tests:** a file matching a test glob (`test_*`, `*_test.*`,
`*_tests.*`, `*.test.*`, `*.spec.*`, or living under `tests/`, `test/`,
`__tests__/`, `spec/`) is `tests`; everything else is `source`. Both groups
are plain config in `.ratchet.json` -- edit `include`/`exclude`/`extensions`
to carve out a different split, e.g. `"exclude": ["vendor/**", "**/*.gen.*"]`
to stop counting vendored or generated code. See [Configuration](configuration.md).

**Existing repo:** `ratchet init` measures today's totals and sets the
ceilings there (plus optional `--slack`). A file already over
`max_file_lines` is frozen at its current size, so nothing is refused on
day one -- you start where you are. From then on a ceiling may only shrink,
unless a human runs `ratchet grant`.

**Without git:** ratchet works without git too: outside a repo it walks the
directory; only strict mode, `--base`, and the "grew vs HEAD" breakdown need
git.

## The four rules

| Rule | What it does |
|------|--------------|
| **Budget** | Each group (`source`, `tests` by default) has a ceiling. A total over it is refused. |
| **Seams** | A file over `max_file_lines` (default 400) is refused, with the top-level definitions nearest the middle offered as places to cut. A file already over the limit at `init` is recorded at its size: it may shrink, never grow. |
| **Grants** | Only `ratchet grant` raises a limit, and every grant is appended to `.ratchet-grants.jsonl` with who and why. |
| **Tighten** | `ratchet tighten` lowers every ceiling to the measured size (plus optional `slack`). Nothing ever raises it automatically. |

Lines are counted without blanks. Docs, data, and fixtures don't count: only
files whose extensions you list in `.ratchet.json` do.

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

Both ship with the Claude Code plugin; see [`hooks/hooks.json`](../hooks/hooks.json)
and [integrations/claude-code](../integrations/claude-code/README.md) to wire
them up by hand elsewhere.

## Refusal wording

A human committing through the git hook sees:

```
ratchet: commit blocked -- source grew 1 line past its limit (1,129 / 1,128)

  starter.py  +1

Fix it one of two ways:
  1. remove 1 line of code (dead code, duplicates), or
  2. allow the growth (humans only -- agents must ask, never run this):
     ratchet grant +1 --group source --reason "why"
```

An agent sees the same facts, told to ask rather than grant, and to stop
after a second refusal:

```
ratchet: refused -- 2 problems

1. source grew 56 lines past its limit (556 / 500)
     app/api.py  +40
     app/store.py  +16

   Fix it one of two ways:
     1. remove 56 lines of code (dead code, duplicates), or
     2. stop and ask a human to allow the growth (humans only -- never run this yourself):
        ratchet grant +56 --group source --reason "why"

2. app/api.py is 20 lines past its limit (420 / 400)
     seams near the middle: line 313 `def upload`, line 316 `class Session`

   Fix it one of two ways:
     1. split it at a seam: move a cohesive group of definitions into a new file, each under 400 lines, or
     2. stop and ask a human to allow the growth (humans only -- never run this yourself):
        ratchet grant +20 --file app/api.py --reason "why"

Do not edit .ratchet.json or .ratchet-grants.jsonl to get past this.
Refused again on the same change? Stop here: report these numbers to a human instead of cutting more and resubmitting.
```

Agent wording is used under `check --hook`, when `RATCHET_AGENT=1`, or when
a known agent's variable is set (`CLAUDECODE`, `CURSOR_AGENT`, `GEMINI_CLI`);
`RATCHET_AGENT=0` forces the human wording. "commit blocked" replaces
"refused" when run from a git hook. For a harness, `ratchet check --json`
gives the same result as data.

## How grants work

Sometimes the growth is the point: a real feature, a new integration. Then a
human runs:

```sh
ratchet grant +300 --group source --reason "CSV export (issue 41)"
ratchet grant +60 --file app/api.py --reason "until the router split lands"
```

`--by` defaults to `git config user.name` (else `$USER`); pass it to override.

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

## Requirements

Python 3.10+, git (optional, needed for `--base` and the "grew vs" lines). No
dependencies. Tests: `pip install pytest && python -m pytest -q`.
