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
