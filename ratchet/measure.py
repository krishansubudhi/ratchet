# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""Finding files, counting lines, and spotting seams. No policy lives here."""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from typing import Iterable, Mapping

CODE_EXTS = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs",
    ".java", ".kt", ".kts", ".scala", ".rb", ".php", ".cs", ".c", ".h", ".cc",
    ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm", ".swift", ".dart", ".lua",
    ".ex", ".exs", ".erl", ".clj", ".hs", ".ml", ".r", ".jl", ".sh", ".bash",
    ".zsh", ".ps1", ".sql", ".vue", ".svelte", ".zig", ".nim",
}

TEST_GLOBS = [
    "**/test_*", "**/*_test.*", "**/*_tests.*", "**/*.test.*", "**/*.spec.*",
    "**/tests/**", "**/test/**", "**/testing/**", "**/__tests__/**", "**/spec/**",
]

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env",
             "__pycache__", "dist", "build", "target", "vendor", ".tox",
             ".mypy_cache", ".pytest_cache", ".ruff_cache"}


@lru_cache(maxsize=512)
def _regex(glob: str) -> re.Pattern[str]:
    """A gitignore-flavoured glob: `**/` is zero or more directories, `*`
    stays inside one path segment, `?` is one character."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


def matches(path: str, globs: Iterable[str]) -> bool:
    return any(_regex(g).match(path) for g in globs)


def git(root: str, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", root, *args], capture_output=True,
                          text=True, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or "git %s failed" % args[0])
    return done.stdout if done.returncode == 0 else ""


def is_git(root: str) -> bool:
    return git(root, "rev-parse", "--is-inside-work-tree", check=False).strip() == "true"


def list_files(root: str) -> list[str]:
    """Every file a reviewer would see: tracked plus untracked-but-not-ignored
    under git, otherwise a walk that skips the usual generated directories."""
    if is_git(root):
        out = git(root, "ls-files", "-z", "--cached", "--others",
                  "--exclude-standard")
        return sorted({p for p in out.split("\0")
                       if p and os.path.isfile(os.path.join(root, p))})
    found = []
    for here, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            found.append(os.path.relpath(os.path.join(here, name), root)
                         .replace(os.sep, "/"))
    return sorted(found)


def count_text(data: bytes) -> int:
    """Non-blank lines. Blank lines are free, so nobody games the budget by
    deleting whitespace or pays for a formatter's taste. Binary counts zero."""
    if b"\0" in data[:8192]:
        return 0
    return sum(1 for line in data.decode("utf-8", "replace").splitlines()
               if line.strip())


def count_file(root: str, path: str) -> int:
    try:
        with open(os.path.join(root, path), "rb") as fh:
            return count_text(fh.read())
    except OSError:
        return 0


def classify(paths: Iterable[str], groups: Mapping[str, Mapping[str, list[str]]]
             ) -> dict[str, str]:
    """path -> group: the first group, in config order, whose `extensions`
    (if given) and `include` globs match and whose `exclude` globs do not."""
    out = {}
    for path in paths:
        for name, spec in groups.items():
            exts = spec.get("extensions")
            if exts and os.path.splitext(path)[1].lower() not in exts:
                continue
            if matches(path, spec.get("include", [])) and not matches(
                    path, spec.get("exclude", [])):
                out[path] = name
                break
    return out


def measure(root: str, groups: Mapping[str, Mapping[str, list[str]]]
            ) -> dict[str, dict[str, int]]:
    """group -> {path: lines} for the working tree."""
    out: dict[str, dict[str, int]] = {g: {} for g in groups}
    for path, group in classify(list_files(root), groups).items():
        out[group][path] = count_file(root, path)
    return out


def changed_since(root: str, ref: str) -> dict[str, int]:
    """path -> line count at `ref`, for every path that differs from it in
    the working tree (new files map to 0). Empty outside git."""
    if not is_git(root):
        return {}
    git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    names = git(root, "diff", "-z", "--name-only", "--no-renames", ref).split("\0")
    names += git(root, "ls-files", "-z", "--others", "--exclude-standard").split("\0")
    out = {}
    for path in {n for n in names if n}:
        blob = subprocess.run(["git", "-C", root, "show", "%s:%s" % (ref, path)],
                              capture_output=True, check=False)
        out[path] = count_text(blob.stdout) if blob.returncode == 0 else 0
    return out


def show(root: str, ref: str, path: str) -> str | None:
    """A file's contents at `ref`, or None if it did not exist there."""
    done = subprocess.run(["git", "-C", root, "show", "%s:%s" % (ref, path)],
                          capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else None


SEAM = re.compile(r"(?:export\s+)?(?:default\s+)?(?:pub(?:\(\w+\))?\s+)?"
                  r"(?:async\s+)?(def|class|function|func|fn|impl|interface|"
                  r"struct|enum|trait|type|module|object)\b\s*([\w.$]*)")


def seams(text: str) -> list[tuple[int, str]]:
    """Top-level definitions, as (1-based line, label): the places a file can
    be cut in two without cutting through anything. Decorators and attributes
    directly above a definition move with it."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if not line or line[0].isspace():
            continue
        hit = SEAM.match(line)
        if not hit:
            continue
        start = i
        while start > 0 and lines[start - 1].startswith(("@", "#[")):
            start -= 1
        out.append((start + 1, ("%s %s" % hit.groups()).strip()))
    return out


def best_seams(text: str, limit: int = 3) -> list[tuple[int, str]]:
    """The seams nearest the middle: a cut there leaves two files of similar
    size, both under the limit if any cut can."""
    found = seams(text)[1:]   # the first definition is not a cut
    middle = len(text.splitlines()) / 2
    return sorted(sorted(found, key=lambda s: abs(s[0] - middle))[:limit])
