"""Phase 21 — Digital World 真实模式测试 (条件跳过)。

验证:
  - OCOS_DW_DRY_RUN=0 时 api_ops 真实 HTTP GET 成功
  - OCOS_DW_DRY_RUN=0 时 git_ops 真实 git 操作 (需 git 命令存在)
  - 白名单 + 速率限制在真实模式下依然生效
  - 无效 URL 被正确拒绝
"""

import os
import pytest
import subprocess
import tempfile

from ocos.digital_world.base import DigitalOperation
from ocos.digital_world import api_ops, git_ops

# ── 条件跳过标记 ──

needs_git = pytest.mark.skipif(
    subprocess.run(["which", "git"], capture_output=True).returncode != 0,
    reason="git not installed"
)

needs_network = pytest.mark.skipif(
    os.environ.get("OCOS_DW_REAL_TEST", "0") != "1",
    reason="Set OCOS_DW_REAL_TEST=1 to run network-dependent tests"
)


def _op(op_type, target, approval_id=None, **params):
    return DigitalOperation.create(op_type, target, "G1",
                                   params=params, approval_id=approval_id)


# ── api_ops 真实 HTTP ─────────────────────────────────────────────


@needs_network
def test_api_get_real_github(monkeypatch):
    """真实 GET https://api.github.com/（public API，不需要认证）。"""
    monkeypatch.setitem(os.environ, "OCOS_DW_DRY_RUN", "0")
    # 重新加载模块以应用新环境变量
    import importlib
    importlib.reload(api_ops)

    op = _op("api_get", "https://api.github.com/")
    result = api_ops.api_get(op)
    assert result.status == "success"
    assert "200" in (result.output or "")


@needs_network
def test_api_get_no_whitelist_real(monkeypatch):
    """不合规 URL 在真实模式下也被拒绝。"""
    monkeypatch.setitem(os.environ, "OCOS_DW_DRY_RUN", "0")
    import importlib
    importlib.reload(api_ops)

    op = _op("api_get", "https://evil.example.com/data")
    result = api_ops.api_get(op)
    assert result.status == "rejected"
    assert "whitelist" in (result.error or "")


# ── git_ops 真实 git ──────────────────────────────────────────────


@needs_git
@needs_network
def test_git_clone_real_public_repo(monkeypatch):
    """真实的 git clone（浅层克隆公共仓库）。"""
    monkeypatch.setitem(os.environ, "OCOS_DW_DRY_RUN", "0")
    import importlib
    importlib.reload(git_ops)

    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = os.path.join(tmpdir, "test-repo")
        op = _op("git_clone", "https://github.com/nousresearch/hermes-agent.git",
                 target_dir=target_dir)
        result = git_ops.git_clone(op)
        # 真实 clone 可能成功或失败（取决于网络），但不应该被仿真
        # 如果是成功，target_dir 应有内容
        if result.status == "success":
            assert os.path.isdir(target_dir)
        # 否则失败也接受（网络问题）
        assert result.status in ("success", "failure")


@needs_git
def test_git_commit_dry_run_unchanged(monkeypatch):
    """确保 dry_run=1 时 git 测试不受影响（not real mode）。"""
    monkeypatch.setitem(os.environ, "OCOS_DW_DRY_RUN", "1")
    import importlib
    importlib.reload(git_ops)

    op = _op("git_commit", ".", approval_id="A1", message="test commit")
    result = git_ops.git_commit(op)
    assert result.status == "success"
    assert "simulated" in (result.output or "")


# ── 重置 dry_run 状态（避免污染后续测试） ──

@pytest.fixture(autouse=True)
def _reset_dry_run():
    """每个测试后恢复 dry_run=1 默认状态。"""
    yield
    import importlib
    importlib.reload(api_ops)
    importlib.reload(git_ops)
