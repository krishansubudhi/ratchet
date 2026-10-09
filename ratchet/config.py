# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""The two files ratchet keeps: `.ratchet.json` (policy and ceilings; JSON
because ratchet must write it) and `.ratchet-grants.jsonl` (append-only log
of every human allowance, one JSON object per line)."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from . import measure

CONFIG = ".ratchet.json"
GRANTS = ".ratchet-grants.jsonl"
VERSION = 1
DEFAULT_MAX_FILE_LINES = 400


class ConfigError(Exception):
    """Missing or malformed config: exit 2, never a silent pass."""


def find_root(start: str) -> str:
    """Nearest dir at/above `start` with a config, else git top, else start."""
    here = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(here, CONFIG)):
            return here
        up = os.path.dirname(here)
        if up == here:
            break
        here = up
    if measure.is_git(start):
        return measure.git(start, "rev-parse", "--show-toplevel").strip()
    return os.path.abspath(start)


def parse(text: str, where: str = CONFIG) -> dict[str, Any]:
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError("%s is not valid JSON: %s" % (where, exc)) from exc
    if not isinstance(cfg, dict) or not isinstance(cfg.get("groups"), dict):
        raise ConfigError("%s has no \"groups\" table" % where)
    cfg.setdefault("max_file_lines", DEFAULT_MAX_FILE_LINES)
    cfg.setdefault("slack", 0)
    cfg.setdefault("ceilings", {})
    cfg.setdefault("file_ceilings", {})
    for group in cfg["groups"]:
        if group not in cfg["ceilings"]:
            raise ConfigError("%s: group %r has no ceiling; run `ratchet "
                              "tighten` or `ratchet init --force`" % (where, group))
    return cfg


def load(root: str) -> dict[str, Any]:
    path = os.path.join(root, CONFIG)
    if not os.path.isfile(path):
        raise ConfigError("no %s here; run `ratchet init` first" % CONFIG)
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())


def save(root: str, cfg: dict[str, Any]) -> None:
    cfg = dict(cfg, file_ceilings=dict(sorted(cfg["file_ceilings"].items())))
    with open(os.path.join(root, CONFIG), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")


def default_groups(paths: list[str]) -> dict[str, dict[str, list[str]]]:
    """Source is every code file that is not a test; tests are code files in
    the usual test locations. Only extensions actually present are listed,
    so data files, docs and fixtures never count."""
    exts = sorted({os.path.splitext(p)[1].lower() for p in paths}
                  & measure.CODE_EXTS) or [".py"]
    return {
        "source": {"include": ["**"], "exclude": list(measure.TEST_GLOBS),
                   "extensions": exts},
        "tests": {"include": list(measure.TEST_GLOBS), "exclude": [],
                  "extensions": exts},
    }


def scaffold(root: str, max_file_lines: int, slack: int) -> dict[str, Any]:
    """Ceilings at today's totals plus slack; files already over the per-file
    limit are recorded at their size: they may shrink, never grow."""
    groups = default_groups(measure.list_files(root))
    sizes = measure.measure(root, groups)
    return {
        "version": VERSION,
        "max_file_lines": max_file_lines,
        "slack": slack,
        "groups": groups,
        "ceilings": {g: sum(files.values()) + slack for g, files in sizes.items()},
        "file_ceilings": {p: n for files in sizes.values()
                          for p, n in files.items() if n > max_file_lines},
    }


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_grants(text: str) -> list[dict[str, Any]]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ConfigError("%s line %d is not JSON: %s" % (GRANTS, n, exc)) from exc
    return out


def load_grants(root: str) -> list[dict[str, Any]]:
    path = os.path.join(root, GRANTS)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return parse_grants(fh.read())


def append_grant(root: str, entry: dict[str, Any]) -> None:
    with open(os.path.join(root, GRANTS), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
