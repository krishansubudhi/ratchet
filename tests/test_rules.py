# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""The rules as pure functions over dicts."""

from ratchet import measure, rules

GROUPS = {"source": {"include": ["**"], "exclude": ["tests/**"],
                     "extensions": [".py"]},
          "tests": {"include": ["tests/**"], "extensions": [".py"]}}


def cfg(source=100, tests=10, max_file_lines=200, file_ceilings=None, slack=0):
    return {"groups": GROUPS, "max_file_lines": max_file_lines, "slack": slack,
            "ceilings": {"source": source, "tests": tests},
            "file_ceilings": dict(file_ceilings or {})}


def kinds(found):
    return [(v.kind, v.target) for v in found]


def test_under_budget_passes():
    assert rules.check(cfg(), {"source": {"a.py": 40, "b.py": 60},
                               "tests": {"tests/t.py": 10}}) == []


def test_growth_past_ceiling_is_refused_with_amount():
    found = rules.check(cfg(), {"source": {"a.py": 45, "b.py": 60}, "tests": {}})
    assert kinds(found) == [("budget", "source")]
    assert found[0].over == 5 and "5 over" in found[0].message


def test_oversized_file_must_split():
    found = rules.check(cfg(source=1000, max_file_lines=50), {"source": {"big.py": 51}, "tests": {}})
    assert kinds(found) == [("file-size", "file:big.py")]
    assert "seam" in found[0].fix


def test_grandfathered_file_may_shrink_not_grow():
    c = cfg(source=1000, max_file_lines=50, file_ceilings={"big.py": 80})
    assert rules.check(c, {"source": {"big.py": 80}, "tests": {}}) == []
    assert kinds(rules.check(c, {"source": {"big.py": 81}, "tests": {}})) == \
        [("file-size", "file:big.py")]


def test_hand_raised_ceiling_is_refused_under_base():
    base, head = cfg(source=100), cfg(source=150)
    sizes = {"source": {"a.py": 40, "b.py": 80}, "tests": {}}
    found = rules.check(head, sizes, base=base)
    assert ("unpaid-raise", "source") in kinds(found)
    assert ("budget", "source") in kinds(found)   # held to the base's 100


def test_grant_pays_for_a_raise():
    base, head = cfg(source=100), cfg(source=150)
    log = [{"target": "source", "lines": 50, "reason": "r", "by": "h"}]
    sizes = {"source": {"a.py": 40, "b.py": 80}, "tests": {}}
    assert rules.check(head, sizes, base=base, base_log=[], log=log) == []


def test_old_grants_do_not_pay_twice():
    log = [{"target": "source", "lines": 50, "reason": "r", "by": "h"}]
    found = rules.check(cfg(source=150), {"source": {}, "tests": {}},
                        base=cfg(source=100), base_log=log, log=log)
    assert kinds(found) == [("unpaid-raise", "source")]


def test_grants_log_is_append_only():
    old = [{"target": "source", "lines": 5, "reason": "r", "by": "h"}]
    found = rules.check(cfg(), {"source": {}, "tests": {}}, base=cfg(),
                        base_log=old, log=[])
    assert kinds(found) == [("grants-log", "grants-log")]


def test_raising_per_file_limit_is_a_raise():
    found = rules.check(cfg(max_file_lines=500), {"source": {}, "tests": {}},
                        base=cfg(max_file_lines=50))
    assert kinds(found) == [("unpaid-raise", "max_file_lines")]


def test_new_file_ceiling_needs_a_file_grant():
    head = cfg(source=1000, max_file_lines=50, file_ceilings={"big.py": 70})
    base = cfg(source=1000, max_file_lines=50)
    sizes = {"source": {"big.py": 70}, "tests": {}}
    assert ("unpaid-raise", "file:big.py") in kinds(
        rules.check(head, sizes, base=base))
    log = [{"target": "file:big.py", "lines": 20, "reason": "r", "by": "h"}]
    assert rules.check(head, sizes, base=base, base_log=[], log=log) == []


def test_tighten_only_goes_down():
    c = cfg(source=100, tests=10, slack=2, max_file_lines=50,
            file_ceilings={"big.py": 80, "gone.py": 90, "fixed.py": 70})
    sizes = {"source": {"big.py": 60, "fixed.py": 30}, "tests": {"tests/t.py": 20}}
    new, notes = rules.tighten(c, sizes)
    assert new["ceilings"] == {"source": 92, "tests": 10}   # tests never rise
    assert new["file_ceilings"] == {"big.py": 60}
    assert len(notes) == 4
    assert rules.tighten(new, sizes)[1] == []


def test_glob_semantics():
    assert measure.matches("a/b/tests/x.py", ["**/tests/**"])
    assert measure.matches("tests/x.py", ["**/tests/**"])
    assert measure.matches("pkg/test_x.py", ["**/test_*"])
    assert not measure.matches("pkg/contest.py", ["**/test*"])
    assert not measure.matches("a/b.py", ["*.py"])
    assert measure.matches("b.py", ["*.py"])


def test_blank_lines_and_binaries_are_free():
    assert measure.count_text(b"a\n\n   \nb\n") == 2
    assert measure.count_text(b"\0\1\2") == 0


def test_seams_find_top_level_definitions_with_decorators():
    text = "import x\n\n@dec\ndef a():\n    pass\n\nclass B:\n    def m(self):\n        pass\n"
    assert measure.seams(text) == [(3, "def a"), (7, "class B")]
    js = "export async function go() {}\nconst x = 1\nexport default class App {}\n"
    assert [s[1] for s in measure.seams(js)] == ["function go", "class App"]
