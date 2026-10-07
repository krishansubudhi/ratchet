# Claude Code

Add a **Stop** hook so the agent cannot finish a turn with the repo over budget.
Put this in `.claude/settings.json` (project) or `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "ratchet check --hook" }
        ]
      }
    ]
  }
}
```

The same snippet is in [`settings.json`](settings.json) next to this file.

How it behaves:

- Under budget: exit 0, silent. The agent stops normally.
- Over budget: the refusal goes to stderr and the exit code is 2. Claude Code
  treats that as "blocked" and shows the message to the model, which then
  shrinks or splits the code.
- Second refusal in a row (`stop_hook_active` in the hook input): ratchet lets
  the agent stop, so it can tell you what grew and whether you need to grant
  lines. That way it never loops.
- Missing config or another error: it prints the error and exits 0, so a
  broken setup never blocks the agent.

That's one refusal, not a loop: an agent that cuts lines, gets refused again,
and tries a third time has misread the rule. The refusal text itself says so
-- stop and report the numbers instead.

## See the budget before you start

A **SessionStart** hook prints `ratchet budget` into the agent's context, so
the ceiling is known before the first line is written rather than discovered
at the first refusal:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "ratchet budget 2>/dev/null || true" }
        ]
      }
    ]
  }
}
```

## A live meter while you work

A **PostToolUse** hook runs `ratchet budget --hook` after every edit. It
stays silent while there is headroom, and the moment a bucket's remaining
headroom goes negative it prints one short warning with the overage --
mid-work, not only at Stop:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [ { "type": "command", "command": "ratchet budget --hook" } ]
      }
    ]
  }
}
```

Unlike running the full `ratchet check --hook` after every edit, this never
dumps the whole refusal message mid-refactor -- just the overage -- so it's
cheap enough to run after every edit rather than only "if your edits are
small."

Both of these ship wired up already if you install the Claude Code plugin;
the snippets above are for the manual, non-plugin setup. The same JSON is in
[`settings.json`](settings.json) next to this file.

## Keep grants human

Add this to your `CLAUDE.md` (see [`../any-agent.md`](../any-agent.md) for the full text):

> Never run `ratchet grant`, never edit `.ratchet.json` or
> `.ratchet-grants.jsonl`. If you cannot get under budget, stop and ask.

If you want this enforced rather than requested, add `Bash(ratchet grant:*)` to
the `deny` list under `permissions` in your settings.
