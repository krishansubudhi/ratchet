# A ratchet for code: keeping AI agents from bloating your repo

*Draft*

Coding agents have made writing code nearly free. Nobody had priced owning it
in the first place, and owning it got more expensive.

Every line in a repository is something a person, or the next agent, has to
read, keep in context, test, and not break. An agent that writes ten lines
where three would do hasn't saved you anything. It has handed you seven lines
of upkeep, forever. Across hundreds of agent sessions, that adds up to a
codebase that doubles in size without doubling in ability.

This post is about a small tool we built to stop that, and what happened when
we turned it on.

## Why agents bloat codebases

It isn't carelessness. Agents bloat code for structural reasons, and once you
see them you see them everywhere.

**Adding is local, deleting is global.** To add a function, an agent needs to
understand the ten lines around where it goes. To delete one safely, it needs
to know that nothing else depends on it. That takes a look at the whole
codebase, which is exactly what a context window doesn't hold. So agents add.

**Reuse needs search, and duplication needs only a keyboard.** The helper you
want probably exists already, three directories away under a slightly
different name. Finding it costs tokens and turns. Writing a new one costs
neither, and the result passes every test.

**Defensive code looks like diligence.** Extra validation, fallbacks for cases
that can't happen, try/except around things that don't throw. Each one reads
as careful work in review. Together they hide the real logic.

**No change is ever responsible.** No single diff is the problem. Every diff
is plus forty lines, reasonable, approved. The growth belongs to nobody, so
nobody stops it.

**Files only get longer.** Splitting a module is a refactor that no task
asked for, so a 300-line file becomes a 1,500-line file one reasonable edit
at a time.

Reviews don't catch this, because reviews look at diffs and the problem is the
sum. Linters don't catch it either: each line passes. What's missing is a
number that belongs to the whole repo and a rule about which way it can move.

## The ratchet

The idea fits on an index card.

**1. A budget.** The repo has recorded line ceilings, one for source and one
for tests. A change that pushes a total past its ceiling is refused. The
refusal is specific: what grew, by how much, which files grew most, and what
to do about it. It isn't a style warning. The change does not go in.

**2. Seams.** No file may exceed a per-file limit. When one does, the agent is
told to split it, and the tool lists the top-level definitions nearest the
middle as places to cut. Files that were already too big when you adopted the
rule are recorded at their current size. They may shrink, never grow.
Without this rule, a budget just pushes code into the files nobody wants to
touch.

**3. Grants.** Sometimes the growth is the point: a real feature, a new
integration. Then a human raises the ceiling with an explicit grant: a number
of lines, a reason, and a name, appended to a log that can't be rewritten. The
agent can't grant itself room. If it edits the config by hand, the CI check
compares against the base branch and refuses any raise that a new grant entry
doesn't pay for. Growth becomes a decision someone made on purpose, not
something that happened.

**4. Tighten.** When code shrinks, the ceiling follows it down, and it never
goes back up without a grant. That's the ratchet. Each cleanup becomes the new
floor, so the gains from a good refactoring day can't quietly leak away over
the next week.

The rules are almost too simple to bother writing down. What makes them work
is where the pressure goes. Without a budget, the cheapest way for an agent to
finish a task is to add code. With one, the cheapest way is often to find the
existing helper, delete the dead branch, or merge two near-duplicates, because
that's how it gets under the line. You've changed what the agent's local
optimum is, without writing a single prompt about code quality.

There's a second effect we didn't expect. The refusal message is a much better
prompt than any instruction. "Write concise code" in a system prompt is
ignored in practice. "source is 112 lines over its ceiling; app/api.py grew by
80" is specific and checkable, so the agent acts on it.

## What happened when we used it

We ran this rule in our own agent system, a feature-rich codebase of tens of
thousands of lines that agents work in all day: several agents in parallel,
shipping changes continuously.

Over one heavy 48-hour stretch, agents landed a steady stream of features and
fixes, and the codebase grew by only about 2,000 lines in total. Features
went in. What didn't go in was the usual sediment around them. Over and over
we watched an agent hit the ceiling, go back, and find something to remove:
an older code path its own change made obsolete, a helper that duplicated one
elsewhere, a test that covered the same case as three others.

A few observations from living with it:

- **Agents are good at deleting once you ask in the right currency.** Lines
  are a currency they understand exactly. The refusal says "112 over", and
  the next attempt comes back under.
- **Grants are rare and informative.** When a human grants room, the reason
  in the log reads like a changelog of where the codebase deliberately
  expanded. Reading that log is a fast way to see what the system became.
- **The per-file limit matters as much as the total.** Before it, agents
  piled into the one big file that already had everything. After it, the
  splits they made were mostly reasonable, because the seams offered were
  real boundaries.
- **Tighten has to be explicit and visible.** A ceiling that drops after
  every cleanup is satisfying to watch, and it means the slack you gain from
  a good refactoring is banked rather than spent by the next change.
- **Count non-blank lines, and nothing else.** We tried cleverer metrics.
  Lines are crude, but agents can't argue with them, a human can check them
  at a glance, and gaming them (one-line monsters) shows up in review
  immediately.

It isn't free. A budget at zero slack means even a good change sometimes needs
a deletion to land, and you'll occasionally grant room you'd rather not. We
think that friction is the feature: it moves the question "should this code
exist?" from never to every time.

## Try it

We've packaged the rule as a small, dependency-free command-line tool that
works with any coding-agent harness:

```sh
pip install -e .        # from a clone
ratchet init            # record today's totals; commit .ratchet.json
ratchet check           # 0 = fine, 1 = refused with instructions
```

There are drop-in integrations for Claude Code (a Stop hook), Cursor, Codex
CLI, and aider (instruction files plus a git hook or test command), the
pre-commit framework, and GitHub Actions, where `--base` catches hand-edited
ceilings. There's also a plain prompt snippet for any other agent. Grants are
`ratchet grant +N --reason "..." --by NAME`, and shrinking is banked with
`ratchet tighten`.

Start with the current size of your repo. The budget won't make anything
smaller on day one, but from then on every line that gets in had to earn
its place.

**Code:** [github.com/OWNER/ratchet](https://github.com/OWNER/ratchet) *(link placeholder)*
