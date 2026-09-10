"""ocos/tests 公共夹具。

UX-LLM: LLM key 可以来自 ~/.ocos/config.json — 单元测试默认隔离到
"无 LLM"环境（锁定 Mock/无 key 路径），需要真实 LLM 的测试自行 opt-in。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_llm_config(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("ocos.engines.text_generator._read_llm_config",
                        lambda: {})
    # get_text_generator() 单例可能被先跑的 tests/ 用真实生产配置创建
    # （FailoverProvider.available=True 但 openai 包缺失 → generate 失败），
    # 此处强制重建，确保隔离真正生效。
    monkeypatch.setattr("ocos.engines.text_generator._TEXTGEN_CACHE", {})
    yield


@pytest.fixture(autouse=True)
def _sandbox_switch_default_off(monkeypatch):
    """沙盒白名单开关测试隔离（2026-09-07，见 tests/conftest.py 同名夹具）。"""
    monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")


@pytest.fixture(autouse=True)
def _isolated_autonomy(monkeypatch, tmp_path):
    """隔离 autonomy_level — 生产 override file (~/.ocos/autonomy_level)
    会被 daemon 写为 "0"，污染 pytest 环境。做法:
    1. 把 OCOS_AUTONOMY_OVERRIDE 指向 tmp_path 的临时文件（隔离生产文件）
    2. 临时文件里写 1（默认测试期 autonomy=1 够跑大部分场景）
    3. 测试可用 monkeypatch.setenv 自行覆盖 OCOS_AUTONOMY_OVERRIDE
       （如 test_goal_claim 要测 level=0/2），env 优先级 > 文件默认值。
    注意: 不能 monkeypatch get_autonomy_level() 函数本身 — 那会阻断
    测试级别的 env override（函数硬编码返回值优先于 env）。"""
    import os as _os
    _override = tmp_path / "autonomy_level"
    _override.write_text("1")  # 默认 1 — 大多数测试不关心具体值，能跑就行
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(_override))
    monkeypatch.delenv("OCOS_AUTONOMY_LEVEL", raising=False)
    yield


@pytest.fixture(autouse=True)
def _isolated_active_interaction(monkeypatch):
    """隔离主动交互引擎：
    1. heartbeat 规则返回 None（不发问候，不污染 scanned 计数）
    2. permission gate 改为 fail-closed（guard 缺失 → 拒绝，符合测试期望）
    """
    try:
        from ocos.daemon.active_interaction import (
            ActiveInteractionEngine,
        )
        # heartbeat 规则 → 直接返回 None（测试不需要问候信号）
        monkeypatch.setattr(
            ActiveInteractionEngine, "_rule_heartbeat",
            lambda self, monitor, ctx: None)

        # permission gate → fail-closed（guard/constitution 任一缺失 → False）
        def _checks_pass_fail_closed(self):
            if self.permission_guard is None or self.constitution is None:
                return False
            # 有 guard 才走原始双检逻辑
            context = {"origin": "active_interaction", "channel": "local"}
            try:
                g = self.permission_guard.check("_ACTION", context)
                if not getattr(g, "allowed", False):
                    return False
                c = self.constitution.check_action("_ACTION", context)
                if not getattr(c, "allowed", False):
                    return False
            except Exception:
                return False
            return True
        monkeypatch.setattr(
            ActiveInteractionEngine, "_checks_pass", _checks_pass_fail_closed)
    except Exception:
        pass  # 模块未装配 → 静默跳过
    yield
