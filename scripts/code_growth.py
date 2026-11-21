#!/usr/bin/env python3
"""Count source lines in a git repo at fixed dates. Stdlib + git only.

    python scripts/code_growth.py https://github.com/pallets/flask [more urls]
    python scripts/code_growth.py --svg docs/code-growth-data.csv > chart.svg

Prints CSV rows: repo,date,commit,files,lines (lines blank if the repo had no commit
before that date), from a bare clone of the default branch. What counts: counts() below,
explained in the Method section of docs/code-growth.md. Blank lines and comments count.
"""

import csv
import os
import subprocess
import sys
import tempfile
from datetime import date

DATES = ["2023-01-01", "2024-01-01", "2025-01-01", "2026-01-01", "today"]
CODE_EXT = set(""".py .pyi .js .jsx .mjs .cjs .ts .tsx .mts .cts .go .rs .c .h .cc .cpp .cxx .hpp
    .hh .java .kt .kts .scala .swift .m .mm .rb .php .cs .fs .lua .sh .bash .zsh .ps1 .vue .svelte
    .dart .ex .exs .erl .hs .ml .zig .sql .r .jl .pl .pm .css .scss .less""".split())
SKIP_DIRS = set("""vendor vendored third_party third-party thirdparty external deps node_modules
    dist build out target generated gen __generated__ docs doc documentation site website examples
    example cookbook fixtures testdata test_data snapshots __snapshots__ .git""".split())
AI = set("aider litellm cline continue crewAI gemini-cli langchain ollama open-webui codex opencode ai".split())
MAX_BYTES = 512 * 1024


def counts(path):
    *dirs, name = path.lower().split("/")
    return not (any(p in SKIP_DIRS for p in dirs) or ".min." in name or "generated" in name
                or ".pb." in name or ("lock" in name and not name.endswith((".py", ".go", ".rs")))
                ) and os.path.splitext(name)[1] in CODE_EXT


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", repo, *args], input=data,
                          capture_output=True, check=True).stdout


def measure(url, work):
    repo = os.path.join(work, "r.git")
    subprocess.run(["git", "clone", "-q", "--bare", "--single-branch", url, repo], check=True)
    head = git(repo, "symbolic-ref", "HEAD").decode().strip()
    cache, rows = {}, []
    for d in DATES:
        before = date.today().isoformat() + " 23:59" if d == "today" else d
        sha = git(repo, "rev-list", "-1", "--first-parent",
                  f"--before={before}", head).decode().strip()
        if not sha:
            rows.append([url, d, "", "", ""])
            continue
        tree = [(m.split(), p) for m, _, p in (line.partition(b"\t") for line in
                git(repo, "ls-tree", "-r", "-l", "-z", sha).split(b"\0") if line)]
        blobs = [m[2].decode() for m, p in tree if m[1] == b"blob" and m[3] != b"-"
                 and int(m[3]) <= MAX_BYTES and counts(p.decode("utf-8", "replace"))]
        todo = [b for b in set(blobs) if b not in cache]
        if todo:
            out, i = git(repo, "cat-file", "--batch", data="\n".join(todo).encode() + b"\n"), 0
            while i < len(out):
                nl = out.index(b"\n", i)
                oid, _kind, size = out[i:nl].split()
                body = out[nl + 1:nl + 1 + int(size)]
                cache[oid.decode()] = 0 if b"\0" in body[:8000] else (
                    body.count(b"\n") + int(bool(body) and not body.endswith(b"\n")))
                i = nl + int(size) + 2
        rows.append([url, d, sha[:12], len(blobs), sum(cache[b] for b in blobs)])
    return rows


def svg(path):
    """The report's chart, indexed to 2025-01-01 = 100: end labels stack 15px apart from the
    bottom up, above the x axis; the legend sits top left, clear of them."""
    rows, x, out = {}, lambda i: f"{60 + 265 * i}.0", [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 420" font-family="sans-serif" '
        'font-size="12">\n<rect width="760" height="420" fill="white"/>\n<text x="60" y="18" '
        'font-size="14">Source lines, indexed to 2025-01-01 = 100</text>\n<rect x="70" y="36" width='
        '"12" height="3" fill="#d9480f"/><text x="86" y="41">AI tools</text>\n<rect x="70" y="54" '
        'width="12" height="3" fill="#1c7ed6"/><text x="86" y="59">control</text>']
    for r in csv.DictReader(open(path)):
        rows.setdefault(r["repo"].rsplit("/", 1)[1], {})[r["date"]] = r["lines"]
    out += [f'<line x1="60" x2="590" y1="{370 - g / 10}" y2="{370 - g / 10}" stroke="#ddd"/><text '
            f'x="54" y="{374 - g / 10}" text-anchor="end" fill="#555">{g}</text>'
            for g in range(0, 3401, 200)]
    out += [f'<text x="{x(i)}" y="390" text-anchor="middle" fill="#555">{d}</text>'
            for i, d in enumerate(DATES[2:4] + ["today"])]
    ends = sorted((100 * int(d[DATES[4]]) / int(d[DATES[2]]), n) for n, d in rows.items() if d[DATES[2]])
    for end, n in ends:
        pts = " ".join(f"{x(i)},{370 - 10 * int(rows[n][k]) / int(rows[n][DATES[2]]):.1f}"
                       for i, k in enumerate(DATES[2:]))
        out.append(f'<polyline fill="none" stroke="{"#d9480f" if n in AI else "#1c7ed6"}" '
                   f'stroke-width="2" opacity="0.8" points="{pts}"/>')
    y = 385
    for end, n in [e for e in ends if e[0] >= 200]:
        y = min(374 - end / 10, y - 15)
        out.append(f'<text x="596.0" y="{y:.1f}" fill="#333">{n} {round(end)}</text>')
    print("\n".join(out + ["</svg>"]))


def main(urls):
    if urls[:1] == ["--svg"]:
        return svg(urls[1])
    w = csv.writer(sys.stdout)
    for url in urls:
        with tempfile.TemporaryDirectory() as work:
            w.writerows(measure(url, work))
        sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
