"""Phase 21/29 — Git 操作: git_clone / git_commit / git_push。

约束:
  - URL 白名单 (GIT_URL_WHITELIST)
  - 速率限制
  - commit/push 需审批
  - dry_run 模式 (OCOS_DW_DRY_RUN=1) 返回模拟结果

生产模式: OCOS_DW_DRY_RUN=0 时使用 subprocess 执行真实 git 命令。
"""

from __future__ import annotations

import os
import subprocess
import time

from ocos.digital_world.base import DigitalOperation, OperationResult

GIT_URL_WHITELIST: tuple[str, ...] = (
    "https://github.com/",
)

# ── dry_run gate ──
_DRY_RUN = os.getenv("OCOS_DW_DRY_RUN", "1") == "1"
_GIT_TIMEOUT = 120  # git 操作超时秒数

# 简易速率限制
_last_git_call: float = 0.0
_GIT_COOLDOWN = 5.0  # 生产模式下两次 git 操作之间最少间隔


def _check_git_cooldown() -> bool:
    """速率冷却检查。dry_run 模式下跳过。"""
    if _DRY_RUN:
        return True
    global _last_git_call
    now = time.monotonic()
    if now - _last_git_call < _GIT_COOLDOWN:
        return False
    _last_git_call = now
    return True


def _real_git_clone(repo_url: str, target_dir: str) -> tuple[bool, str]:
    """真实 git clone。"""
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, target_dir],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return True, f"Cloned into {target_dir}\n{result.stderr[:500]}"
        return False, f"git clone failed (rc={result.returncode}): {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "git clone timed out"
    except FileNotFoundError:
        return False, "git command not found"


def _real_git_commit(target_dir: str, message: str) -> tuple[bool, str]:
    """真实 git add + commit。"""
    try:
        add = subprocess.run(
            ["git", "-C", target_dir, "add", "-A"],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
        if add.returncode != 0:
            return False, f"git add failed: {add.stderr[:500]}"
        commit = subprocess.run(
            ["git", "-C", target_dir, "commit", "-m", message],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
        if commit.returncode == 0:
            return True, f"Committed: {commit.stdout[:500]}"
        return False, f"git commit failed (rc={commit.returncode}): {commit.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "git commit timed out"
    except FileNotFoundError:
        return False, "git command not found"


def _real_git_push(target_dir: str, branch: str = "main") -> tuple[bool, str]:
    """真实 git push。"""
    try:
        result = subprocess.run(
            ["git", "-C", target_dir, "push", "origin", branch],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return True, f"Pushed to {branch}\n{result.stderr[:500]}"
        return False, f"git push failed (rc={result.returncode}): {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "git push timed out"
    except FileNotFoundError:
        return False, "git command not found"


def _is_git_allowed(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in GIT_URL_WHITELIST)


# ── 公开操作函数 ──


def git_clone(op: DigitalOperation) -> OperationResult:
    """Git clone。dry_run 返回模拟结果，否则执行真实操作。"""
    start = time.monotonic()

    if not _is_git_allowed(op.target):
        return OperationResult.rejected(op.op_id, "Git URL not in whitelist")

    if not _check_git_cooldown():
        return OperationResult.rejected(op.op_id, "git rate cooldown")

    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id, f"Cloned {op.target} (simulated)", duration_ms,
        )

    # 真实 git clone
    target_dir = op.params.get("target_dir", "/tmp/ocos-git-clone")
    ok, msg = _real_git_clone(op.target, target_dir)
    duration_ms = int((time.monotonic() - start) * 1000)
    if ok:
        return OperationResult.success(op.op_id, msg, duration_ms)
    return OperationResult.failure(op.op_id, msg, duration_ms)


def git_commit(op: DigitalOperation) -> OperationResult:
    """Git commit。需 message 参数。"""
    start = time.monotonic()

    if not _check_git_cooldown():
        return OperationResult.rejected(op.op_id, "git rate cooldown")

    # 参数校验：message 是必填项
    if not op.params.get("message"):
        return OperationResult.failure(
            op.op_id, "commit requires message parameter", duration_ms=0,
        )

    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id, "Commit OK (simulated)", duration_ms,
        )

    target_dir = op.params.get("target_dir", ".")
    message = op.params.get("message", "OCOS auto commit")
    ok, msg = _real_git_commit(target_dir, message)
    duration_ms = int((time.monotonic() - start) * 1000)
    if ok:
        return OperationResult.success(op.op_id, msg, duration_ms)
    return OperationResult.failure(op.op_id, msg, duration_ms)


def git_push(op: DigitalOperation) -> OperationResult:
    """Git push。"""
    start = time.monotonic()

    if not _check_git_cooldown():
        return OperationResult.rejected(op.op_id, "git rate cooldown")

    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id, "Push OK (simulated)", duration_ms,
        )

    target_dir = op.params.get("target_dir", ".")
    branch = op.params.get("branch", "main")
    ok, msg = _real_git_push(target_dir, branch)
    duration_ms = int((time.monotonic() - start) * 1000)
    if ok:
        return OperationResult.success(op.op_id, msg, duration_ms)
    return OperationResult.failure(op.op_id, msg, duration_ms)
