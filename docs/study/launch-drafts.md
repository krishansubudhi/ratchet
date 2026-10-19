# Launch drafts (DRAFT ONLY, nothing here has been posted)

Numbers come from `agent-pr-bloat.md`. Re-check them against `results.json` before posting anything. The result is modest and the copy below is written to match: do not upgrade it to "agents bloat codebases" or "agents are fine".

## Show HN

Show HN is for something people can try, so the study and the tool want two different posts.

**Option A: the study (plain HN submission, not "Show HN")**

Title (pick one, under 80 characters):

1. `Do AI coding agents bloat codebases? Data from 3,211 merged PRs in 68 repos`
2. `Agent PRs net ~10 more lines than size-matched human PRs (1,085 vs 2,126, 68 repos)`
3. `I compared 1,085 AI-agent PRs with 2,126 human ones in 68 big repos`

URL: the repo's `docs/study/agent-pr-bloat.md` on the `study` branch (or wherever it ends up).

**Option B: the tool (a real Show HN, post separately and later)**

Title: `Show HN: Ratchet, a code-size budget that only goes down (agents need a human grant to grow it)`

URL: https://github.com/krishansubudhi/ratchet

### First comment (for Option A)

> Author here. I wanted to know whether the "agents bloat codebases" claim holds up outside anecdotes, so I pulled every merged 2026 PR from 101 popular open-source repos (≥1k stars, 12 languages) and compared PRs that carry a solid agent signal (a "Generated with Claude Code" footer, a Claude co-author trailer, or a Copilot/Devin/Codex/Jules account) with human PRs from the same repos and merge months.
>
> Result: small, consistent, not dramatic. Median net lines per PR: +58 for agents vs +35 for humans, but about half of that gap is just agents doing bigger changes. Matched on repo and size (993 pairs, median 95 vs 94 lines changed), an agent PR nets about 10 more lines (56 vs 46, 95% CI +3 to +18) and deletes a smaller share of what it touches (median delete ratio 0.100 vs 0.143). The sign held when I dropped the four most agent-heavy repos and when I split by period. In 24 of the 34 repos with enough data, agents delete a smaller share than humans; in the other 10 they delete more.
>
> Things I'd poke at first:
> - Detection bias. Agent use without a footer is invisible, so the human group is contaminated, which pushes toward "no difference". 177 of the 2,303 sampled "human" PRs turned out to have a Claude commit trailer and I dropped them; I can't see the ones with no trace.
> - It's mostly Claude Code: 835 of the 1,085 agent PRs. Nothing here speaks for Cursor or Aider users who leave no footer.
> - Merged PRs only, and PR size is not codebase size. Whether the extra lines survive, get deleted later, or leave dead code is a different (better) study.
> - Means disagree with medians: mean net lines per PR is about equal (316 vs 307), because a few huge PRs in each group dominate. The tails are where the interesting stuff probably is, and I can't separate bloat from legitimate big refactors there.
>
> Everything is reproducible: stdlib Python, `gh`, the raw listings are committed as a tarball, sampling is seeded. I'd especially like to hear about better ways to detect agent PRs without footers, or a cleaner size-matching design than "nearest same-repo PR within a factor of 1.4".

## X thread

1/ Do AI coding agents bloat codebases? I looked at 3,211 merged 2026 PRs in 68 popular open-source repos: 1,085 with a clear agent signal, 2,126 human controls from the same repos and months. Short answer: a little, and less than the discourse suggests. [chart: pr-size-distribution.png]

2/ How I split them: agent = "Generated with Claude Code" footer, a Claude co-author trailer, or a Copilot/Devin/Codex/Jules account. Human = same repo, same merge month, no signal. 12 languages, max 40 agent PRs per repo so n8n and AutoGPT can't run the table.

3/ Raw medians: the agent PR nets +58 lines, the human PR +35. Agent PRs also delete a smaller share of what they touch (delete ratio 0.10 vs 0.16).

4/ But agent PRs are bigger: median 98 lines changed vs 78. Fair question: is that the whole story?

5/ So I matched each agent PR to a human PR from the same repo of nearly the same size (993 pairs, 95 vs 94 lines). The gap roughly halves: +10 net lines (95% CI +3 to +18), delete ratio 0.100 vs 0.143. Smaller, but it doesn't vanish. [chart: delete-ratio-by-size.png]

6/ It isn't one repo driving it. Agents delete a smaller share than humans in 24 of 34 repos with enough PRs in both groups, and the gap holds without the four most agent-heavy repos and in both halves of the year. [chart: delete-ratio-by-repo.png]

7/ What this doesn't show: agent use without a footer is invisible to me, so the human group is contaminated (that pushes toward "no difference"). It's mostly Claude Code. It's merged PRs only. Mean net lines per PR are about equal (316 vs 307), so the tails matter more than the medians. And PR size isn't repo size.

8/ Full write-up, method, caveats, scripts and data (stdlib Python + gh, seeded sampling): https://github.com/krishansubudhi/ratchet/blob/study/docs/study/agent-pr-bloat.md. I built a code-size budget that only goes down because of this kind of drift, but nothing in the study depends on it: https://github.com/krishansubudhi/ratchet
