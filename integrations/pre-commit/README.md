# pre-commit

Two ways to run `ratchet check` on every commit. Pick one.

## 1. Using the pre-commit framework (pre-commit.com)

In **your** repo's root, add or extend `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/krishansubudhi/ratchet
    rev: v0
    hooks:
      - id: ratchet
```

Then run:

```sh
pre-commit install
```

Run `ratchet init` first and commit `.ratchet.json`, so there is a budget for
the hook to check against.

## 2. Without the framework (plain git hook)

From a clone of this repo:

```sh
cp integrations/git/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

That copies [`integrations/git/pre-commit`](../git/pre-commit) into your
repo's hooks. If you don't have a clone handy, write it directly:

```sh
curl -fsSL https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/git/pre-commit \
  -o .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```
