# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
"""The CLI end to end, against real temporary git repos."""

import json
import subprocess
import sys

from ratchet import config
from ratchet.cli import main

from conftest import funcs


def run(repo, *args):
    return main(["-C", repo.path, *args])


def test_init_records_totals_and_oversized_files(repo, capsys):
    repo.write("src/big.py", funcs(300))   # 600 lines
    assert run(repo, "init") == 0
    cfg = json.loads(repo.read(config.CONFIG))
    assert cfg["ceilings"] == {"source": 701, "tests": 10}
    assert cfg["file_ceilings"] == {"src/big.py": 600}
    assert run(repo, "init") == 2   # no clobbering without --force
    assert run(repo, "init", "--force", "--slack", "5") == 0
    assert json.loads(repo.read(config.CONFIG))["ceilings"]["source"] == 706


def test_check_exit_codes_and_message(repo, capsys, monkeypatch):
    run(repo, "init")
    repo.commit()
    assert run(repo, "check") == 0
    assert "ratchet: ok" in capsys.readouterr().out
    repo.append("src/util.py", "Y = 2\nZ = 3\n")
    assert run(repo, "check") == 1
    out = capsys.readouterr().out
    assert out.startswith("ratchet: refused -- source grew 2 lines past its "
                          "limit (103 / 101)\n\n  src/util.py  +2\n")
    assert "1. remove 2 lines of code" in out and "agents must ask" in out
    grant = 'ratchet grant +2 --group source --reason "why"\n'
    assert grant in out and "Stop here" not in out   # no agent rules for humans
    monkeypatch.setenv("GIT_INDEX_FILE", "x")   # git sets it in pre-commit
    monkeypatch.setenv("CLAUDECODE", "1")
    assert run(repo, "check") == 1
    out = capsys.readouterr().out
    assert out.startswith("ratchet: commit blocked -- source grew 2 lines past") \
        and "Do not edit .ratchet.json" in out and "never run this yourself" in out
    assert out.endswith("report these numbers to a human instead of cutting "
                        "more and resubmitting.\n")
    monkeypatch.setenv("RATCHET_AGENT", "0")
    assert run(repo, "check") == 1 and "Stop here" not in capsys.readouterr().out


def test_check_json(repo, capsys):
    run(repo, "init")
    repo.commit()
    repo.write("src/new.py", "a = 1\n")
    capsys.readouterr()
    assert run(repo, "check", "--json") == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["violations"][0]["kind"] == "budget"
    assert data["violations"][0]["over"] == 1
    assert data["grew"]["source"] == [{"path": "src/new.py", "lines": 1}]


def test_split_suggests_seams(repo, capsys):
    run(repo, "init", "--max-file-lines", "100")
    repo.commit()
    repo.append("src/app.py", "def extra():\n    return 0\n")
    run(repo, "grant", "+2", "--reason", "r", "--by", "h")
    capsys.readouterr()
    assert run(repo, "check") == 1
    out = capsys.readouterr().out
    assert "src/app.py is 2 lines past its limit (102 / 100)" in out
    assert "seams near the middle: line" in out


def test_shrink_passes_and_tighten_banks_it(repo, capsys):
    run(repo, "init")
    repo.commit()
    repo.write("src/app.py", funcs(40))   # -20 lines
    assert run(repo, "check") == 0
    assert "ratchet tighten" in capsys.readouterr().out
    assert run(repo, "tighten", "--dry-run") == 0
    assert json.loads(repo.read(config.CONFIG))["ceilings"]["source"] == 101
    assert run(repo, "tighten") == 0
    assert json.loads(repo.read(config.CONFIG))["ceilings"]["source"] == 81
    repo.write("src/app.py", funcs(45))   # regrowing past the new floor
    assert run(repo, "check") == 1


def test_grant_is_logged_and_lets_growth_through(repo, capsys):
    run(repo, "init")
    base = repo.commit()
    repo.write("src/feature.py", funcs(10))
    assert run(repo, "check") == 1
    assert run(repo, "grant", "+20", "--reason", "new export feature",
               "--by", "alice") == 0
    log = config.load_grants(repo.path)
    assert len(log) == 1 and log[0]["target"] == "source"
    assert log[0]["lines"] == 20 and log[0]["by"] == "alice"
    assert log[0]["before"] == 101 and log[0]["after"] == 121
    assert run(repo, "check") == 0
    assert run(repo, "check", "--base", base) == 0
    run(repo, "grant", "+5", "--file", "src/feature.py", "--reason", "x",
        "--by", "bob")
    assert len(config.load_grants(repo.path)) == 2


def test_grant_needs_reason_and_by_defaults_to_git_user(repo, monkeypatch):
    run(repo, "init")
    assert run(repo, "grant", "+5", "--reason", " ", "--by", "a") == 2
    assert run(repo, "grant", "+5", "--group", "nope", "--reason", "x") == 2
    assert config.load_grants(repo.path) == []
    assert run(repo, "grant", "+5", "--reason", "x") == 0
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", repo.path + "/none")
    monkeypatch.setenv("USER", "carol")
    repo.git("config", "--unset", "user.name")
    assert run(repo, "grant", "+1", "--reason", "y") == 0
    assert [g["by"] for g in config.load_grants(repo.path)] == ["test", "carol"]


def test_base_catches_hand_edited_config(repo, capsys):
    run(repo, "init")
    base = repo.commit()
    repo.write("src/feature.py", funcs(10))
    cfg = json.loads(repo.read(config.CONFIG))
    cfg["ceilings"]["source"] += 50
    repo.write(config.CONFIG, json.dumps(cfg))
    assert run(repo, "check") == 0          # locally the edit "works"...
    capsys.readouterr()
    assert run(repo, "check", "--base", base) == 1   # ...review does not
    out = capsys.readouterr().out
    assert "source limit was raised to 151" in out


def test_base_catches_rewritten_grants_log(repo, capsys):
    run(repo, "init")
    run(repo, "grant", "+5", "--reason", "x", "--by", "a")
    base = repo.commit()
    repo.write(config.GRANTS, "")
    assert run(repo, "check", "--base", base) == 1
    assert "grants log was edited" in capsys.readouterr().out


def test_errors_exit_2(repo, capsys):
    assert run(repo, "check") == 2       # no config yet
    assert "ratchet init" in capsys.readouterr().err
    run(repo, "init")
    repo.commit()
    assert run(repo, "check", "--base", "no-such-ref") == 2


def test_works_without_git(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert main(["-C", str(tmp_path), "init"]) == 0
    assert main(["-C", str(tmp_path), "check"]) == 0
    (tmp_path / "b.py").write_text("y = 1\n")
    assert main(["-C", str(tmp_path), "check"]) == 1


def test_hook_mode_blocks_with_exit_2_then_lets_go(repo):
    run(repo, "init")
    repo.commit()
    repo.write("src/new.py", "a = 1\n")
    hook = [sys.executable, "-m", "ratchet", "-C", repo.path, "check", "--hook"]
    first = subprocess.run(hook, input="{}", capture_output=True, text=True)
    assert first.returncode == 2 and first.stdout == ""
    assert first.stderr.rstrip().endswith("cutting more and resubmitting.")
    again = subprocess.run(hook, input='{"stop_hook_active": true}',
                           capture_output=True, text=True)
    assert again.returncode == 0
    repo.write("src/new.py", "")
    assert subprocess.run(hook, input=b"{}", capture_output=True).returncode == 0


def test_budget_shows_totals_remaining_and_is_always_ok(repo, capsys):
    run(repo, "init")
    repo.commit()
    capsys.readouterr()
    assert run(repo, "budget") == 0
    out = capsys.readouterr().out
    assert "source 101/101 (0 left)" in out
    assert "tests 10/10 (0 left)" in out
    assert run(repo, "budget", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["groups"]["source"] == {"lines": 101, "ceiling": 101, "remaining": 0} \
        and data["over"] == {}
    # budget never refuses -- it's a report, not a gate, even over budget.
    repo.append("src/util.py", "Y = 2\n")
    capsys.readouterr()
    assert run(repo, "budget") == 0
    assert "source 102/101 (-1 left)" in capsys.readouterr().out


def test_budget_lists_files_near_the_per_file_cap(repo, capsys):
    run(repo, "init", "--max-file-lines", "110")
    repo.commit()
    capsys.readouterr()
    assert run(repo, "budget") == 0
    out = capsys.readouterr().out
    assert "near the per-file cap:" in out
    assert "src/app.py is 100/110 (10 left)" in out
    assert "src/util.py" not in out.split("near the per-file cap:")[1]


def test_budget_hook_warns_only_once_headroom_goes_negative(repo, capsys):
    run(repo, "init")
    repo.commit()
    assert run(repo, "budget", "--hook") == 0
    assert capsys.readouterr().err == ""
    repo.append("src/util.py", "Y = 2\nZ = 3\n")
    assert run(repo, "budget", "--hook") == 2
    err = capsys.readouterr().err
    assert "over budget mid-edit" in err and "source +2" in err


def test_budget_hook_never_blocks_on_a_missing_config(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "budget", "--hook"]) == 0
    assert capsys.readouterr().err == ""
