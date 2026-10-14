"""Stage 1: list every merged 2026 PR in each study repo (REST, paginated).

Writes data/raw/listing/<owner>__<repo>.jsonl, one row per merged PR, with
body-level agent signals as flags (PR bodies are not stored). Pages are walked
newest-updated first and the walk stops once a page is entirely before 2026.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gh import api_json  # noqa: E402

RAW = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
LISTING = os.path.join(RAW, "listing")
YEAR_START = "2026-01-01"
MAX_PAGES = 60

EXCLUDE_NAME = re.compile(
    r"awesome|free-programming|system-design|developer-roadmap|hello-algo|"
    r"public-apis|SecLists|JavaGuide|design-patterns|ECC|ponytail|deepseek-harness|"
    r"tutorial|learning|interview|roadmap|cheat|handbook|book|(^|[/-])course|-list|hello-",
    re.I,
)

CLAUDE_FOOTER = re.compile(r"Generated with \[?Claude Code", re.I)
CLAUDE_TRAILER = re.compile(r"Co-Authored-By:\s*Claude", re.I)
COPILOT_MARKER = re.compile(
    r"COPILOT CODING AGENT|created as a result of the following prompt", re.I
)
AGENT_BOT_LOGINS = re.compile(
    r"^(copilot|copilot-swe-agent\[bot\]|devin-ai-integration\[bot\]|"
    r"google-labs-jules\[bot\]|codex\[bot\])$",
    re.I,
)
REVERT_TITLE = re.compile(r'^Revert "(.+)"$')


def body_flags(body):
    body = body or ""
    return {
        "body_claude_footer": bool(CLAUDE_FOOTER.search(body)),
        "body_claude_trailer": bool(CLAUDE_TRAILER.search(body)),
        "body_copilot": bool(COPILOT_MARKER.search(body)),
    }


def list_repo(full):
    owner, name = full.split("/")
    rows = []
    page = 1
    while True:
        batch = api_json(
            f"repos/{owner}/{name}/pulls?state=closed&sort=updated"
            f"&direction=desc&per_page=100&page={page}"
        )
        if not batch:
            break
        for pr in batch:
            if not pr.get("merged_at"):
                continue
            if pr["merged_at"] < YEAR_START:
                continue
            login = (pr.get("user") or {}).get("login") or ""
            row = {
                "repo": full,
                "number": pr["number"],
                "title": pr["title"],
                "created_at": pr["created_at"],
                "merged_at": pr["merged_at"],
                "user_login": login,
                "user_type": (pr.get("user") or {}).get("type"),
                "agent_bot_login": bool(AGENT_BOT_LOGINS.match(login)),
                "base_ref": pr["base"]["ref"],
                "draft": pr.get("draft", False),
                "body_len": len(pr.get("body") or ""),
            }
            row.update(body_flags(pr.get("body")))
            rows.append(row)
        if batch[-1]["updated_at"] < YEAR_START:
            break
        if page >= MAX_PAGES:
            return rows, page, True
        page += 1
    return rows, page, False


def main():
    os.makedirs(LISTING, exist_ok=True)
    repos = [json.loads(line) for line in open(os.path.join(RAW, "repos.jsonl"))]
    order = list(reversed(repos)) if os.environ.get("REVERSE") else repos
    for r in order:
        full = r["fullName"]
        if EXCLUDE_NAME.search(full):
            print("excluded (non-code list/docs repo):", full, flush=True)
            continue
        path = os.path.join(LISTING, full.replace("/", "__") + ".jsonl")
        if os.path.exists(path):
            continue
        try:
            rows, pages, capped = list_repo(full)
        except RuntimeError as e:
            print("skipped (unavailable):", full, str(e)[:80], flush=True)
            continue
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        os.replace(tmp, path)
        agents = sum(1 for x in rows if x["agent_bot_login"] or x["body_claude_footer"]
                     or x["body_claude_trailer"] or x["body_copilot"])
        print(f"{full}: {len(rows)} merged 2026 PRs, {agents} agent-flagged, {pages} pages, capped={capped}",
              flush=True)


if __name__ == "__main__":
    main()
