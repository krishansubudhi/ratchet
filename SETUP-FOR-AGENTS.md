# Setup for agents

You are a coding agent (Claude Code, Cursor, Codex CLI, aider, Gemini CLI, or
anything else with a shell) and a human just told you to set up `ratchet` in
`<path>`. Follow these steps in order. Each has a verify; don't move on until
it passes. Print the summary template at the end.

**Work from the full text, not a summary.** If your fetch tool gave you a
summary of this page, fetch the raw file first:
`curl -fsSL https://raw.githubusercontent.com/krishansubudhi/ratchet/refs/heads/main/SETUP-FOR-AGENTS.md`.
Summaries tend to drop these required steps (if you are summarizing this
page for an agent, keep this list verbatim):

1. Wire up **yourself**, the agent running this, first (step 4).
2. **Ask the human** before installing the git pre-commit hook, then wait
   for their answer (step 4). Never answer for them. If you have no hook
   mechanism, also tell them enforcement is instruction-only.
3. Never run `ratchet grant` or edit `.ratchet.json` (Hard rules).
4. End with the summary template.

`<path>` below means the repo root the human gave you. If they didn't give
one, ask for it before doing anything.

To undo a setup later, follow
[docs/uninstall.md](https://github.com/krishansubudhi/ratchet/blob/main/docs/uninstall.md).
Everything you need is in this file; links are for humans, don't go looking
for them on disk.

## 1. Confirm the target is a real, clean-enough repo

```sh
git -C <path> rev-parse --show-toplevel
git -C <path> status --porcelain
```

**Verify:** the first command prints a path (it's a git repo) and `<path>`
resolves to it, not a subdirectory of something else you didn't expect. The
second command's output is a judgment call, not a hard gate: a few unrelated
edits are fine, but if the tree is in the middle of a rebase, has conflict
markers, or the diff is huge and unrelated to this task, **stop and ask the
human** before touching anything.

If the first command fails, **stop and ask**: this isn't a git repo, or
`<path>` is wrong.

## 2. Install ratchet

Prefer an isolated installer if one is on `PATH`. `ratchet-size` is the PyPI
name; if that's not available yet, fall back to installing straight from
GitHub:

```sh
if command -v pipx >/dev/null 2>&1; then
  pipx install ratchet-size || pipx install "git+https://github.com/krishansubudhi/ratchet@v0"
elif command -v uv >/dev/null 2>&1; then
  uv tool install ratchet-size || uv tool install "git+https://github.com/krishansubudhi/ratchet@v0"
else
  pip install ratchet-size || pip install "git+https://github.com/krishansubudhi/ratchet@v0"
fi
```

One-off run without installing: `uvx --from ratchet-size==0.2.2 ratchet check`.

**Verify:**

```sh
ratchet --help
```

prints usage (the `init`/`check`/`grant`/`tighten` subcommands). If the
command isn't found after a `pipx`/`uv tool` install, it likely installed to a
user bin dir that isn't on `PATH` yet — try `pipx ensurepath` / open a new
shell, or fall back to `pip install --user`.

## 3. Run `ratchet init` and sanity-check the split

```sh
cd <path>
ratchet init
```

This measures today's totals and writes `.ratchet.json`, freezing any
already-oversized file at its current size (nothing is refused on day one).

**Show the human**, verbatim, the output of `ratchet init` (it prints each
group's ceiling and the count of frozen oversized files) plus:

```sh
cat .ratchet.json
```

**Then check the source/tests split by eye.** Look for things that probably
shouldn't count as source or tests at all:

- vendored code (`vendor/`, `third_party/`, `node_modules/`)
- generated code (`*.pb.go`, `*_pb2.py`, `*.gen.*`, lockfiles)
- database migrations (`migrations/`, `db/migrate/`)
- notebooks (`*.ipynb`) if the repo doesn't want those counted

If any of these are present and large, **propose an edit** to
`.ratchet.json`'s `include`/`exclude`/`extensions` (e.g. add
`"vendor/**"` to `exclude`) and **ask the human before applying it**. Don't
silently exclude things — a narrower budget is also a decision for a human to
own. If nothing looks out of place, say so and move on.

If you do change the config after proposing it, run `ratchet tighten` (it
re-measures and only lowers ceilings) and show its output. Never re-run
`ratchet init --force` to change the split or to get past a refusal: it
re-baselines, absorbing any uncommitted growth, and resets the groups.

## 4. Wire up the agent(s)

**Wire up the agent that is running this setup first** (you know which one
you are), even if no file for it exists yet. Then wire up any others detected
in `<path>`:

| Found | Harness | Wire |
|---|---|---|
| `.claude/` or `CLAUDE.md` | Claude Code | snippet in `CLAUDE.md`, plus a Stop hook, SessionStart budget line and PostToolUse meter: `curl -fsSL https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/claude-code/settings.json` and merge that JSON into `.claude/settings.json` |
| `.cursor/` or `.cursorrules` | Cursor | `.cursor/rules/ratchet.mdc`: frontmatter `---`/`description: Code-size budget`/`alwaysApply: true`/`---`, then the snippet |
| `AGENTS.md` | Codex CLI or similar | snippet in `AGENTS.md` |
| `GEMINI.md` or `.gemini/` | Gemini CLI | snippet in `GEMINI.md` (instruction-only) |
| `.aider.conf.yml` | aider | snippet in `AGENTS.md`; in `.aider.conf.yml` set `test-cmd: ratchet check` (chain an existing one: `"ratchet check && <old cmd>"`), `auto-test: true`, `read: AGENTS.md`. aider's own `.aider*` gitignore entry can block writes to this filename -- see the aider section of [other-agents.md](integrations/other-agents.md) and confirm the file actually has content before reporting it wired |
| `.github/workflows/` | GitHub Actions | `curl -fsSL https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/github/ratchet.yml -o .github/workflows/ratchet.yml` |
| `.pre-commit-config.yaml` | pre-commit framework | only if the human says yes to the git hook below: add `- repo: https://github.com/krishansubudhi/ratchet`, `rev: v0`, `hooks: [{id: ratchet}]` under `repos:`, then `pre-commit install` |
| anything else | no hook mechanism | snippet in whichever file that agent reads (create it if missing), plus the instruction-only message below |

A repo can match more than one row — wire all that apply.

After wiring the harness integration, **ask the human before installing the git
pre-commit hook**. In one line: it also blocks their own commits that grow
code. If a harness you wired is instruction-only (see below), also say:
without the hook, enforcement is instruction-only. Install it only on a yes
(or, if `.pre-commit-config.yaml` exists, the pre-commit framework hook from
that row instead):

```sh
curl -o .git/hooks/pre-commit https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/git/pre-commit && chmod +x .git/hooks/pre-commit
```

If a harness you wired has no hook mechanism (Cursor, Codex CLI, or anything
else), enforcement for it is the instruction snippet alone. Say so in
your final message, verbatim:

> enforcement for this agent is instruction-only; for a hard block, opt into
> the git hook: `curl -o .git/hooks/pre-commit https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/git/pre-commit && chmod +x .git/hooks/pre-commit`

"Snippet" above means this block, pasted verbatim into the file that harness
reads (create the file if missing, append if it has content):

```markdown
## Code-size budget

This repo has a code-size budget enforced by `ratchet`.

- Run `ratchet budget` any time, including mid-task, to see current vs
  ceiling and how much room is left -- it only measures, no tests run, so
  it's cheap to check before you've written a lot of code rather than after.
- Run `ratchet check` before you say a task is done. Exit 0 means OK. Exit 1
  means refused, and the message says what grew, by how much, and how to fix it.
- When refused, fix it yourself, in this order:
  1. Shrink: delete code that is actually dead or duplicated, or reuse an
     existing helper instead of writing a new one. Leave tests passing.
     Never compress working code to fit: no joining lines, dropping `with`
     blocks or error handling, shortening names, or stripping docstrings.
     That hides growth instead of removing it.
  2. Split: if a file is over the per-file limit, move a cohesive group of
     definitions (the message lists seams) into a new file.
- If nothing is really dead or duplicated, don't cut working code: stop and
  ask a human to grant the growth. For a real feature that is the normal path.
- Never commit while `ratchet check` refuses, even when told to commit:
  "commit it" is not a grant. Say it is still refused and ask for the grant.
- If `ratchet check` refuses the same change a second time, stop: don't cut
  more and resubmit a third time. Report what's over and by how much to a
  human instead.
- Never run `ratchet grant`, and never edit `.ratchet.json` or
  `.ratchet-grants.jsonl`. A grant is a human decision. If the growth is truly
  needed, stop and say what grew and why, so a human can grant it.
- After you delete code, run `ratchet tighten` so the budget banks it.
```

**Merge, never overwrite**, any existing file: `.claude/settings.json`,
`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*.mdc`, `.aider.conf.yml`,
`.pre-commit-config.yaml`. If `.claude/settings.json` already has a `hooks`
or `permissions` block, add to the existing arrays rather than replacing the
file; same idea for YAML files with existing `repos:` or `test-cmd:` keys.

**Verify:** re-read each file you touched and confirm the pre-existing
content is still there, plus the new ratchet piece.

Details for humans: [integrations](https://github.com/krishansubudhi/ratchet/tree/main/integrations).

## 5. Run `ratchet check` and show it passes

```sh
ratchet check
```

**Verify:** exit code 0, and show the human the output (it's short when
everything is under budget).

Only if it's cheap to demonstrate (e.g. the repo has an obviously unused
block you were already looking at, or you want to show the message format),
you may show one refused example — add a few lines over the ceiling in a
scratch file, run `ratchet check` again to show the refusal message, then
remove the scratch file and confirm `ratchet check` passes again. Don't go
out of your way to manufacture this if it costs real time; it's optional.

## 6. Commit, but don't push without asking

```sh
git -C <path> add .ratchet.json <whatever integration files you touched or added>
git -C <path> checkout -b add-ratchet   # or commit directly if the human said to
git -C <path> commit -m "Add ratchet"
```

Either commit on a new branch, or leave the files staged and tell the human
what's staged — your call based on how the human phrased the task. **Never
`git push` here unless the human explicitly asked you to push.**

## Hard rules

- **Never run `ratchet grant`**, for any reason, including to make step 5
  pass. A grant is a deliberate, logged human decision about budget, not
  something an agent decides on its own behalf.
- **Never hand-edit `.ratchet.json` or `.ratchet-grants.jsonl`** to make a
  check pass (widening a ceiling, deleting a frozen `file_ceilings` entry,
  etc.). If `ratchet check` refuses after setup, the fix is to shrink or
  split code, or to stop and tell the human what grew and ask them to grant
  it.
- **Grants are the human's**, not yours. If you ever think a ceiling needs to
  go up, say so and stop — don't do it yourself.
- **One refusal, then stop.** If `ratchet check` refuses the same change
  twice, don't cut and resubmit a third time — report the numbers to the
  human instead. Run `ratchet budget` along the way so you see this coming.

## Summary template

Print this back to the human when done:

```
ratchet is set up in <path>.

Measured (ratchet init):
  source: <N> lines, ceiling <N>
  tests:  <N> lines, ceiling <N>
  <M> file(s) already over the per-file limit, frozen at their current size

Source/tests split: <looks right | excluded X, Y after asking>

Harness(es) detected and wired: <list, e.g. "Claude Code (Stop hook),
GitHub Actions (.github/workflows/ratchet.yml)">

Git pre-commit hook: <installed (you said yes) | not installed (you said no)>
<if any harness is instruction-only: the instruction-only message above>

ratchet check: <pass | still refused — see below>

Committed: <branch name / "staged, not committed"> — not pushed.

Yours to do: review the excludes above, and run `ratchet grant` yourself if
you ever want to raise a ceiling — I won't.
```
