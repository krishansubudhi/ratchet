"""Stage 0: pick the study population of popular, active public repos.

Per language, take the most-starred non-fork, non-archived repos that were pushed
to recently. Writes data/raw/repos.jsonl. Resumable: rewrites only if absent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gh import _run, SEARCH_PACE  # noqa: E402
import time  # noqa: E402

RAW = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
OUT = os.path.join(RAW, "repos.jsonl")
LANGUAGES = ["python", "javascript", "typescript", "go", "rust", "java",
             "csharp", "ruby", "php", "cpp", "kotlin", "swift"]
PER_LANGUAGE = 10


def main():
    os.makedirs(RAW, exist_ok=True)
    if os.path.exists(OUT):
        print("repos.jsonl exists; delete it to re-pick")
        return
    rows = []
    for lang in LANGUAGES:
        out = _run([
            "search", "repos", "--language", lang, "--stars", ">=1000",
            "--updated", ">=2026-08-01", "--sort", "stars", "--limit", "20",
            "--json", "fullName,stargazersCount,language,isFork,isArchived,updatedAt",
        ])
        picked = [r for r in json.loads(out) if not r["isFork"] and not r["isArchived"]]
        picked = picked[:PER_LANGUAGE]
        for r in picked:
            r["picked_for"] = lang
        rows += picked
        print(lang, [r["fullName"] for r in picked], flush=True)
        time.sleep(SEARCH_PACE)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} repos")


if __name__ == "__main__":
    main()
