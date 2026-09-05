"""S2.2: auto 审批模式启动警告横幅回归（评审版 R3）。"""

from __future__ import annotations

import pytest

from ocos.daemon import DaemonState, ResidentRuntime


class _FakeRuntime:
    def boot(self):
        pass


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
    rt = ResidentRuntime.__new__(ResidentRuntime)
    rt._lock = __import__("threading").Lock()
    rt._state = DaemonState.STOPPED
    rt._stop_event = __import__("threading").Event()
    rt._runtime = _FakeRuntime()
    rt._domain_goal_store = None
    rt._kernel = None
    return rt


def test_auto_mode_prints_warning(runtime, monkeypatch, capsys):
    monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")  # S3.13: 默认已切 ask，auto 需显式设置
    monkeypatch.setattr(runtime, "_kernel", None)
    # kernel None 会在后续 getattr 崩溃——只验证横幅，捕获异常
    try:
        runtime.start()
    except Exception:
        pass
    assert "OCOS_APPROVAL_MODE=auto" in capsys.readouterr().out


def test_ask_mode_no_warning(runtime, monkeypatch, capsys):
    monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
    try:
        runtime.start()
    except Exception:
        pass
    assert "OCOS_APPROVAL_MODE=auto" not in capsys.readouterr().out
