"""TextGenerator — LLM 叙事文本生成抽象层。

支持可插拔 Provider：
  - MockProvider:    开发/测试，无需 API 密钥
  - AnthropicProvider: Anthropic API（需要 ANTHROPIC_API_KEY 环境变量）
  - OpenaiProvider:   OpenAI API（需要 OPENAI_API_KEY 环境变量）

设计原则：
  - 异步安全（asyncio-compatible）
  - 无硬编码密钥（仅环境变量）
  - Prompt 模板化 + 上下文注入
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from ocos.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Provider 抽象
# ═══════════════════════════════════════════════════════════════


class LLMProvider(ABC):
    """LLM 提供商抽象基类。"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        """异步生成文本。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """提供商名称。"""
        ...

    @property
    def available(self) -> bool:
        """是否可用（API 密钥已配置）。"""
        return True

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """默认流式实现 — 一次性 generate 并单块回调；支持流式的子类覆写。

        返回拼接后的完整文本。on_chunk 每收到一段增量文本即被调用（同步）。
        """
        text = await self.generate(prompt, system_prompt=system_prompt,
                                   temperature=temperature, max_tokens=max_tokens)
        if on_chunk is not None:
            on_chunk(text)
        return text


class MockProvider(LLMProvider):
    """Mock 提供商 — 无需 API 密钥，返回结构化占位内容。"""

    MOCK_CHAPTER_TEMPLATE = """## 第{chapter}章：{title}

### 场景一：{scene_type_1}
{description_1}

### 场景二：{scene_type_2}
{description_2}

### 场景三：{scene_type_3}
{description_3}

### 叙事元
- 节奏：{pacing}
- 强度：{intensity}/1.0
- 情感目标：{emotion}"""

    MOCK_TITLES = {
        "relationship": [
            "邂逅", "暗流", "转折", "告白", "分离",
            "重逢", "抉择", "和解", "承诺", "永恒",
        ],
        "survival": [
            "困境", "突围", "陷阱", "盟友", "背叛",
            "反击", "牺牲", "决战", "重生", "黎明",
        ],
        "mystery": [
            "线索", "疑云", "追查", "真相", "反转",
            "博弈", "揭露", "暗线", "收网", "结局",
        ],
        "power": [
            "崛起", "暗算", "布局", "较量", "联盟",
            "危机", "破局", "巅峰", "代价", "传承",
        ],
    }

    def __init__(self, use_realistic_text: bool = True) -> None:
        self._use_realistic = use_realistic_text

    @property
    def name(self) -> str:
        return "mock"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        """生成 Mock 章节内容。"""
        await asyncio.sleep(0.01)  # 模拟 API 延迟

        # 从 prompt 中提取关键参数
        lines = prompt.split("\n")
        chapter = 1
        driver = "relationship"
        intensity = 0.5
        pacing = "balanced"
        emotion = "neutral"

        for line in lines:
            lc = line.lower()
            if "chapter" in lc and ":" in line:
                try:
                    chapter = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            if "primary_driver" in lc and ":" in line:
                driver = line.split(":")[-1].strip().strip("'\"")
            if "intensity" in lc and ":" in line:
                try:
                    intensity = float(line.split(":")[-1].strip())
                except ValueError:
                    pass
            if "pacing_type" in lc and ":" in line:
                pacing = line.split(":")[-1].strip().strip("'\"")
            if "emotion_target" in lc and ":" in line:
                emotion = line.split(":")[-1].strip().strip("'\"")

        # 选择标题
        titles = self.MOCK_TITLES.get(driver, self.MOCK_TITLES["relationship"])
        title_idx = (chapter - 1) % len(titles)
        title = titles[title_idx]

        # 场景描述模板
        scene_templates = {
            "dialogue": "一段深入的对话展示了角色之间的权力博弈与情感张力。",
            "action": f"动态场景推动剧情向前发展，冲突强度 {intensity:.1f}。",
            "inner": "内心独白揭示角色的真实动机与情感变化。",
            "description": "环境描写营造氛围，为接下来的情节做铺垫。",
            "exposition": f"以{pacing}节奏推进主线，揭示新的信息。",
            "reflection": "角色对已有认知进行反思，情感状态：{emotion}。",
        }

        scene_types = ["dialogue", "action", "inner"]
        if self._use_realistic:
            descriptions = [
                scene_templates.get(t, scene_templates["exposition"])
                for t in scene_types
            ]
        else:
            descriptions = [
                f"[场景 {i+1} — {t}]" for i, t in enumerate(scene_types)
            ]

        return self.MOCK_CHAPTER_TEMPLATE.format(
            chapter=chapter,
            title=title,
            scene_type_1=scene_types[0].capitalize(),
            description_1=descriptions[0],
            scene_type_2=scene_types[1].capitalize(),
            description_2=descriptions[1],
            scene_type_3=scene_types[2].capitalize(),
            description_3=descriptions[2],
            pacing=pacing,
            intensity=intensity,
            emotion=emotion,
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 提供商。"""

    def __init__(self) -> None:
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        if not self.available:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed: pip install anthropic")

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        kwargs: dict[str, Any] = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        return response.content[0].text


class OpenaiProvider(LLMProvider):
    """OpenAI API 提供商（兼容 DeepSeek 等OpenAI-compatible 端点）。

    配置优先级: 构造参数 > 环境变量 > ~/.ocos/config.json 的 llm 段
    （{"llm": {"api_key", "base_url", "model"}}）。
    """

    def __init__(self, api_key: str = "", base_url: str = "",
                 model: str = "") -> None:
        cfg = _read_llm_config()
        self._api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")
                         or cfg.get("api_key", ""))
        self._base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "")
                          or cfg.get("base_url", "") or None)
        self._model = (model or os.environ.get("OPENAI_MODEL", "")
                       or cfg.get("model", "") or "gpt-4o")
        # 最近一次调用的模型与 token 用量（供状态栏展示；TUI-OpenClaw 对齐）
        self.last_model = self._model
        self.last_usage: dict = {}

    @property
    def name(self) -> str:
        return "openai"

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY not set")

        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            raise RuntimeError("openai package not installed: pip install openai")

        # S3.7 (白皮书 P3): 禁用系统代理改由 SDK 客户端 trust_env=False
        # 实现——原 pop/restore 进程级环境变量在并发下互相踩踏（无锁）。
        # S3.13 修正: openai>=3.8 的 DefaultHttpxClient 实例不被 http_client
        # 参数校验接受（非 httpx.AsyncClient 子类），回退显式 httpx.AsyncClient
        # （trust_env=False 即代理隔离，无进程级 env 变更）。
        client = AsyncOpenAI(
            api_key=self._api_key, base_url=self._base_url,
            http_client=httpx.AsyncClient(trust_env=False, timeout=120.0))
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.last_model = self._model
        u = getattr(response, "usage", None)
        self.last_usage = ({"prompt": getattr(u, "prompt_tokens", 0) or 0,
                            "completion": getattr(u, "completion_tokens", 0) or 0}
                           if u else {})
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """OpenAI 兼容端点流式生成 — 逐增量块回调 on_chunk，返回拼接全文。"""
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY not set")
        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            raise RuntimeError("openai package not installed: pip install openai")

        client = AsyncOpenAI(
            api_key=self._api_key, base_url=self._base_url,
            http_client=httpx.AsyncClient(trust_env=False, timeout=120.0))
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        parts: list[str] = []
        self.last_model = self._model
        stream = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if not chunk.choices:
                # 末尾 usage 块（choices 为空）：捕获 token 用量
                u = getattr(chunk, "usage", None)
                if u is not None:
                    self.last_usage = {
                        "prompt": getattr(u, "prompt_tokens", 0) or 0,
                        "completion": getattr(u, "completion_tokens", 0) or 0}
                continue
            delta = (chunk.choices[0].delta.content or "")
            if delta:
                parts.append(delta)
                if on_chunk is not None:
                    on_chunk(delta)
        return "".join(parts)


# ═══════════════════════════════════════════════════════════════
# Failover Provider（P3-429: 第二 provider 故障转移）
# ═══════════════════════════════════════════════════════════════


class FailoverProvider(LLMProvider):
    """主备故障转移 — primary 限流(429)/网络/服务端错误时透明切换 fallback。

    每次请求先走 primary（自身已含 SDK 级退避重试）；重试耗尽仍失败时，
    同一请求改由 fallback 完成。fallback 也失败则抛出 fallback 的错误。
    未配置 fallback（config.json 无 llm_fallback 段）时不会被构造，
    行为与单 provider 完全一致。

    GATEWAY-FAILOVER（2026-09-07）：部分上游平台（如 Agnes apihub）对
    shell 命令类内容返回 HTTP 200 + 拦截说明文本（CMD_INJECTION/SSRF
    规则），不抛异常 → 无法走 except 分支。此处对 primary 返回文本
    做拦截特征检测，命中即视为失败切换 fallback，保证命令执行类
    prompt 在无网关的备用 provider 上正常完成。
    """

    # 上游网关/内容策略拦截的特征信号（大小写不敏感）。要求足够特异，
    # 正常对话几乎不会输出这些术语组合。
    _GATEWAY_SIGNALS = (
        "CMD_INJECTION",          # Agnes 网关命令注入规则名
        "prompt_injection",       # 通用注入拦截
        "content filtering policy",
        "violates our usage policy",
        "violates our content policy",
    )

    @staticmethod
    def _hit_gateway(text: str) -> bool:
        if not text:
            return False
        low = text.lower()
        return any(sig.lower() in low for sig in FailoverProvider._GATEWAY_SIGNALS)

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_model = ""
        self.last_usage: dict = {}

    def _propagate(self, src: LLMProvider) -> None:
        """把实际执行方的 last_model/last_usage 冒泡到外层。"""
        self.last_model = getattr(src, "last_model", "")
        self.last_usage = getattr(src, "last_usage", {})

    @property
    def name(self) -> str:
        return f"failover({self._primary.name}->{self._fallback.name})"

    @property
    def available(self) -> bool:
        return self._primary.available or self._fallback.available

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        import asyncio
        kwargs = {"system_prompt": system_prompt,
                  "temperature": temperature, "max_tokens": max_tokens}
        if not self._primary.available:
            out = await self._fallback.generate(prompt, **kwargs)
            self._propagate(self._fallback)
            return out
        try:
            out = await self._primary.generate(prompt, **kwargs)
            if self._hit_gateway(out):
                logger.warning(
                    "Primary provider '%s' returned gateway-block text, "
                    "failover to '%s'", self._primary.name, self._fallback.name)
                out = await self._fallback.generate(prompt, **kwargs)
                self._propagate(self._fallback)
                return out
            self._propagate(self._primary)
            return out
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise  # 取消/中断必须透传，不得转投 fallback
        except Exception as exc:
            logger.warning(
                "Primary provider '%s' failed (%s: %s), failover to '%s'",
                self._primary.name, type(exc).__name__, str(exc)[:120],
                self._fallback.name)
            out = await self._fallback.generate(prompt, **kwargs)
            self._propagate(self._fallback)
            return out

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """流式故障转移 — 封装 generate_stream 的 primary→fallback。"""
        import asyncio
        kwargs = {"system_prompt": system_prompt,
                  "temperature": temperature, "max_tokens": max_tokens,
                  "on_chunk": on_chunk}
        if not self._primary.available:
            out = await self._fallback.generate_stream(prompt, **kwargs)
            self._propagate(self._fallback)
            return out
        try:
            out = await self._primary.generate_stream(prompt, **kwargs)
            if self._hit_gateway(out):
                logger.warning(
                    "Primary provider '%s' stream returned gateway-block "
                    "text, failover to '%s'",
                    self._primary.name, self._fallback.name)
                out = await self._fallback.generate_stream(prompt, **kwargs)
                self._propagate(self._fallback)
                return out
            self._propagate(self._primary)
            return out
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            logger.warning(
                "Primary provider '%s' stream failed (%s: %s), failover to '%s'",
                self._primary.name, type(exc).__name__, str(exc)[:120],
                self._fallback.name)
            out = await self._fallback.generate_stream(prompt, **kwargs)
            self._propagate(self._fallback)
            return out


# ═══════════════════════════════════════════════════════════════
# Prompt 构建器
# ═══════════════════════════════════════════════════════════════


class PromptBuilder:
    """将 Narrative Contract + Policy + 章节规划 转化为 LLM Prompt。"""

    SYSTEM_TEMPLATE = """你是一位专业的{genre}小说作家。你的任务是创作出符合以下要求的高质量小说章节。

写作风格：
- 类型：{genre}
- 叙事节奏：{pacing}
- 情感基调：{emotion}
- 默认使用中文写作"""

    CHAPTER_TEMPLATE = """请创作小说的第 {chapter} 章：{title}

## 章节规划

{chapter_plan}

## {genre} 写作约束

- 叙事驱动：{driver}
- 章节节奏：{pacing}
- 强度级别：{intensity}/1.0
- 情感目标：{emotion}
- 对话比例：{dialogue_ratio}
- 描述比例：{description_ratio}
- 章节结尾风格：{ending_rule}

## 格式要求

请输出以下格式：
1. 章节正文（不少于 500 字）
2. 叙事标签（情感曲线位置、节奏标记）"""

    REWRITE_TEMPLATE = """请重写以下章节内容。

## 原始章节

{original_text}

## 修改要求

{instructions}

## 格式要求

保持章节风格一致，仅修改指定的内容。
输出完整的重写后章节。"""

    @staticmethod
    def build_system_prompt(genre: str, policy: dict[str, Any]) -> str:
        """构建系统提示。"""
        pacing = policy.get("pacing_profile", {}).get("default_pacing_type", "balanced")
        emotion = policy.get("emotion_profile", {}).get("curve", "neutral")
        return PromptBuilder.SYSTEM_TEMPLATE.format(
            genre=genre,
            pacing=pacing,
            emotion=emotion,
        )

    @staticmethod
    def build_chapter_prompt(
        chapter: dict[str, Any],
        contract: dict[str, Any],
        policy: dict[str, Any],
    ) -> tuple[str, str]:
        """构建章节生成提示。

        Returns:
            (system_prompt, user_prompt)
        """
        genre = contract.get("genre", contract.get("primary_driver", "general"))
        driver = contract.get("primary_driver", "relationship")
        pacing = policy.get("pacing_profile", {}).get("default_pacing_type", "balanced")
        emotion = policy.get("emotion_profile", {}).get("curve", "neutral")

        system = PromptBuilder.build_system_prompt(genre, policy)

        # 章节规划摘要
        plan_lines = [f"- 焦点：{chapter.get('focus', chapter.get('title', '通用'))}"]
        scene_types = chapter.get("scene_types", [])
        if scene_types:
            plan_lines.append(f"- 场景类型：{', '.join(scene_types)}")
        plan_lines.append(f"- 冲突类型：{chapter.get('conflict_type', 'general')}")

        chapter_plan = "\n".join(plan_lines)

        user = PromptBuilder.CHAPTER_TEMPLATE.format(
            chapter=chapter.get("chapter", 1),
            title=chapter.get("title", f"第{chapter.get('chapter', 1)}章"),
            chapter_plan=chapter_plan,
            genre=genre,
            driver=driver,
            pacing=pacing,
            intensity=chapter.get("intensity", 0.5),
            emotion=chapter.get("emotion_target", emotion),
            dialogue_ratio=chapter.get("dialogue_ratio", 0.35),
            description_ratio=chapter.get("description_ratio", 0.25),
            ending_rule=chapter.get("chapter_ending_rule", "natural"),
        )
        return system, user

    @staticmethod
    def build_rewrite_prompt(
        original_text: str,
        instructions: str,
    ) -> tuple[str, str]:
        """构建重写提示。"""
        system = "你是一位专业的小说编辑，擅长在不改变原文风格的前提下修改指定内容。"
        user = PromptBuilder.REWRITE_TEMPLATE.format(
            original_text=original_text,
            instructions=instructions,
        )
        return system, user


# ═══════════════════════════════════════════════════════════════
# TextGenerator 主类
# ═══════════════════════════════════════════════════════════════


@dataclass
class GenerationResult:
    """生成结果。"""
    text: str
    provider: str
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


_TEXTGEN_CACHE: dict = {}

def get_text_generator() -> "TextGenerator":
    """P3-2: TextGenerator 实例缓存 — 此前每个调用点每 tick 重建
    （Provider 重初始化 + 日志噪音）。"""
    global _TEXTGEN_CACHE
    if "instance" not in _TEXTGEN_CACHE:
        _TEXTGEN_CACHE["instance"] = TextGenerator()
    return _TEXTGEN_CACHE["instance"]


def _read_llm_config() -> dict:
    """读取 ~/.ocos/config.json 的 llm 段（环境变量优先于配置文件）。"""
    return _read_config_block("llm")


def _read_llm_fallback_config() -> dict:
    """读取 ~/.ocos/config.json 的 llm_fallback 段（P3-429 故障转移备用 provider）。

    格式: {"llm_fallback": {"api_key", "base_url", "model"}} — 段缺失或
    api_key 为空表示未启用故障转移，行为与单 provider 一致。
    """
    return _read_config_block("llm_fallback")


def _read_config_block(block: str) -> dict:
    path = os.path.join(os.path.expanduser("~"), ".ocos", "config.json")
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return (json.load(f) or {}).get(block, {}) or {}
    except (OSError, ValueError):
        return {}


class TextGenerator:
    """文本生成主类 — 管理 Provider + Prompt 构建。"""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._provider = provider or self._auto_provider()
        self._prompt_builder = prompt_builder or PromptBuilder()
        logger.info(f"TextGenerator initialized with provider={self._provider.name}")

    @staticmethod
    def _auto_provider() -> LLMProvider:
        """自动选择可用提供商（env 或 ~/.ocos/config.json 任一有 key 即启用）。"""
        if os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicProvider()
        if (os.environ.get("OPENAI_API_KEY")
                or _read_llm_config().get("api_key")):
            primary: LLMProvider = OpenaiProvider()
            # P3-429: 配置了 llm_fallback 段（含 api_key）则启用故障转移
            fb = _read_llm_fallback_config()
            if fb.get("api_key"):
                fallback = OpenaiProvider(
                    api_key=fb.get("api_key", ""),
                    base_url=fb.get("base_url", ""),
                    model=fb.get("model", ""),
                )
                logger.info("LLM failover enabled: %s -> %s",
                            primary.name, fallback.name)
                return FailoverProvider(primary, fallback)
            return primary
        logger.info("No API keys found, using MockProvider")
        return MockProvider()

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @provider.setter
    def provider(self, p: LLMProvider) -> None:
        self._provider = p
        logger.info(f"TextGenerator switched to provider={p.name}")

    @property
    def available(self) -> bool:
        """是否有可用的 LLM 提供商。"""
        return self._provider.available

    def generate(
        self,
        prompt: str | None = None,
        user_prompt: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> str:
        """通用 Q&A 接口 — 同步包装 provider.generate.

        供 LLMTutor / 认知循环等非写作管线模块调用.
        写作管线请用 generate_chapter / generate_rewrite.

        兼容两种调用风格:
            generate("问什么")
            generate(user_prompt="问什么", system_prompt="你是专家")
        """
        import asyncio

        actual_prompt = user_prompt if user_prompt is not None else prompt
        if not actual_prompt:
            logger.warning("TextGenerator.generate: empty prompt")
            return ""

        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self._provider.generate(
                        actual_prompt, system_prompt, temperature, max_tokens,
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            logger.warning("TextGenerator.generate failed: %s", e)
            return ""

    async def generate_chapter(
        self,
        chapter: dict[str, Any],
        contract: dict[str, Any],
        policy: dict[str, Any],
        temperature: float = 0.8,
    ) -> GenerationResult:
        """从合约 + 政策 + 章节规划生成一章内容。"""
        system, prompt = self._prompt_builder.build_chapter_prompt(
            chapter, contract, policy,
        )
        text = await self._provider.generate(
            prompt=prompt,
            system_prompt=system,
            temperature=temperature,
            max_tokens=2000,
        )
        return GenerationResult(
            text=text,
            provider=self._provider.name,
            metadata={
                "chapter": chapter.get("chapter", 0),
                "title": chapter.get("title", ""),
            },
        )

    async def generate_rewrite(
        self,
        original_text: str,
        instructions: str,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """重写指定文本。"""
        system, prompt = self._prompt_builder.build_rewrite_prompt(
            original_text, instructions,
        )
        text = await self._provider.generate(
            prompt=prompt,
            system_prompt=system,
            temperature=temperature,
            max_tokens=2000,
        )
        return GenerationResult(
            text=text,
            provider=self._provider.name,
        )
