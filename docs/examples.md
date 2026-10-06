# Example: ratchet on pallets/click

Real commands, real output, on a fresh clone of
[pallets/click](https://github.com/pallets/click) at commit
`2247b35ea1c47c727d7a06e51fa280e12a863ff6` (2026-10-04). This is what
[docs/demo.gif](demo.gif) shows; regenerate both with [demo.sh](demo.sh).

**Honesty note:** the "agent bloats the code" step below is a scripted patch
([agent_change.patch](agent_change.patch)), not a live agent run. It stands
in for a real agent asked to add a feature who pastes a near-duplicate of
existing code instead of reusing it -- the exact shape of change `ratchet`
is built to catch. Everything else (`ratchet init`, `ratchet check`, the
numbers) is the real tool running against the real repo.

## 1. `ratchet init` records today's size

```
$ ratchet init
wrote .ratchet.json
  source   ceiling 11,430 lines
  tests    ceiling 13,385 lines
  per-file limit 400 lines, 21 file(s) already over it recorded at their size
next: commit .ratchet.json, then run `ratchet check` before every commit
```

`.ratchet.json` now holds those ceilings, plus a `file_ceilings` entry for
every file already over 400 lines (`src/click/core.py`, `src/click/types.py`,
and 19 others) -- frozen at their current size, so day one isn't a wall of
refusals.

## 2. An agent duplicates instead of reusing

The feature ask: print a two-column option-like list outside of
`HelpFormatter`. `click.formatting` already has exactly this in
`HelpFormatter.write_dl`, but the simulated change pastes a new
freestanding implementation instead -- twice, with a second near-identical
variant "for wider spacing". Applying it:

```
$ git apply agent_change.patch
```

## 3. `ratchet check` refuses it

```
$ ratchet check
ratchet: REFUSED -- 1 problem (source 11,502/11,430, tests 13,385/13,385)

1. source is 11,502 lines, ceiling 11,430: 72 over
   grew vs HEAD: src/click/formatting.py +72
   fix: remove at least 72 lines of source: delete dead code, reuse what exists instead of adding a parallel version, simplify.

Do not edit .ratchet.json or .ratchet-grants.jsonl to get past this.
If the growth is truly needed, stop and ask a human to run:
  ratchet grant +72 --group source --reason "<why>" --by <name>
exit code: 1
```

## 4. The fix: delete the duplicate

The real fix is to call `HelpFormatter.write_dl` like the rest of the
codebase does. For the demo, reverting the file gets to the same place:

```
$ git checkout -- src/click/formatting.py
```

## 5. `ratchet check` passes again

```
$ ratchet check
ratchet: ok -- source 11,430/11,430, tests 13,385/13,385
exit code: 0
```
