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

## Optional: check after every edit

A `PostToolUse` hook gives faster feedback, but it fires while a refactor is
half done. Use it only if your edits are small:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [ { "type": "command", "command": "ratchet check --hook" } ]
      }
    ]
  }
}
```

## Keep grants human

Add this to your `CLAUDE.md` (see [`../any-agent.md`](../any-agent.md) for the full text):

> Never run `ratchet grant`, never edit `.ratchet.json` or
> `.ratchet-grants.jsonl`. If you cannot get under budget, stop and ask.

If you want this enforced rather than requested, add `Bash(ratchet grant:*)` to
the `deny` list under `permissions` in your settings.
