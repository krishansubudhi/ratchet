#!/usr/bin/env python3
"""Count source lines in a git repo at fixed dates. Stdlib + git only.

    python scripts/code_growth.py https://github.com/pallets/flask [more urls]

Prints CSV rows: repo,date,commit,files,lines (lines blank if the repo had
no commit before that date). Each repo is cloned bare into a temp dir,
default branch only, and every blob is read once (git cat-file --batch).

What counts (the rule, exactly):
- a file whose extension is in CODE_EXT below;
- not under a path part in SKIP_DIRS (vendored, generated, build output,
  docs, examples, fixtures);
- not a lock file, minified file, or a name containing "generated" or ".pb.";
- not larger than 512 KB (almost always generated or bundled data).
Lines are newline counts, blank lines and comments included.
"""

import csv
import os
import subprocess
import sys
import tempfile
from datetime import date

DATES = ["2023-01-01", "2024-01-01", "2025-01-01", "2026-01-01", "today"]
CODE_EXT = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts",
    ".cts", ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh",
    ".java", ".kt", ".kts", ".scala", ".swift", ".m", ".mm", ".rb", ".php",
    ".cs", ".fs", ".lua", ".sh", ".bash", ".zsh", ".ps1", ".vue", ".svelte",
    ".dart", ".ex", ".exs", ".erl", ".hs", ".ml", ".zig", ".sql", ".r",
    ".jl", ".pl", ".pm", ".css", ".scss", ".less",
}
SKIP_DIRS = {
    "vendor", "vendored", "third_party", "third-party", "thirdparty",
    "external", "deps", "node_modules", "dist", "build", "out", "target",
    "generated", "gen", "__generated__", "docs", "doc", "documentation",
    "site", "website", "examples", "example", "cookbook", "fixtures",
    "testdata", "test_data", "snapshots", "__snapshots__", ".git",
}
MAX_BYTES = 512 * 1024


def counts(path):
    parts = path.lower().split("/")
    name = parts[-1]
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return False
    if ".min." in name or "generated" in name or ".pb." in name:
        return False
    if "lock" in name and not name.endswith((".py", ".go", ".rs")):
        return False
    return os.path.splitext(name)[1] in CODE_EXT


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", repo, *args], input=data,
                          capture_output=True, check=True).stdout


def measure(url, work):
    repo = os.path.join(work, "r.git")
    subprocess.run(["git", "clone", "-q", "--bare", "--single-branch", url,
                    repo], check=True)
    head = git(repo, "symbolic-ref", "HEAD").decode().strip()
    cache = {}
    rows = []
    for d in DATES:
        before = date.today().isoformat() + " 23:59" if d == "today" else d
        sha = git(repo, "rev-list", "-1", "--first-parent",
                  f"--before={before}", head).decode().strip()
        if not sha:
            rows.append([url, d, "", "", ""])
            continue
        blobs = []
        for line in git(repo, "ls-tree", "-r", "-l", "-z", sha).split(b"\0"):
            if not line:
                continue
            meta, path = line.split(b"\t", 1)
            _mode, kind, oid, size = meta.split()
            if (kind == b"blob" and size != b"-" and int(size) <= MAX_BYTES
                    and counts(path.decode("utf-8", "replace"))):
                blobs.append(oid.decode())
        todo = [b for b in set(blobs) if b not in cache]
        if todo:
            out = git(repo, "cat-file", "--batch",
                      data="\n".join(todo).encode() + b"\n")
            i = 0
            while i < len(out):
                nl = out.index(b"\n", i)
                oid, _kind, size = out[i:nl].split()
                body = out[nl + 1:nl + 1 + int(size)]
                cache[oid.decode()] = 0 if b"\0" in body[:8000] else (
                    body.count(b"\n") + (0 if body.endswith(b"\n") or not body
                                         else 1))
                i = nl + 1 + int(size) + 1
        rows.append([url, d, sha[:12], len(blobs),
                     sum(cache[b] for b in blobs)])
    return rows


def main(urls):
    w = csv.writer(sys.stdout)
    for url in urls:
        with tempfile.TemporaryDirectory() as work:
            w.writerows(measure(url, work))
        sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
