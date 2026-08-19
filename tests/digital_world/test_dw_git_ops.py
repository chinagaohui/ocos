"""Phase 29 — Gate Tests: git_ops。

验证:
  29-G01: git_clone with whitelist URL
  29-G02: git_clone rejected for bad URL
  29-G03: git_commit requires message
  29-G04: git_push with approval
"""

import pytest
from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.git_ops import git_clone, git_commit, git_push


def _op(op_type: str, target: str, approval_id: str | None = None, **params):
    return DigitalOperation.create(op_type, target, "G1", params=params, approval_id=approval_id)


# ── 29-G01: git_clone whitelist ───────────────────────────────────

def test_git_clone_allowed():
    op = _op("git_clone", "https://github.com/user/repo.git")
    result = git_clone(op)
    assert result.status == "success"


# ── 29-G02: git_clone rejected ────────────────────────────────────

def test_git_clone_not_whitelisted():
    op = _op("git_clone", "http://evil.com/repo.git")
    result = git_clone(op)
    assert result.status == "rejected"


# ── 29-G03: git_commit requires message ───────────────────────────

def test_git_commit_requires_message():
    op = _op("git_commit", ".", approval_id="A1")
    result = git_commit(op)
    assert result.status == "failure"


def test_git_commit_with_message():
    op = _op("git_commit", ".", approval_id="A1", message="fix: bug")
    result = git_commit(op)
    assert result.status == "success"


# ── 29-G04: git_push ──────────────────────────────────────────────

def test_git_push():
    op = _op("git_push", "origin", approval_id="A1", branch="main")
    result = git_push(op)
    assert result.status == "success"
