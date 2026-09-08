"""UX-J+: 沙盒无害设备文件放行（/dev/null 等）回归测试。

背景: "> /dev/null 2>&1" 是脚本静默输出的惯用法，/dev 前缀一刀切
误拦导致目标假性失败。放行 null/zero/full/random/urandom 五个
无凭据无害设备；/dev 其余路径（磁盘、TTY 等）仍严格拦截。
"""
import tempfile
from pathlib import Path

import pytest

from ocos.autonomous_runtime.action_dispatcher import ActionType
from ocos.execution.bridge import DecisionBridge, DispatchedAction


@pytest.fixture
def bridge():
    with tempfile.TemporaryDirectory() as td:
        yield DecisionBridge(db_path=str(Path(td) / "t.db"))


def _run(bridge, command: str) -> dict:
    action = DispatchedAction(ActionType.RUN_COMMAND, target="sandbox",
                              payload={"command": command})
    return bridge._handler_run_command(action)


class TestHarmlessDevDevices:
    def test_redirect_to_dev_null_allowed(self, bridge):
        r = _run(bridge, "echo test > /dev/null 2>&1")
        assert "敏感路径" not in (r.get("block_reason") or "")

    def test_cat_dev_null_allowed(self, bridge):
        r = _run(bridge, "cat /dev/null")
        assert "敏感路径" not in (r.get("block_reason") or "")

    def test_dev_zero_allowed(self, bridge):
        r = _run(bridge, "head -c 8 /dev/zero")
        assert "敏感路径" not in (r.get("block_reason") or "")

    def test_disk_device_still_blocked(self, bridge):
        r = _run(bridge, "cat /dev/sda")
        assert r.get("blocked") is True
        assert "敏感路径" in (r.get("block_reason") or "")

    def test_dev_tty_still_blocked(self, bridge):
        r = _run(bridge, "cat /dev/tty0")
        assert r.get("blocked") is True
        assert "敏感路径" in (r.get("block_reason") or "")

    def test_shadow_file_still_blocked(self, bridge):
        r = _run(bridge, "cat /etc/shadow")
        assert r.get("blocked") is True
        assert "敏感路径" in (r.get("block_reason") or "")

    def test_public_readonly_regression(self, bridge):
        # 原有精确放行不受影响
        r = _run(bridge, "cat /etc/os-release /proc/cpuinfo")
        assert "敏感路径" not in (r.get("block_reason") or "")

    def test_executed_output_still_returned(self, bridge):
        # 放行后命令真实执行且输出正常返回
        r = _run(bridge, "echo ocos-devnull-check > /dev/null 2>&1; echo visible")
        assert r.get("ok") is True
        assert "visible" in (r.get("stdout") or "")
