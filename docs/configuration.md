# Configuration

Back to the [README](../README.md). What counts and why: [How it works](how-it-works.md).

`ratchet init` writes `.ratchet.json` at the repo root; commit it. It is JSON
because ratchet must write the file, and Python's standard library reads TOML
but cannot write it.

```json
{
  "version": 1,
  "max_file_lines": 400,
  "slack": 0,
  "groups": {
    "source": {"include": ["**"], "exclude": ["**/tests/**", "**/test_*"], "extensions": [".py", ".ts"]},
    "tests":  {"include": ["**/tests/**", "**/test_*"], "extensions": [".py", ".ts"]}
  },
  "ceilings": {"source": 10300, "tests": 5000},
  "file_ceilings": {"app/legacy.py": 1210}
}
```

`ratchet init` actually fills `tests.include` (and `source.exclude`) with the
full set of test globs listed in [How it works](how-it-works.md#what-it-counts)
-- the two shown above are trimmed for readability.

- Globs work like gitignore: `**/` means any number of directories.
- Each file belongs to the first group that matches it.
- Edit `include`/`exclude`/`extensions` to change what counts, e.g.
  `"exclude": ["vendor/**", "**/*.gen.*"]` to stop counting vendored or
  generated code. Then run `ratchet tighten`, which re-measures and only
  lowers ceilings. Don't use `init --force` to change the split or to get
  past a refusal: it re-baselines, so it refuses on uncommitted code.
- `slack` keeps some headroom above the measured size after `init` and
  `tighten`, if you would rather not require a delete for every add.
- Files are listed with `git ls-files`, so ignored files never count.
  Outside git, ratchet walks the tree and skips the usual build and vendor
  directories.

`ratchet init --max-file-lines 300 --slack 50` sets both at creation.

Don't edit `ceilings` or `file_ceilings` by hand to raise them: use
`ratchet grant` (see [How grants work](how-it-works.md#how-grants-work)).
