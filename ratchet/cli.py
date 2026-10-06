# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""Command line: init, check, grant, tighten. Exit 0 ok, 1 refused, 2 error."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence

from . import __version__, config, measure, rules
from .rules import n

OK, REFUSED, ERROR = 0, 1, 2


def _sizes(root: str, cfg: dict[str, Any]) -> dict[str, dict[str, int]]:
    return measure.measure(root, cfg["groups"])


def cmd_init(root: str, args: argparse.Namespace) -> int:
    if os.path.exists(os.path.join(root, config.CONFIG)) and not args.force:
        print("%s already exists; use --force to rewrite it" % config.CONFIG,
              file=sys.stderr)
        return ERROR
    cfg = config.scaffold(root, args.max_file_lines, args.slack)
    config.save(root, cfg)
    print("wrote %s" % config.CONFIG)
    for group, cap in cfg["ceilings"].items():
        print("  %-8s ceiling %s lines" % (group, n(cap)))
    print("  per-file limit %s lines, %d file(s) already over it recorded "
          "at their size" % (n(cfg["max_file_lines"]), len(cfg["file_ceilings"])))
    print("next: commit %s, then run `ratchet check` before every commit"
          % config.CONFIG)
    return OK


def _grew(root: str, ref: str | None, sizes: dict[str, dict[str, int]]
          ) -> dict[str, list[tuple[str, int]]]:
    """group -> [(path, +lines)], biggest first, against `ref`."""
    if ref is None:
        return {}
    try:
        before = measure.changed_since(root, ref)
    except RuntimeError:
        return {}
    out = {}
    for group, files in sizes.items():
        up = [(p, files[p] - before[p]) for p in files
              if p in before and files[p] > before[p]]
        out[group] = sorted(up, key=lambda x: -x[1])
    return out


def _default_ref(root: str) -> str | None:
    if not measure.is_git(root):
        return None
    ok = measure.git(root, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    return "HEAD" if ok.strip() else None


def _grant_hint(v: rules.Violation) -> str | None:
    if v.kind == "budget":
        return "ratchet grant +%d --group %s" % (v.over, v.target)
    if v.kind == "file-size":
        return "ratchet grant +%d --file %s" % (v.over, v.target[5:])
    return None


def render(result: dict[str, Any], violations: Sequence[rules.Violation]) -> str:
    totals = result["totals"]
    summary = ", ".join("%s %s/%s" % (g, n(t["lines"]), n(t["ceiling"]))
                        for g, t in totals.items())
    if not violations:
        lines = ["ratchet: ok -- " + summary]
        room = sum(t["ceiling"] - t["lines"] for t in totals.values())
        if room > result["slack"] * len(totals):
            lines.append("  the code shrank: run `ratchet tighten` and commit "
                         "to bank it")
        return "\n".join(lines)
    out = ["ratchet: REFUSED -- %d problem%s (%s)" % (
        len(violations), "" if len(violations) == 1 else "s", summary), ""]
    for i, v in enumerate(violations, 1):
        out.append("%d. %s" % (i, v.message))
        grew = result["grew"].get(v.target, [])
        if grew:
            out.append("   grew vs %s: %s" % (result["against"], ", ".join(
                "%s +%d" % g for g in grew[:5])))
        if v.seams:
            out.append("   seams near the middle: " + ", ".join(
                "line %d `%s`" % s for s in v.seams))
        out.append("   fix: " + v.fix)
    hints = [h for h in map(_grant_hint, violations) if h]
    out += ["", "Do not edit %s or %s to get past this." % (
        config.CONFIG, config.GRANTS)]
    if hints:
        out.append("If the growth is truly needed, stop and ask a human to run:")
        out += ['  %s --reason "<why>" --by <name>' % h for h in hints]
    return "\n".join(out)


def cmd_check(root: str, args: argparse.Namespace) -> int:
    cfg = config.load(root)
    sizes = _sizes(root, cfg)
    base = None
    base_log: list[dict[str, Any]] = []
    log = config.load_grants(root)
    if args.base:
        try:
            measure.git(root, "rev-parse", "--verify", "--quiet",
                        args.base + "^{commit}")
        except RuntimeError:
            raise config.ConfigError("--base %s is not a commit here (in CI, "
                                     "fetch full history)" % args.base) from None
        text = measure.show(root, args.base, config.CONFIG)
        base = config.parse(text, "%s:%s" % (args.base, config.CONFIG)) \
            if text is not None else None
        base_log = config.parse_grants(measure.show(root, args.base,
                                                    config.GRANTS) or "")
    violations = rules.check(cfg, sizes, base, base_log, log)
    for v in violations:
        if v.kind == "file-size":
            try:
                with open(os.path.join(root, v.target[5:]), encoding="utf-8",
                          errors="replace") as fh:
                    v.seams = measure.best_seams(fh.read())
            except OSError:
                pass
    caps = rules.effective(cfg, base, log[len(base_log):] if base else [])
    against = args.base or _default_ref(root)
    result = {
        "ok": not violations,
        "against": against,
        "slack": int(cfg["slack"]),
        "totals": {g: {"lines": t, "ceiling": caps[g]}
                   for g, t in rules.totals(sizes).items()},
        "grew": {},
    }
    grew = _grew(root, against, sizes)
    result["grew"] = {g: v for g, v in grew.items() if v}
    if args.json:
        payload = dict(result, violations=[v.to_dict() for v in violations],
                       grew={g: [{"path": p, "lines": d} for p, d in v]
                             for g, v in result["grew"].items()})
        print(json.dumps(payload, indent=2))
    else:
        print(render(result, violations))
    return REFUSED if violations else OK


def _hook_retry() -> bool:
    """True when an agent harness says this is its second try at stopping
    after a refusal (Claude Code's `stop_hook_active`). Let it stop then: it
    has seen the message, and a human may need to grant."""
    if sys.stdin is None or sys.stdin.isatty():
        return False
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return False
    return isinstance(event, dict) and bool(event.get("stop_hook_active"))


def cmd_hook(root: str, args: argparse.Namespace) -> int:
    """Exit 2 with the refusal on stderr is what agent hooks read as "blocked,
    show the model why". Errors never block: they print and exit 0."""
    if _hook_retry():
        print("ratchet: still over budget; tell the human what grew and "
              "whether a grant is needed", file=sys.stderr)
        return OK
    out = sys.stdout
    sys.stdout = sys.stderr
    try:
        code = cmd_check(root, args)
    except (config.ConfigError, RuntimeError) as exc:
        print("ratchet: error: %s" % exc)
        code = OK
    finally:
        sys.stdout = out
    return 2 if code == REFUSED else OK


def _amount(text: str) -> int:
    try:
        value = int(text.lstrip("+"))
    except ValueError:
        raise argparse.ArgumentTypeError("expected +N, got %r" % text) from None
    if value < 1:
        raise argparse.ArgumentTypeError("a grant is at least +1")
    return value


def cmd_grant(root: str, args: argparse.Namespace) -> int:
    if not args.reason.strip() or not args.by.strip():
        print("a grant needs a real --reason and --by", file=sys.stderr)
        return ERROR
    cfg = config.load(root)
    if args.file:
        path = args.file.replace(os.sep, "/")
        target = "file:" + path
        before = rules.file_limit(cfg, path)
        cfg["file_ceilings"][path] = before + args.amount
    elif args.max_file_lines:
        target, before = "max_file_lines", int(cfg["max_file_lines"])
        cfg["max_file_lines"] = before + args.amount
    else:
        target = args.group
        if target not in cfg["ceilings"]:
            print("no group %r; groups are: %s" % (
                target, ", ".join(cfg["ceilings"])), file=sys.stderr)
            return ERROR
        before = int(cfg["ceilings"][target])
        cfg["ceilings"][target] = before + args.amount
    config.append_grant(root, {
        "ts": config.now_utc(), "target": target, "lines": args.amount,
        "before": before, "after": before + args.amount,
        "reason": args.reason.strip(), "by": args.by.strip()})
    config.save(root, cfg)
    print("granted +%d to %s (%s -> %s), logged in %s" % (
        args.amount, target, n(before), n(before + args.amount), config.GRANTS))
    print("commit %s and %s together" % (config.CONFIG, config.GRANTS))
    return OK


def cmd_tighten(root: str, args: argparse.Namespace) -> int:
    cfg = config.load(root)
    new, notes = rules.tighten(cfg, _sizes(root, cfg))
    if not notes:
        print("nothing to tighten: every ceiling already fits the code")
        return OK
    if not args.dry_run:
        config.save(root, new)
    print(("would tighten:" if args.dry_run else "tightened:"))
    for note in notes:
        print("  " + note)
    return OK


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ratchet", description="A code-size budget that only goes down.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-C", dest="dir", default=".", help="run as if started in DIR")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="scan the repo and write %s" % config.CONFIG)
    s.add_argument("--max-file-lines", type=int,
                   default=config.DEFAULT_MAX_FILE_LINES)
    s.add_argument("--slack", type=int, default=0,
                   help="lines of headroom kept above the measured totals")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("check", help="refuse growth past the ceilings")
    s.add_argument("--base", metavar="REF",
                   help="also refuse limit raises not paid for by grants since REF")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("--hook", action="store_true",
                   help="agent-hook mode: report on stderr, exit 2 when refused")

    s = sub.add_parser("grant", help="(humans) allow N more lines, logged")
    s.add_argument("amount", type=_amount, metavar="+N")
    where = s.add_mutually_exclusive_group()
    where.add_argument("--group", default="source")
    where.add_argument("--file", metavar="PATH")
    where.add_argument("--max-file-lines", action="store_true",
                       help="raise the per-file limit itself")
    s.add_argument("--reason", required=True)
    s.add_argument("--by", required=True)

    s = sub.add_parser("tighten", help="lower ceilings to what the code measures")
    s.add_argument("--dry-run", action="store_true")
    return p


COMMANDS = {"init": cmd_init, "check": cmd_check, "grant": cmd_grant,
            "tighten": cmd_tighten}


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = os.path.abspath(args.dir) if args.cmd == "init" else \
            config.find_root(args.dir)
        if args.cmd == "init" and measure.is_git(root):
            root = measure.git(root, "rev-parse", "--show-toplevel").strip()
        if args.cmd == "check" and args.hook:
            return cmd_hook(root, args)
        return COMMANDS[args.cmd](root, args)
    except (config.ConfigError, RuntimeError) as exc:
        print("ratchet: error: %s" % exc, file=sys.stderr)
        return ERROR
