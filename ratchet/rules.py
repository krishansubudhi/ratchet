# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""The rules. Pure functions over measurements and configs: no I/O here,
so every rule is testable with plain dicts.

1. budget  -- a group's total may not exceed its ceiling.
2. seams   -- a file may not exceed the per-file limit; split it.
3. grants  -- under --base, any ceiling higher than the base's must be paid
              for by grant entries appended since the base, and the grants
              log itself may only be appended to.
4. tighten -- ceilings only move down, to what the code measures now.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

Sizes = Mapping[str, Mapping[str, int]]   # group -> path -> lines


@dataclass
class Violation:
    kind: str             # "budget" | "file-size" | "unpaid-raise" | "grants-log"
    target: str           # a group name, "file:PATH", or a config key
    measured: int
    ceiling: int
    message: str
    fix: str
    seams: list[tuple[int, str]] = field(default_factory=list)

    @property
    def over(self) -> int:
        return self.measured - self.ceiling

    def to_dict(self) -> dict[str, Any]:
        return dict(asdict(self), over=self.over,
                    seams=[{"line": n, "at": s} for n, s in self.seams])


def file_limit(cfg: Mapping[str, Any], path: str) -> int:
    return int(cfg["file_ceilings"].get(path, cfg["max_file_lines"]))


def totals(sizes: Sizes) -> dict[str, int]:
    return {g: sum(files.values()) for g, files in sizes.items()}


def rule_budget(cfg: Mapping[str, Any], sizes: Sizes,
                ceilings: Mapping[str, int] | None = None) -> list[Violation]:
    caps = ceilings or cfg["ceilings"]
    out = []
    for group, total in totals(sizes).items():
        cap = int(caps.get(group, cfg["ceilings"][group]))
        if total <= cap:
            continue
        out.append(Violation(
            "budget", group, total, cap,
            "%s is %s lines, ceiling %s: %s over" % (
                group, n(total), n(cap), n(total - cap)),
            "remove at least %s lines of %s: delete dead code, reuse what "
            "exists instead of adding a parallel version, simplify." % (
                n(total - cap), group)))
    return out


def rule_file_size(cfg: Mapping[str, Any], sizes: Sizes,
                   limits: Mapping[str, int] | None = None) -> list[Violation]:
    out = []
    for files in sizes.values():
        for path, lines in sorted(files.items()):
            cap = int((limits or {}).get(path, file_limit(cfg, path)))
            if lines <= cap:
                continue
            grandfathered = path in cfg["file_ceilings"]
            out.append(Violation(
                "file-size", "file:" + path, lines, cap,
                "%s is %s lines, %s %s" % (
                    path, n(lines),
                    "and was recorded at" if grandfathered else "limit",
                    n(cap)),
                ("this file was already over the limit, so it may shrink "
                 "but not grow; " if grandfathered else "") +
                "split it at a seam: move a cohesive group of definitions "
                "into a new file, so each piece is under %s lines." %
                n(cfg["max_file_lines"])))
    return out


def near_files(cfg: Mapping[str, Any], sizes: Sizes, headroom: float = 0.1
              ) -> list[tuple[str, int, int]]:
    """(path, lines, cap) for files within `headroom` (10% by default) of
    their per-file cap, or already over it. Most urgent -- least remaining,
    negative first -- sorts first."""
    out = []
    for files in sizes.values():
        for path, lines in files.items():
            cap = file_limit(cfg, path)
            if cap - lines <= cap * headroom:
                out.append((path, lines, cap))
    return sorted(out, key=lambda t: t[2] - t[1])


def limits_of(cfg: Mapping[str, Any]) -> dict[str, int]:
    """Every number that caps growth, flattened: groups by name, files as
    `file:PATH`, and the per-file limit itself."""
    out = {g: int(c) for g, c in cfg["ceilings"].items()}
    out.update({"file:" + p: int(c) for p, c in cfg["file_ceilings"].items()})
    out["max_file_lines"] = int(cfg["max_file_lines"])
    return out


def granted(grants: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in grants:
        out[g["target"]] = out.get(g["target"], 0) + int(g["lines"])
    return out


def allowed(base: Mapping[str, Any], new_grants: Sequence[Mapping[str, Any]]
            ) -> dict[str, int]:
    """What each limit may be at most: the base's value plus what humans
    granted since. A file with no recorded ceiling at the base was capped by
    the base's per-file limit."""
    was = limits_of(base)
    out = dict(was)
    for target, lines in granted(new_grants).items():
        start = was.get(target)
        if start is None:
            start = was["max_file_lines"] if target.startswith("file:") else 0
        out[target] = start + lines
    return out


def rule_unpaid_raise(cfg: Mapping[str, Any], base: Mapping[str, Any],
                      new_grants: Sequence[Mapping[str, Any]]) -> list[Violation]:
    """Editing the config by hand is the same as growing past it."""
    cap = allowed(base, new_grants)
    out = []
    for target, value in limits_of(cfg).items():
        most = cap.get(target)
        if most is None:
            most = cap["max_file_lines"] if target.startswith("file:") else 0
        if value <= most:
            continue
        out.append(Violation(
            "unpaid-raise", target, value, most,
            "%s limit was raised to %s, but the base plus grants allows %s" % (
                target, n(value), n(most)),
            "do not edit the config to make room; revert the change to "
            "it. Only a human raises a limit, with `ratchet grant`."))
    return out


def rule_grants_log(base_log: Sequence[Mapping[str, Any]],
                    log: Sequence[Mapping[str, Any]]) -> list[Violation]:
    if list(log[:len(base_log)]) == list(base_log):
        return []
    return [Violation(
        "grants-log", "grants-log", len(log), len(base_log),
        "the grants log was edited, not appended to",
        "restore the existing lines exactly; grants are only ever added.")]


def effective(cfg: Mapping[str, Any], base: Mapping[str, Any] | None,
              new_grants: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """The limits a check holds the tree to: the config's own, and under
    --base never more than the base plus new grants."""
    mine = limits_of(cfg)
    if base is None:
        return mine
    cap = allowed(base, new_grants)
    return {k: min(v, cap.get(k, v)) for k, v in mine.items()}


def check(cfg: Mapping[str, Any], sizes: Sizes,
          base: Mapping[str, Any] | None = None,
          base_log: Sequence[Mapping[str, Any]] = (),
          log: Sequence[Mapping[str, Any]] = ()) -> list[Violation]:
    new_grants = list(log[len(base_log):]) if base is not None else []
    caps = effective(cfg, base, new_grants)
    files = {k[5:]: v for k, v in caps.items() if k.startswith("file:")}
    limit = caps["max_file_lines"]
    limits = {p: files.get(p, limit)
              for group in sizes.values() for p in group}
    out = rule_budget(cfg, sizes, caps) + rule_file_size(cfg, sizes, limits)
    if base is not None:
        out = rule_grants_log(base_log, log) + rule_unpaid_raise(
            cfg, base, new_grants) + out
    return out


def tighten(cfg: Mapping[str, Any], sizes: Sizes) -> tuple[dict[str, Any], list[str]]:
    """The ratchet: every ceiling drops to what the code measures now (plus
    slack), and never rises. Recorded file ceilings drop the same way, and
    disappear once the file is back under the per-file limit or gone."""
    new = dict(cfg, ceilings=dict(cfg["ceilings"]), file_ceilings={})
    notes = []
    slack = int(cfg.get("slack", 0))
    for group, total in totals(sizes).items():
        old = int(cfg["ceilings"][group])
        if total + slack < old:
            new["ceilings"][group] = total + slack
            notes.append("%s: %s -> %s" % (group, n(old), n(total + slack)))
    lines = {p: c for files in sizes.values() for p, c in files.items()}
    for path, old in cfg["file_ceilings"].items():
        now = lines.get(path)
        if now is None or now <= int(cfg["max_file_lines"]):
            notes.append("%s: recorded %s -> back under the limit" % (path, n(old)))
        elif now < int(old):
            new["file_ceilings"][path] = now
            notes.append("%s: %s -> %s" % (path, n(old), n(now)))
        else:
            new["file_ceilings"][path] = int(old)
    return new, notes


def n(value: int) -> str:
    return "{:,}".format(value)
