"""Stage 3: metrics, bootstrap CIs (PR-level and repo-clustered), size matching, SVG charts.

Stdlib only. Reads data/raw/enriched.jsonl and data/raw/listing/*.jsonl; writes
docs/study/results.json, docs/study/results-table.md, docs/study/*.svg and
data/raw/pr_metrics.jsonl.
"""
import json
import math
import os
import random
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import enrich  # noqa: E402

ROOT = os.path.join(HERE, "..", "..")
RAW = os.path.join(ROOT, "data", "raw")
DOCS = os.path.join(ROOT, "docs", "study")
BOOT = 3000
SEED = 7
CALIPER = 0.15  # log10 distance allowed when matching a human PR to an agent PR on size

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|testing|e2e|fixtures?)(/|$)|(^|/)test_[^/]*$|"
    r"_test\.[a-z]+$|\.(test|spec)\.[a-z]+$|Tests?\.[a-z]+$",
    re.I,
)
NONCODE_PATH = re.compile(
    r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|Cargo\.lock|poetry\.lock|"
    r"go\.sum|uv\.lock|Gemfile\.lock|composer\.lock)$|\.(snap|lock|svg|json|md|mdx|txt|csv|"
    r"yml|yaml|toml|png|jpg|po|pot|xlf|resx)$|(^|/)(dist|vendor|node_modules|"
    r"generated|__generated__|docs?|i18n|locales?|translations?)(/|$)|\.min\.|\.generated\.|"
    r"\.pb\.go$|_pb2",
    re.I,
)
SIZE_BINS = [(0, 10), (10, 30), (30, 100), (100, 300), (300, 1000), (1000, math.inf)]


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def revert_index():
    reverted = {}
    listing = os.path.join(RAW, "listing")
    for name in os.listdir(listing):
        if not name.endswith(".jsonl"):
            continue
        rows = load(os.path.join(listing, name))
        by_title = defaultdict(list)
        for r in rows:
            by_title[r["title"]].append(r)
        for r in rows:
            m = re.match(r'^Revert "(.+)"', r["title"])
            if not m:
                continue
            for orig in by_title.get(m.group(1), []):
                if orig["merged_at"] < r["merged_at"]:
                    reverted[(orig["repo"], orig["number"])] = r["number"]
    return reverted


def metrics(rec, reverted):
    add, dele = rec["additions"], rec["deletions"]
    total = add + dele
    files = rec["files"]
    trunc = rec["files_truncated"]
    test = [f for f in files if TEST_PATH.search(f["path"])]
    src = [f for f in files if not TEST_PATH.search(f["path"]) and not NONCODE_PATH.search(f["path"])]
    test_add = sum(f["additions"] for f in test)
    src_add = sum(f["additions"] for f in src)
    src_del = sum(f["deletions"] for f in src)
    return {
        "repo": rec["repo"], "number": rec["number"], "group": rec["group"],
        "merged_at": rec["merged_at"],
        "additions": add, "deletions": dele, "net": add - dele, "churn": total,
        "delete_ratio": dele / total if total else 0.0,
        "net_negative": 1.0 if dele > add else 0.0,
        "changed_files": rec["changed_files"],
        "files_truncated": trunc,
        "test_add_share": None if trunc else (test_add / add if add else 0.0),
        "src_net": None if trunc else src_add - src_del,
        "reverted": 1.0 if (rec["repo"], rec["number"]) in reverted else 0.0,
    }


def med(v):
    return statistics.median(v)


def mean(v):
    return sum(v) / len(v)


def ci(v):
    v = sorted(v)
    n = len(v)
    return [v[int(0.025 * n)], v[int(0.975 * n) - 1]]


def boot_pr(a, b, stat, rng, n=BOOT):
    """PR-level bootstrap: CIs for each group and for stat(a)-stat(b)."""
    ea, eb, ed = [], [], []
    for _ in range(n):
        x = stat(rng.choices(a, k=len(a)))
        y = stat(rng.choices(b, k=len(b)))
        ea.append(x)
        eb.append(y)
        ed.append(x - y)
    return [ci(ea), ci(eb), ci(ed)]


def boot_cluster_diff(rows, key, stat, rng, n=BOOT):
    """Repo-clustered bootstrap of stat(agent)-stat(human): resample repos, keep their PRs."""
    by_repo = defaultdict(lambda: ([], []))
    for m in rows:
        if m[key] is None:
            continue
        by_repo[m["repo"]][0 if m["group"] == "agent" else 1].append(m[key])
    repos = [r for r, (a, h) in by_repo.items() if a and h]
    diffs = []
    for _ in range(n):
        a, h = [], []
        for r in rng.choices(repos, k=len(repos)):
            a += by_repo[r][0]
            h += by_repo[r][1]
        diffs.append(stat(a) - stat(h))
    return ci(diffs), len(repos)


def summarize(label, key, rows, stat, rng):
    agent = [m[key] for m in rows if m["group"] == "agent" and m[key] is not None]
    human = [m[key] for m in rows if m["group"] == "human" and m[key] is not None]
    ca, ch, cd = boot_pr(agent, human, stat, rng)
    cc, nrep = boot_cluster_diff(rows, key, stat, rng)
    return {
        "metric": label, "key": key, "n_agent": len(agent), "n_human": len(human),
        "agent": stat(agent), "agent_ci95": ca, "human": stat(human), "human_ci95": ch,
        "diff": stat(agent) - stat(human), "diff_ci95_pr": cd,
        "diff_ci95_repo_cluster": cc, "repos_in_cluster": nrep,
    }


def size_bin_label(lo, hi):
    return f"{lo}-{hi if hi != math.inf else 'inf'}"


def size_bins(agent, human):
    out = []
    for lo, hi in SIZE_BINS:
        a = [m for m in agent if lo <= m["churn"] < hi]
        h = [m for m in human if lo <= m["churn"] < hi]
        row = {"bin": size_bin_label(lo, hi), "n_agent": len(a), "n_human": len(h)}
        if len(a) >= 5 and len(h) >= 5:
            row.update({
                "delete_ratio_agent": med([m["delete_ratio"] for m in a]),
                "delete_ratio_human": med([m["delete_ratio"] for m in h]),
                "net_agent": med([m["net"] for m in a]),
                "net_human": med([m["net"] for m in h]),
                "net_neg_agent": mean([m["net_negative"] for m in a]),
                "net_neg_human": mean([m["net_negative"] for m in h]),
            })
        else:
            row["note"] = "too few"
        out.append(row)
    return out


def matched_pairs(agent, human, rng):
    """Pair each agent PR with a same-repo human PR of nearly equal size (caliper on log10
    churn), nearest first, with replacement. Returns [(agent_m, human_m)]."""
    by_repo = defaultdict(list)
    for h in human:
        by_repo[h["repo"]].append(h)
    pairs = []
    for a in agent:
        if a["churn"] == 0:
            continue
        la = math.log10(a["churn"])
        cands = [(abs(math.log10(h["churn"]) - la), h) for h in by_repo.get(a["repo"], [])
                 if h["churn"] > 0]
        cands = [(d, h) for d, h in cands if d <= CALIPER]
        if cands:
            best = min(d for d, _ in cands)
            pairs.append((a, rng.choice([h for d, h in cands if d <= best + 1e-9])))
    return pairs


def matched_summary(pairs, rng):
    out = {"n_pairs": len(pairs), "repos": len({a["repo"] for a, _ in pairs})}
    if not pairs:
        return out
    for name, key, stat in [("delete_ratio", "delete_ratio", med), ("delete_ratio_mean", "delete_ratio", mean),
                            ("net_negative", "net_negative", mean), ("net", "net", med)]:
        d = [a[key] - h[key] for a, h in pairs]
        boots = [stat(rng.choices(d, k=len(d))) for _ in range(BOOT)]
        out[name] = {"agent": stat([a[key] for a, _ in pairs]), "human": stat([h[key] for _, h in pairs]),
                     "paired_diff": stat(d), "paired_diff_ci95": ci(boots)}
    for key in ["net", "delete_ratio"]:
        boots = []
        for _ in range(BOOT):
            s = rng.choices(pairs, k=len(pairs))
            boots.append(med([a[key] for a, _ in s]) - med([h[key] for _, h in s]))
        out[f"{key}_gap_of_medians"] = {
            "agent": med([a[key] for a, _ in pairs]), "human": med([h[key] for _, h in pairs]),
            "diff": med([a[key] for a, _ in pairs]) - med([h[key] for _, h in pairs]), "diff_ci95": ci(boots)}
    out["agent_median_churn"] = med([a["churn"] for a, _ in pairs])
    out["human_median_churn"] = med([h["churn"] for _, h in pairs])
    out["agent_median_net"] = med([a["net"] for a, _ in pairs])
    out["human_median_net"] = med([h["net"] for _, h in pairs])
    return out


def per_repo(rows, min_each=8):
    by = defaultdict(lambda: {"agent": [], "human": []})
    for m in rows:
        by[m["repo"]][m["group"]].append(m)
    out = []
    for repo, g in by.items():
        if len(g["agent"]) >= min_each and len(g["human"]) >= min_each:
            out.append({
                "repo": repo, "n_agent": len(g["agent"]), "n_human": len(g["human"]),
                "net_agent": med([m["net"] for m in g["agent"]]),
                "net_human": med([m["net"] for m in g["human"]]),
                "delete_ratio_agent": med([m["delete_ratio"] for m in g["agent"]]),
                "delete_ratio_human": med([m["delete_ratio"] for m in g["human"]]),
                "churn_agent": med([m["churn"] for m in g["agent"]]),
                "churn_human": med([m["churn"] for m in g["human"]]),
            })
    return sorted(out, key=lambda r: r["delete_ratio_agent"] - r["delete_ratio_human"])


# ---- charts -------------------------------------------------------------------

C_AGENT, C_HUMAN = "#c2410c", "#2563eb"


def svg_open(w, h, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="Helvetica,Arial,sans-serif" font-size="12">',
            f'<rect width="{w}" height="{h}" fill="white"/>',
            f'<text x="20" y="26" font-size="15" font-weight="bold" fill="#111">{title}</text>']


def write(path, parts):
    with open(path, "w") as f:
        f.write("\n".join(parts + ["</svg>"]))


def grid(parts, left, w, h, bottom, plot_h, top, fmt_tick):
    for i in range(5):
        v = top * i / 4
        y = h - bottom - v / top * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{w - 20}" y2="{y:.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#555">{fmt_tick(v)}</text>')


def legend(parts, x, y, labels):
    for label, col in labels:
        parts.append(f'<rect x="{x}" y="{y - 10}" width="10" height="10" fill="{col}"/>'
                     f'<text x="{x + 14}" y="{y}" fill="#222">{label}</text>')
        x += 14 + 7 * len(label) + 18


def chart_churn(path, agent, human):
    w, h, left, bottom = 680, 380, 56, 70
    parts = svg_open(w, h, "How big are the PRs? Share of PRs by lines changed")
    plot_h = h - bottom - 50
    shares = [(len([m for m in agent if lo <= m["churn"] < hi]) / len(agent),
               len([m for m in human if lo <= m["churn"] < hi]) / len(human)) for lo, hi in SIZE_BINS]
    top = math.ceil(max(max(s) for s in shares) * 25) / 25
    grid(parts, left, w, h, bottom, plot_h, top, lambda v: f"{v * 100:.0f}%")
    bw = (w - left - 20) / len(SIZE_BINS)
    for i, ((lo, hi), (sa, sh)) in enumerate(zip(SIZE_BINS, shares)):
        x0 = left + i * bw
        for j, (v, col) in enumerate([(sa, C_AGENT), (sh, C_HUMAN)]):
            bh = v / top * plot_h
            parts.append(f'<rect x="{x0 + 10 + j * (bw - 20) / 2:.1f}" y="{h - bottom - bh:.1f}" '
                         f'width="{(bw - 20) / 2 - 2:.1f}" height="{bh:.1f}" fill="{col}"/>')
        lab = f"{lo}+" if hi == math.inf else f"{lo}-{hi}"
        parts.append(f'<text x="{x0 + bw / 2:.1f}" y="{h - bottom + 16}" text-anchor="middle" fill="#333">{lab}</text>')
    ma, mh = med([m["churn"] for m in agent]), med([m["churn"] for m in human])
    parts.append(f'<text x="{left}" y="{h - 34}" fill="#333">lines changed per PR (adds + deletes). '
                 f'Median: agent {ma:.0f}, human {mh:.0f}</text>')
    legend(parts, left, h - 12, [(f"agent PRs (n={len(agent)})", C_AGENT), (f"human PRs (n={len(human)})", C_HUMAN)])
    write(path, parts)


def chart_bins(path, bins):
    usable = [r for r in bins if "note" not in r]
    w, h, left, bottom = 680, 380, 56, 70
    parts = svg_open(w, h, "Same size, same story? Median delete ratio per PR-size bin")
    plot_h = h - bottom - 50
    grid(parts, left, w, h, bottom, plot_h, 1.0, lambda v: f"{v:.2f}")
    bw = (w - left - 20) / max(len(usable), 1)
    for i, r in enumerate(usable):
        x0 = left + i * bw
        for j, (k, col) in enumerate([("delete_ratio_agent", C_AGENT), ("delete_ratio_human", C_HUMAN)]):
            bh = r[k] * plot_h
            bx = x0 + 12 + j * (bw - 24) / 2
            parts.append(f'<rect x="{bx:.1f}" y="{h - bottom - bh:.1f}" width="{(bw - 24) / 2 - 2:.1f}" '
                         f'height="{bh:.1f}" fill="{col}"/>')
            parts.append(f'<text x="{bx + (bw - 24) / 4 - 1:.1f}" y="{h - bottom - bh - 4:.1f}" '
                         f'text-anchor="middle" font-size="10" fill="#333">{r[k]:.2f}</text>')
        parts.append(f'<text x="{x0 + bw / 2:.1f}" y="{h - bottom + 16}" text-anchor="middle" fill="#333">{r["bin"]} lines</text>')
        parts.append(f'<text x="{x0 + bw / 2:.1f}" y="{h - bottom + 30}" text-anchor="middle" font-size="10" '
                     f'fill="#666">n={r["n_agent"]} / {r["n_human"]}</text>')
    legend(parts, left, h - 12, [("agent PRs", C_AGENT), ("human PRs", C_HUMAN)])
    parts.append(f'<text x="{left + 260}" y="{h - 12}" fill="#666">n = agent / human; bins need 5+ of each</text>')
    write(path, parts)


def chart_repos(path, rows):
    w = 680
    h = 130 + 24 * len(rows)
    parts = svg_open(w, h, "Per repo: median delete ratio, agent vs human PRs")
    left, right = 275, w - 40
    parts.append('<text x="20" y="46" fill="#555">repos with 8+ agent and 8+ human PRs. 0 = pure additions, 1 = pure deletions</text>')
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = left + tick * (right - left)
        parts.append(f'<line x1="{x:.1f}" y1="60" x2="{x:.1f}" y2="{h - 56}" stroke="#ddd"/>')
        parts.append(f'<text x="{x:.1f}" y="{h - 42}" text-anchor="middle" fill="#555">{tick:.2f}</text>')
    for i, r in enumerate(rows):
        y = 78 + i * 24
        xa = left + r["delete_ratio_agent"] * (right - left)
        xh = left + r["delete_ratio_human"] * (right - left)
        parts.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{xh:.1f}" y2="{y}" stroke="#999"/>')
        parts.append(f'<circle cx="{xa:.1f}" cy="{y}" r="5" fill="{C_AGENT}"/>')
        parts.append(f'<circle cx="{xh:.1f}" cy="{y}" r="5" fill="{C_HUMAN}"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" fill="#222">'
                     f'{r["repo"]} ({r["n_agent"]}/{r["n_human"]})</text>')
    legend(parts, left, h - 14, [("agent", C_AGENT), ("human", C_HUMAN)])
    parts.append(f'<text x="20" y="{h - 14}" fill="#666">(n agent / n human)</text>')
    write(path, parts)


# ---- main ---------------------------------------------------------------------

def fmt(x, d=2):
    if abs(x) >= 100:
        d = 0
    elif abs(x) >= 10:
        d = 1
    return f"{x:.{d}f}"


def table(res):
    lines = ["| metric | agent PRs | human PRs | agent - human | 95% CI, PR bootstrap | 95% CI, repo-clustered |",
             "|---|---|---|---|---|---|"]
    for m in res["metrics"]:
        lines.append(
            f"| {m['metric']} | {fmt(m['agent'])} [{fmt(m['agent_ci95'][0])}, {fmt(m['agent_ci95'][1])}] "
            f"| {fmt(m['human'])} [{fmt(m['human_ci95'][0])}, {fmt(m['human_ci95'][1])}] "
            f"| {fmt(m['diff'])} | [{fmt(m['diff_ci95_pr'][0])}, {fmt(m['diff_ci95_pr'][1])}] "
            f"| [{fmt(m['diff_ci95_repo_cluster'][0])}, {fmt(m['diff_ci95_repo_cluster'][1])}] |")
    return "\n".join(lines)


def main():
    os.makedirs(DOCS, exist_ok=True)
    rng = random.Random(SEED)
    picks = {(r["repo"], r["number"]) for _, r in enrich.select(enrich.load_listing())}
    seen, enriched = set(), []
    for r in load(os.path.join(RAW, "enriched.jsonl")):
        k = (r["repo"], r["number"])
        if k in picks and k not in seen:
            seen.add(k)
            enriched.append(r)
    reverted = revert_index()
    rows = [metrics(r, reverted) for r in enriched
            if r["group"] == "agent" or not r["commit_claude_trailer"]]
    agent = [m for m in rows if m["group"] == "agent"]
    human = [m for m in rows if m["group"] == "human"]
    repos_agent = sorted({m["repo"] for m in agent})

    listing = enrich.load_listing()
    res = {
        "population": {
            "repos_listed": len({r["repo"] for r in listing}),
            "merged_2026_prs_listed": len(listing),
            "agent_flagged_prs": sum(1 for r in listing if enrich.is_agent_row(r)),
            "human_pool_prs": sum(1 for r in listing if not enrich.is_agent_row(r) and r["user_type"] == "User"),
            "bot_authored_unflagged_prs": sum(1 for r in listing if not enrich.is_agent_row(r) and r["user_type"] != "User"),
        },
        "n_agent": len(agent), "n_human": len(human),
        "repos_with_agent_prs": len(repos_agent),
        "repos_with_both": len({m["repo"] for m in agent} & {m["repo"] for m in human}),
        "agent_prs_by_repo": {r: sum(1 for m in agent if m["repo"] == r) for r in repos_agent},
        "human_dropped_commit_trailer": sum(1 for r in enriched if r["group"] == "human" and r["commit_claude_trailer"]),
        "label_sources": {k: sum(1 for r in enriched if r["group"] == "agent" and r[k])
                          for k in ["body_claude_footer", "body_claude_trailer", "body_copilot",
                                    "agent_bot_login", "commit_claude_trailer"]},
        "files_truncated": {"agent": sum(1 for m in agent if m["files_truncated"]),
                            "human": sum(1 for m in human if m["files_truncated"])},
        "metrics": [],
    }
    specs = [
        ("lines changed (adds + deletes)", "churn", med),
        ("additions", "additions", med),
        ("deletions", "deletions", med),
        ("net lines (adds - deletes)", "net", med),
        ("delete ratio (deletes / lines changed)", "delete_ratio", med),
        ("share of PRs that delete more than they add", "net_negative", mean),
        ("files changed", "changed_files", med),
        ("net lines in non-test source files", "src_net", med),
        ("test share of additions", "test_add_share", med),
        ("share of PRs later reverted", "reverted", mean),
    ]
    for label, key, stat in specs:
        res["metrics"].append(summarize(label, key, rows, stat, rng))

    res["size_bins"] = size_bins(agent, human)
    res["size_matched"] = matched_summary(matched_pairs(agent, human, rng), rng)
    res["per_repo"] = per_repo(rows)
    lang = {}
    for line in open(os.path.join(RAW, "repos.jsonl")):
        r = json.loads(line)
        lang[r["fullName"]] = r.get("language") or r.get("picked_for")
    res["agent_prs_by_language"] = {}
    for m in agent:
        res["agent_prs_by_language"][lang.get(m["repo"], "?")] = res["agent_prs_by_language"].get(lang.get(m["repo"], "?"), 0) + 1
    res["repos_by_language"] = {}
    for r in repos_agent:
        res["repos_by_language"][lang.get(r, "?")] = res["repos_by_language"].get(lang.get(r, "?"), 0) + 1

    big = sorted(res["agent_prs_by_repo"], key=lambda r: -res["agent_prs_by_repo"][r])[:4]
    res["sensitivity"] = {}
    for name, keep in [
        ("without_top4_agent_repos", lambda m: m["repo"] not in big),
        ("merged_june_onward", lambda m: m["merged_at"] >= "2026-06-01"),
        ("merged_before_june", lambda m: m["merged_at"] < "2026-06-01"),
    ]:
        sub = [m for m in rows if keep(m)]
        sa = [m for m in sub if m["group"] == "agent"]
        sh = [m for m in sub if m["group"] == "human"]
        entry = {"n_agent": len(sa), "n_human": len(sh)}
        if len(sa) >= 20 and len(sh) >= 20:
            for key in ["net", "delete_ratio", "churn"]:
                a = [m[key] for m in sa]
                hh = [m[key] for m in sh]
                entry[key] = {"agent": med(a), "human": med(hh),
                              "diff_ci95_pr": boot_pr(a, hh, med, rng)[2]}
            entry["size_matched"] = matched_summary(matched_pairs(sa, sh, rng), rng)
        res["sensitivity"][name] = entry
    res["sensitivity"]["top4_repos"] = big

    with open(os.path.join(DOCS, "results.json"), "w") as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(DOCS, "results-table.md"), "w") as f:
        f.write(table(res) + "\n")
    with open(os.path.join(RAW, "pr_metrics.jsonl"), "w") as f:
        for m in rows:
            f.write(json.dumps(m) + "\n")
    chart_churn(os.path.join(DOCS, "pr-size-distribution.svg"), agent, human)
    chart_bins(os.path.join(DOCS, "delete-ratio-by-size.svg"), res["size_bins"])
    if res["per_repo"]:
        chart_repos(os.path.join(DOCS, "delete-ratio-by-repo.svg"), res["per_repo"])
    print(table(res))
    keys = ["n_agent", "n_human", "repos_with_agent_prs", "repos_with_both", "label_sources",
            "files_truncated", "size_bins", "size_matched", "sensitivity", "agent_prs_by_repo"]
    print(json.dumps({k: res[k] for k in keys}, indent=1)[:9000])


if __name__ == "__main__":
    main()
