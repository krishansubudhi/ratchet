# Uninstall

Back to the [README](../README.md).

Undo whichever pieces you wired up, from the repo root:

| Piece | Remove |
|-------|--------|
| Git hook (strict mode) | `grep -q ratchet .git/hooks/pre-commit && rm .git/hooks/pre-commit` (only deletes it if it's ratchet's) |
| pre-commit framework | delete the `ratchet` hook from `.pre-commit-config.yaml` |
| Claude Code settings | delete the ratchet `SessionStart`, `PostToolUse` and `Stop` entries (and the `ratchet grant` deny rule) from `.claude/settings.json` |
| Claude Code plugin | `/plugin uninstall ratchet@ratchet`, then optionally `/plugin marketplace remove ratchet` |
| Instruction files | delete the "Code-size budget" snippet from `AGENTS.md`, `CLAUDE.md`, or `.cursor/rules/ratchet.mdc` |
| aider | drop `ratchet check` from `test-cmd` in `.aider.conf.yml` |
| GitHub Actions | delete `.github/workflows/ratchet.yml` |
| Budget and grant log | `rm .ratchet.json .ratchet-grants.jsonl` |
| The tool itself | `pipx uninstall ratchet-size` (or `pip uninstall ratchet-size` / `uv tool uninstall ratchet-size`) |
