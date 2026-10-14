"""Thin, rate-limit-aware wrappers around the gh CLI. Stdlib only."""
import json
import re
import subprocess
import time

SEARCH_PACE = 2.5
_last_search = [0.0]


def _run(args, retries=6):
    for attempt in range(retries):
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
        if proc.returncode == 0:
            return proc.stdout
        err = proc.stderr + proc.stdout
        if "rate limit" in err.lower() or "HTTP 403" in err or "HTTP 429" in err:
            wait = 90 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"gh {' '.join(args)[:120]} failed: {err[:400]}")
    raise RuntimeError("gh: retries exhausted")


def search_prs(query, limit=1000):
    gap = SEARCH_PACE - (time.time() - _last_search[0])
    if gap > 0:
        time.sleep(gap)
    _last_search[0] = time.time()
    out = _run([
        "search", "prs", query, "--limit", str(limit),
        "--json", "number,title,body,author,repository,createdAt,closedAt,url",
    ])
    return json.loads(out)


def api(path, paginate=False, jq=None):
    args = ["api", path]
    if paginate:
        args.append("--paginate")
    if jq:
        args += ["--jq", jq]
    return _run(args)


_BAD_UNICODE_ESCAPE = re.compile(r"(?<!\\)((?:\\\\)*)\\u(?![0-9a-fA-F]{4})")


def api_json(path):
    raw = api(path)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = _BAD_UNICODE_ESCAPE.sub(lambda m: m.group(1) + "\\\\u", raw)
        return json.loads(fixed)


def graphql(query):
    return json.loads(_run(["api", "graphql", "-f", f"query={query}"]))
