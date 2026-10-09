# Integrations

Back to the [README](../README.md). The easiest path: tell your agent to follow
[SETUP-FOR-AGENTS.md](../SETUP-FOR-AGENTS.md); it is self-contained, wires up
the agent running it first, then any other harness it detects in the repo.

| Harness | How |
|---------|-----|
| Claude Code | Stop hook `ratchet check --hook`: [integrations/claude-code](../integrations/claude-code/README.md), or the plugin below |
| Cursor, Codex CLI, aider | instruction file (+ opt-in git hook) / aider test-cmd: [integrations/other-agents.md](../integrations/other-agents.md) |
| pre-commit (opt-in strict) | framework hook, or a plain git hook: [integrations/pre-commit](../integrations/pre-commit/README.md) |
| GitHub Actions | `uses: krishansubudhi/ratchet@v0`: [integrations/github](../integrations/github/README.md) |
| Anything else | prompt snippet: [integrations/any-agent.md](../integrations/any-agent.md) |

## Claude Code plugin

Prefer a plugin over the manual setup? Ratchet ships as a Claude Code
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
[agent setup](../SETUP-FOR-AGENTS.md) -- install, `ratchet init`, detect your
harness, `ratchet check` -- in the repo you're in. See
[`.claude-plugin/`](../.claude-plugin) and [`hooks/hooks.json`](../hooks/hooks.json)
for the manifests, or `claude plugin validate .` to check them yourself.

## Strict mode: the git hook

By default ratchet refuses the *agent* when it tries to finish with code over
the ceiling; your own commits are not blocked. To also block your own
commits, install the git pre-commit hook:

```sh
curl -o .git/hooks/pre-commit https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/git/pre-commit && chmod +x .git/hooks/pre-commit
```

What you sign up for: any commit that grows code past the ceiling is refused
until you delete code or a human runs `ratchet grant +N --reason ...`.

## CI

Use the GitHub Action, or run `ratchet check --base <target branch>` in any
CI. `--base` also refuses ceilings raised without a matching grant; see
[How grants work](how-it-works.md#how-grants-work). For a harness,
`ratchet check --json` and `ratchet budget --json` give results as data.
