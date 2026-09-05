"""TextGenerator + MockProvider + PromptBuilder 测试。"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ocos.engines.text_generator import (
    AnthropicProvider,
    GenerationResult,
    LLMProvider,
    MockProvider,
    OpenaiProvider,
    PromptBuilder,
    TextGenerator,
)


# ═══════════════════════════════════════════════════════════════
# MockProvider
# ═══════════════════════════════════════════════════════════════


class TestMockProvider:
    """MockProvider 应返回结构化占位内容。"""

    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        p = MockProvider()
        result = await p.generate("prompt")
        assert isinstance(result, str)
        assert len(result) > 50

    @pytest.mark.asyncio
    async def test_generate_contains_chapter_and_scenes(self):
        p = MockProvider()
        result = await p.generate(
            "Chapter: 5\nprimary_driver: 'mystery'\nintensity: 0.8\npacing_type: accelerate\nemotion_target: suspense"
        )
        assert "第5章" in result or "Chapter" in result
        assert "场景" in result
        assert "叙事元" in result

    @pytest.mark.asyncio
    async def test_driver_affects_title(self):
        p = MockProvider()
        for driver, expected_word in [
            ("relationship", "邂逅"),
            ("survival", "困境"),
            ("mystery", "线索"),
            ("power", "崛起"),
        ]:
            result = await p.generate(f"primary_driver: '{driver}'\nChapter: 1")
            assert expected_word in result, f"Expected '{expected_word}' for driver '{driver}', got: {result[:100]}"

    @pytest.mark.asyncio
    async def test_pacing_and_emotion_in_metadata(self):
        p = MockProvider()
        result = await p.generate(
            "pacing_type: accelerate\nemotion_target: suspense\nChapter: 3\nintensity: 0.7"
        )
        assert "accelerate" in result
        assert "0.7" in result or "suspense" in result

    def test_name(self):
        assert MockProvider().name == "mock"

    def test_available(self):
        assert MockProvider().available is True

    @pytest.mark.asyncio
    async def test_simple_template_works(self):
        p = MockProvider(use_realistic_text=False)
        result = await p.generate("prompt")
        assert "[场景 1" in result or "[场景 2" in result


# ═══════════════════════════════════════════════════════════════
# PromptBuilder
# ═══════════════════════════════════════════════════════════════


class TestPromptBuilder:
    """Prompt 模板构建。"""

    SAMPLE_CONTRACT = {
        "genre": "relationship",
        "primary_driver": "relationship",
        "tone": "romantic",
    }

    SAMPLE_POLICY = {
        "pacing_profile": {"default_pacing_type": "accelerate"},
        "emotion_profile": {"curve": "suspense"},
    }

    SAMPLE_CHAPTER = {
        "chapter": 3,
        "title": "暗流",
        "focus": "主角之间的矛盾升级",
        "scene_types": ["dialogue", "inner"],
        "conflict_type": "emotional",
        "intensity": 0.8,
        "emotion_target": "suspense",
        "dialogue_ratio": 0.4,
        "description_ratio": 0.2,
        "chapter_ending_rule": "cliffhanger",
    }

    def test_build_system_prompt(self):
        system = PromptBuilder.build_system_prompt("relationship", self.SAMPLE_POLICY)
        assert "relationship" in system
        assert "accelerate" in system
        assert "suspense" in system

    def test_build_chapter_prompt(self):
        system, user = PromptBuilder.build_chapter_prompt(
            self.SAMPLE_CHAPTER, self.SAMPLE_CONTRACT, self.SAMPLE_POLICY,
        )
        assert "暗流" in user
        assert "第 3 章" in user or "第3章" in user
        assert "dialogue, inner" in user or "dialogue, inner" in user
        assert "cliffhanger" in user
        assert "0.8" in user

    def test_build_chapter_prompt_defaults(self):
        """缺失字段应有默认值。"""
        system, user = PromptBuilder.build_chapter_prompt(
            {}, {}, {},
        )
        assert "第 1 章" in user or "第1章" in user
        assert "general" in user or "neutral" in system

    def test_build_rewrite_prompt(self):
        system, user = PromptBuilder.build_rewrite_prompt(
            "原章节正文...", "增加对话描写",
        )
        assert "原章节正文..." in user
        assert "增加对话描写" in user
        assert "编辑" in system


# ═══════════════════════════════════════════════════════════════
# TextGenerator
# ═══════════════════════════════════════════════════════════════


class TestTextGenerator:
    """TextGenerator 主类。"""

    @pytest.mark.asyncio
    async def test_generate_chapter_returns_result(self):
        gen = TextGenerator(provider=MockProvider())
        result = await gen.generate_chapter(
            chapter={"chapter": 1, "title": "初遇"},
            contract={"genre": "relationship"},
            policy={},
        )
        assert isinstance(result, GenerationResult)
        assert isinstance(result.text, str)
        assert len(result.text) > 50
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_generate_rewrite_returns_result(self):
        gen = TextGenerator(provider=MockProvider())
        result = await gen.generate_rewrite(
            original_text="原章节...",
            instructions="增加内心独白",
        )
        assert isinstance(result.text, str)

    def test_default_provider_is_mock_when_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            gen = TextGenerator()
            assert gen.provider.name == "mock"

    def test_auto_provider_anthropic_when_key_set(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
            gen = TextGenerator()
            assert gen.provider.name == "anthropic"

    def test_auto_provider_openai_when_key_set(self):
        # 隔离宿主机 ~/.ocos/config.json 的 llm_fallback 段（否则 FailoverProvider
        # 包装后 name 为 failover(openai->openai)，本测试只验证 env 自动选择）
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=True), \
                patch("ocos.engines.text_generator._read_llm_fallback_config",
                      return_value={}):
            gen = TextGenerator()
            assert gen.provider.name == "openai"

    def test_anthropic_takes_precedence(self):
        """两者都有时优先 Anthropic。"""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_API_KEY": "sk-openai-test",
        }, clear=True):
            gen = TextGenerator()
            assert gen.provider.name == "anthropic"

    def test_provider_setter(self):
        gen = TextGenerator(provider=MockProvider())
        new = MagicMock(spec=LLMProvider)
        new.name = "custom"
        gen.provider = new
        assert gen.provider.name == "custom"

    def test_available_mock(self):
        gen = TextGenerator(provider=MockProvider())
        assert gen.available is True

    def test_available_anthropic_without_key(self):
        p = AnthropicProvider()
        assert p.available is False

    def test_available_openai_without_key(self):
        p = OpenaiProvider()
        assert p.available is False


class TestOpenaiProviderHttpClient:
    """S3.13 回归（生产冒烟发现）: http_client 必须是 httpx.AsyncClient 实例。

    openai>=3.8 的 DefaultHttpxClient 实例不被 http_client 参数校验接受
    （报 Invalid http_client argument ... got <class 'openai._DefaultHttpxClient'>），
    必须传显式 httpx.AsyncClient（trust_env=False 即代理隔离）。
    """

    @pytest.mark.asyncio
    async def test_generate_constructs_valid_http_client(self):
        import httpx
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        with patch("openai.AsyncOpenAI") as mock_cls:
            instance = mock_cls.return_value
            instance.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="ok"))]))
            p = OpenaiProvider(api_key="sk-test")
            out = await p.generate("hi", max_tokens=5)
            assert out == "ok"
            kwargs = mock_cls.call_args.kwargs
            assert isinstance(kwargs["http_client"], httpx.AsyncClient)
            assert kwargs["http_client"]._trust_env is False


# ═══════════════════════════════════════════════════════════════
# AnthropicProvider / OpenaiProvider（仅静态检查，不调用 API）
# ═══════════════════════════════════════════════════════════════


class TestAnthropicProvider:
    def test_name(self):
        p = AnthropicProvider()
        assert p.name == "anthropic"

    def test_available_without_key(self):
        p = AnthropicProvider()
        assert p.available is False

    @pytest.mark.asyncio
    async def test_generate_raises_without_key(self):
        p = AnthropicProvider()
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
            await p.generate("prompt")


class TestOpenaiProvider:
    def test_name(self):
        p = OpenaiProvider()
        assert p.name == "openai"

    def test_available_without_key(self):
        p = OpenaiProvider()
        assert p.available is False

    @pytest.mark.asyncio
    async def test_generate_raises_without_key(self, monkeypatch):
        # LLM 接入后 ~/.ocos/config.json 可能带 key — 隔离到无 key 环境
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setattr("ocos.engines.text_generator._read_llm_config",
                            lambda: {})
        p = OpenaiProvider()
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY not set"):
            await p.generate("prompt")


# ═══════════════════════════════════════════════════════════════
# LLMProvider ABC
# ═══════════════════════════════════════════════════════════════


def test_provider_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        LLMProvider()
