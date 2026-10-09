# Any agent: the prompt snippet

Paste this into whatever file your agent reads at startup: `AGENTS.md`,
`CLAUDE.md`, `.cursor/rules/*.mdc`, `CONVENTIONS.md`, a system prompt, or
anything else.

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
- If `ratchet check` refuses the same change a second time, stop: don't cut
  more and resubmit a third time. Report what's over and by how much to a
  human instead.
- Never run `ratchet grant`, and never edit `.ratchet.json` or
  `.ratchet-grants.jsonl`. A grant is a human decision. If the growth is truly
  needed, stop and say what grew and why, so a human can grant it.
- After you delete code, run `ratchet tighten` so the budget banks it.
```

The snippet works without any hook. A hook or a CI check makes it binding
rather than a request. See the other files in this directory.
