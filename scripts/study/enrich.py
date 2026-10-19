"""Stage 2: pull size, file and commit detail for agent PRs and a repo-matched human sample.

Agent group: every listed PR with an agent signal (PR body footer, Copilot marker,
or agent bot author). Human group: PRs by human accounts with no body or bot
signal, sampled per repo in proportion to that repo's agent count, then dropped
if any commit message carries an agent trailer (catches agents whose footer is
only in commits). Both groups go through GraphQL in batches.

Writes data/raw/enriched.jsonl (resumable: keys already present are skipped).
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gh import graphql  # noqa: E402

RAW = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
LISTING = os.path.join(RAW, "listing")
OUT = os.path.join(RAW, "enriched.jsonl")
BATCH = 8
SEED = 20260914

sys.path.insert(0, os.path.dirname(__file__))
from list_prs import CLAUDE_TRAILER, EXCLUDE_NAME  # noqa: E402


def load_listing():
    rows = []
    for name in sorted(os.listdir(LISTING)):
        if name.endswith(".jsonl"):
            with open(os.path.join(LISTING, name)) as f:
                rows += [json.loads(line) for line in f]
    return rows


def is_agent_row(r):
    return bool(r["agent_bot_login"] or r["body_claude_footer"]
                or r["body_claude_trailer"] or r["body_copilot"])


AGENT_CAP_PER_REPO = 40
HUMAN_PER_AGENT = 2
HUMAN_MIN_PER_REPO = 10


def select(rows):
    """Cap agent PRs per repo (so n8n/AutoGPT cannot dominate); for each sampled
    agent PR draw human PRs from the same repo and merge month (fallback: repo)."""
    by_repo = {}
    for r in rows:
        by_repo.setdefault(r["repo"], {"agent": [], "human": []})
        if is_agent_row(r):
            by_repo[r["repo"]]["agent"].append(r)
        elif r["user_type"] == "User":
            by_repo[r["repo"]]["human"].append(r)
    picks = []
    for repo, g in sorted(by_repo.items()):
        if not g["agent"] or EXCLUDE_NAME.search(repo):
            continue
        rng = random.Random(f"{SEED}/{repo}")
        agents = rng.sample(g["agent"], min(len(g["agent"]), AGENT_CAP_PER_REPO))
        picks += [("agent", r) for r in agents]
        pool_month = {}
        for h in g["human"]:
            pool_month.setdefault(h["merged_at"][:7], []).append(h)
        chosen = set()
        want = max(HUMAN_PER_AGENT * len(agents), HUMAN_MIN_PER_REPO)
        for a in agents:
            for _ in range(HUMAN_PER_AGENT):
                pool = [h for h in pool_month.get(a["merged_at"][:7], [])
                        if h["number"] not in chosen]
                if not pool:
                    pool = [h for h in g["human"] if h["number"] not in chosen]
                if not pool:
                    break
                h = rng.choice(pool)
                chosen.add(h["number"])
        while len(chosen) < min(want, len(g["human"])):
            pool = [h for h in g["human"] if h["number"] not in chosen]
            chosen.add(rng.choice(pool)["number"])
        picks += [("human", h) for h in g["human"] if h["number"] in chosen]
    return picks


FIELDS = """
number additions deletions changedFiles mergedAt createdAt
author { login }
commits(first: 100) { totalCount nodes { commit { message } } }
files(first: 100) { nodes { path additions deletions } }
"""


def build_query(batch):
    parts = []
    for i, (owner, name, number) in enumerate(batch):
        parts.append(
            f'r{i}: repository(owner: "{owner}", name: "{name}") '
            f"{{ p: pullRequest(number: {number}) {{ {FIELDS} }} }}"
        )
    return "query { " + " ".join(parts) + " }"


def main():
    picks = select(load_listing())
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            done = {(json.loads(l)["repo"], json.loads(l)["number"]) for l in f}
    todo = [(g, r) for g, r in picks if (r["repo"], r["number"]) not in done]
    print(f"picks={len(picks)} todo={len(todo)}", flush=True)
    with open(OUT, "a") as out:
        for start in range(0, len(todo), BATCH):
            chunk = todo[start:start + BATCH]
            specs = []
            for _, r in chunk:
                owner, name = r["repo"].split("/")
                specs.append((owner, name, r["number"]))
            try:
                res = graphql(build_query(specs))
                data = res["data"]
            except (RuntimeError, KeyError) as e:
                print("batch failed, skipping:", str(e)[:200], flush=True)
                continue
            for i, (group, r) in enumerate(chunk):
                pr = (data.get(f"r{i}") or {}).get("p")
                if pr is None:
                    continue
                msgs = [n["commit"]["message"] for n in pr["commits"]["nodes"]]
                trailer = any(CLAUDE_TRAILER.search(m) for m in msgs)
                rec = {
                    "group": group,
                    "repo": r["repo"],
                    "number": r["number"],
                    "title": r["title"],
                    "merged_at": r["merged_at"],
                    "created_at": r["created_at"],
                    "user_login": r["user_login"],
                    "agent_bot_login": r["agent_bot_login"],
                    "body_claude_footer": r["body_claude_footer"],
                    "body_claude_trailer": r["body_claude_trailer"],
                    "body_copilot": r["body_copilot"],
                    "commit_claude_trailer": trailer,
                    "additions": pr["additions"],
                    "deletions": pr["deletions"],
                    "changed_files": pr["changedFiles"],
                    "commit_count": pr["commits"]["totalCount"],
                    "commits_truncated": pr["commits"]["totalCount"] > len(msgs),
                    "files": [{"path": f["path"], "additions": f["additions"],
                               "deletions": f["deletions"]}
                              for f in pr["files"]["nodes"]],
                    "files_truncated": pr["changedFiles"] > len(pr["files"]["nodes"]),
                }
                out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"{start + len(chunk)}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
