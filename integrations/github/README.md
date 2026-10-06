# GitHub Action

The action is [`action.yml`](../../action.yml) at the repo root. It is
standard-library Python, so it installs nothing and runs on any runner that
has `python3`.

```yaml
# .github/workflows/ratchet.yml
name: ratchet
on: [pull_request]
jobs:
  budget:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # --base needs the base commit
      - uses: OWNER/ratchet@v0    # replace OWNER once published
```

On a pull request the action runs `ratchet check --base <PR base sha>`. That
adds two checks to the local ones:

- **Unpaid raises.** If the PR raises a ceiling in `.ratchet.json` without
  matching entries appended to `.ratchet-grants.jsonl`, it fails. An agent that
  edits the config to make room gets caught in review, not trusted.
- **Append-only grants.** If the PR rewrites or deletes existing grant lines,
  it fails.

Grants show up in the PR diff as single JSON lines, with who granted the lines
and why.
