# Copyright 2026 Krishan Subudhi
# SPDX-License-Identifier: Apache-2.0
import os
import subprocess

import pytest


class Repo:
    """A throwaway git repo with helpers for writing code and committing."""

    def __init__(self, path):
        self.path = str(path)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args):
        return subprocess.run(["git", "-C", self.path, *args], check=True,
                              capture_output=True, text=True).stdout

    def write(self, rel, text):
        full = os.path.join(self.path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(text)

    def append(self, rel, text):
        with open(os.path.join(self.path, rel), "a") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.path, rel)) as fh:
            return fh.read()

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)
        return self.git("rev-parse", "HEAD").strip()


def funcs(count, prefix="f"):
    """`count` two-line functions: 2*count non-blank lines."""
    return "".join("def %s%d():\n    return %d\n\n" % (prefix, i, i)
                   for i in range(count))


@pytest.fixture
def repo(tmp_path):
    r = Repo(tmp_path)
    r.write("src/app.py", funcs(50))           # 100 lines
    r.write("src/util.py", "X = 1\n")          # 1 line
    r.write("tests/test_app.py", funcs(5, "test_"))  # 10 lines
    r.write("README.md", "docs do not count\n")
    return r
