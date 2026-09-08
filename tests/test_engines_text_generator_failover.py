"""FailoverProvider 单元测试 — P3-429 第二 provider 故障转移。"""

import asyncio
import json

import pytest

from ocos.engines.text_generator import (
    FailoverProvider,
    LLMProvider,
    TextGenerator,
)


class StubProvider(LLMProvider):
    """可编程 stub — failures 队列非空时依次抛出，否则返回模板文本。"""

    def __init__(self, name: str, failures: list[Exception] | None = None,
                 text: str = "ok") -> None:
        self._name = name
        self._failures = list(failures or [])
        self.text = text
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return True

    async def generate(self, prompt, system_prompt=None,
                       temperature=0.8, max_tokens=2000) -> str:
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return self.text


class RateLimitError(Exception):
    """模拟 openai.RateLimitError（带 status_code 的 API 错误）。"""

    status_code = 429


class UnavailableStub(StubProvider):
    @property
    def available(self) -> bool:
        return False


class StreamStub(StubProvider):
    """带 generate_stream 的 stub（流式网关拦截测试用）。"""

    async def generate_stream(self, prompt, system_prompt=None,
                              temperature=0.8, max_tokens=2000,
                              on_chunk=None) -> str:
        out = await self.generate(prompt, system_prompt,
                                  temperature, max_tokens)
        if on_chunk:
            on_chunk(out)
        return out


def test_primary_ok_no_failover():
    primary = StubProvider("primary", text="A")
    fallback = StubProvider("fallback", text="B")
    out = asyncio.run(FailoverProvider(primary, fallback).generate("hi"))
    assert out == "A"
    assert primary.calls == 1 and fallback.calls == 0


def test_failover_on_rate_limit():
    primary = StubProvider("primary", failures=[RateLimitError("429")])
    fallback = StubProvider("fallback", text="B")
    out = asyncio.run(FailoverProvider(primary, fallback).generate("hi"))
    assert out == "B"
    assert primary.calls == 1 and fallback.calls == 1


def test_failover_on_generic_error():
    primary = StubProvider("primary", failures=[ConnectionError("reset")])
    fallback = StubProvider("fallback", text="B")
    out = asyncio.run(FailoverProvider(primary, fallback).generate("hi"))
    assert out == "B"


def test_both_fail_raises_fallback_error():
    primary = StubProvider("primary", failures=[RateLimitError("429")])
    fallback = StubProvider("fallback", failures=[RuntimeError("down")])
    with pytest.raises(RuntimeError, match="down"):
        asyncio.run(FailoverProvider(primary, fallback).generate("hi"))


def test_cancellation_passthrough():
    """取消/中断必须透传 — 不得吞掉转投 fallback。"""

    async def run():
        primary = StubProvider("primary",
                               failures=[asyncio.CancelledError()])
        fallback = StubProvider("fallback", text="B")
        await FailoverProvider(primary, fallback).generate("hi")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


def test_unavailable_primary_direct_fallback():
    primary = UnavailableStub("primary")
    fallback = StubProvider("fallback", text="B")
    out = asyncio.run(FailoverProvider(primary, fallback).generate("hi"))
    assert out == "B"
    assert primary.calls == 0


def test_name_and_available():
    fp = FailoverProvider(StubProvider("p"), StubProvider("f"))
    assert fp.name == "failover(p->f)"
    assert fp.available


# ── GATEWAY-FAILOVER（2026-09-07）：HTTP 200 + 拦截文本也切换 ──

def test_gateway_signal_detection():
    """拦截特征大小写不敏感；正常文本不误伤。"""
    hit = FailoverProvider._hit_gateway
    assert hit("请求被网关拒绝: CMD_INJECTION 规则触发")
    assert hit("content filtering policy violation")
    assert hit("This violates our Usage Policy.")
    assert hit("detected PROMPT_INJECTION attempt")
    assert not hit("磁盘 62%，内存 13G，负载 2.77")
    assert not hit("")
    assert not hit(None)


def test_failover_on_gateway_block_text():
    """primary 返回 200 + 网关拦截文本 → 切 fallback（非异常路径）。"""
    primary = StubProvider(
        "primary", text="shell 命令被权限网关拦截（触发 CMD_INJECTION 与 SSRF 规则）")
    fallback = StubProvider("fallback", text="df: / 62% used")
    out = asyncio.run(FailoverProvider(primary, fallback).generate("hi"))
    assert out == "df: / 62% used"
    assert primary.calls == 1 and fallback.calls == 1


def test_gateway_block_propagates_fallback_meta():
    """拦截切换后 last_model 应来自 fallback 而非 primary。"""
    primary = StreamStub("primary", text="CMD_INJECTION blocked")
    fallback = StreamStub("fallback", text="fine")
    fp = FailoverProvider(primary, fallback)
    fp._fallback.last_model = "deepseek-chat"
    out = asyncio.run(fp.generate("hi"))
    assert out == "fine"
    assert fp.last_model == "deepseek-chat"


def test_gateway_block_stream_failover():
    """流式路径同样检测拦截文本并切换。"""
    primary = StreamStub("primary", text="blocked by content filtering policy")
    fallback = StreamStub("fallback", text="stream-ok")
    out = asyncio.run(
        FailoverProvider(primary, fallback).generate_stream("hi"))
    assert out == "stream-ok"
    assert fallback.calls == 1


def test_auto_provider_config_gate(tmp_path, monkeypatch):
    """config.json 无 llm_fallback 段 → 单 provider；有 → FailoverProvider。"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = home / ".ocos" / "config.json"
    cfg.parent.mkdir()

    cfg.write_text(json.dumps({
        "llm": {"api_key": "k1", "base_url": "https://p.example/v1",
                "model": "m1"},
    }), encoding="utf-8")
    p = TextGenerator._auto_provider()
    assert type(p).__name__ == "OpenaiProvider"

    cfg.write_text(json.dumps({
        "llm": {"api_key": "k1", "base_url": "https://p.example/v1",
                "model": "m1"},
        "llm_fallback": {"api_key": "k2", "base_url": "https://f.example/v1",
                         "model": "m2"},
    }), encoding="utf-8")
    p2 = TextGenerator._auto_provider()
    assert isinstance(p2, FailoverProvider)
    assert p2.name == "failover(openai->openai)"
    # fallback provider 收到 llm_fallback 段的显式配置（非 llm 主段）
    assert p2._fallback._api_key == "k2"
    assert p2._fallback._base_url == "https://f.example/v1"
    assert p2._fallback._model == "m2"
    # primary 不受 fallback 段影响
    assert p2._primary._api_key == "k1"
