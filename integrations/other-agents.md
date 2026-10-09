# Cursor, Codex CLI, aider, and friends

Every harness can do two things: read instructions, and run git. ratchet uses both.

1. **Instructions.** Paste the snippet from [`any-agent.md`](any-agent.md) into
   the file your agent reads at startup.
2. **A gate the agent cannot talk its way past.** Where the harness has a
   finish hook, use it. Otherwise the snippet is a request, not a block; for a
   hard block, opt into strict mode with a git pre-commit hook (below) or
   [pre-commit](https://pre-commit.com), and/or the
   [GitHub Action](github/README.md) in CI.

## Git pre-commit hook (no framework, opt-in strict mode)

This blocks every commit that grows code past the ceiling, including your
own, until code is deleted or a human runs `ratchet grant`.

```sh
cp integrations/git/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook measures the working tree, not just the staged files. That is the
stricter choice: what you are about to leave behind must fit.

## Cursor

Create `.cursor/rules/ratchet.mdc`:

```markdown
---
description: Code-size budget
alwaysApply: true
---
<paste the snippet from any-agent.md>
```

Without a hook this is instruction-only. If you opted into the pre-commit
hook, it applies to Cursor's commits too.

## Codex CLI

Put the snippet in `AGENTS.md` at the repo root. Codex reads it on every run.
Instruction-only by default; opt into the pre-commit hook if you want a
commit it makes refused while over budget.

## aider

aider skips git hooks on its own commits by default, so wire ratchet in as its
test command. aider runs it after each change and shows the model any failure:

```yaml
# .aider.conf.yml
test-cmd: ratchet check
auto-test: true
read: AGENTS.md   # holding the snippet from any-agent.md
```

aider's own `--gitignore` default (on unless disabled) writes `.aider*` to
`.gitignore` the first time it runs in a repo. That pattern also matches
`.aider.conf.yml`, so aider will silently refuse to create or edit it
("Skipping edits to .aider.conf.yml that matches gitignore spec") and the
test-cmd never gets wired. Check `.gitignore` for a bare `.aider*` line before
writing the config; if it's there, narrow it (e.g. `.aider.chat.history.md`,
`.aider.tags.cache.v4/`) or add `.aider.conf.yml` back with a `!.aider.conf.yml`
line, then verify the file actually has content before reporting it as wired.

If you already have a test command, chain the two with `ratchet check`
first: size is cheap to check and tells you to stop before you pay for a
slow test run that a refusal would have thrown away anyway.
`test-cmd: "ratchet check && pytest -q"`.

## Anything else

If the harness lets you run a command when the agent finishes, run
`ratchet check --hook`: the refusal goes to stderr and the exit code is 2. For
a machine-readable result, run `ratchet check --json`.
