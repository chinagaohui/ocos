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
    yield
