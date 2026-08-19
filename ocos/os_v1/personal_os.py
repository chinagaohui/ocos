"""Phase 50: PersonalCognitiveOS — 统一个人认知操作系统入口。

不是大脑，是统一的认知路由层。

处理流程:
    UserIntent
        ↓ classify (确定领域/复杂度)
        ↓ enrich  (注入上下文 — Memory/Timeline/Signature)
        ↓ route   (分发到对应认知子系统)
        ↓ decide  (Phase 43 Decision)
        ↓ execute (Phase 45 Capability)
        ↓ learn   (Phase 41 Memory + Phase 48 Personalization)
        ↓ respond (OSResponse)

核心边界:
    OS50-01: Interface ≠ Brain — 路由意图，不替代各层决策
    OS50-06: Capability ≠ Identity — 外部工具是提供者
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.os_v1.os_types import (
    UserIntent, IntentDomain, IntentComplexity,
    OSResponse, CapabilityProvider, CapabilityResult, CapabilityStatus,
)


@dataclass
class PersonalCognitiveOS:
    """Personal Cognitive OS — 统一认知操作系统。

    聚合所有 Phase 39-49 的子系统，提供统一入口。

    这不是一个新的认知层——它只是路由。
    决策仍在 Phase 43，记忆仍在 Phase 41，演化仍在 Phase 47。
    """

    # 能力注册表 (OS50-06: 外部工具)
    capability_providers: dict[str, CapabilityProvider] = field(default_factory=dict)

    # 操作统计
    intent_count: int = 0
    response_count: int = 0
    capability_calls: int = 0

    def register_capability(self, provider: CapabilityProvider) -> None:
        """注册外部能力 (OS50-06: 不是 OCOS 的一部分)。"""
        self.capability_providers[provider.name] = provider

    def unregister_capability(self, name: str) -> bool:
        return self.capability_providers.pop(name, None) is not None

    def classify_intent(self, raw_text: str) -> UserIntent:
        """分类用户意图 —— 确定领域和复杂度。

        这是路由层，不做决策。
        """
        self.intent_count += 1
        intent_id = f"intent:{self.intent_count}"

        # 关键词→领域映射
        domain = self._infer_domain(raw_text)
        complexity = self._infer_complexity(raw_text)

        return UserIntent(
            intent_id=intent_id,
            raw_text=raw_text,
            domain=domain,
            complexity=complexity,
            context_tags=self._extract_tags(raw_text),
        )

    def _infer_domain(self, text: str) -> IntentDomain:
        lower = text.lower()
        # 先检查编程（避免"写代码"被WRITING匹配）
        if any(k in lower for k in ["代码", "编程", "函数", "code", "debug", "python", "script", "api", "web server"]):
            return IntentDomain.CODING
        if any(k in lower for k in ["写", "写文", "文章", "故事", "write", "novel"]):
            return IntentDomain.WRITING
        if any(k in lower for k in ["研究", "调查", "research", "论文"]):
            return IntentDomain.RESEARCH
        if any(k in lower for k in ["分析", "报告", "analyze", "analysis"]):
            return IntentDomain.ANALYSIS
        if any(k in lower for k in ["计划", "规划", "plan", "schedule"]):
            return IntentDomain.PLANNING
        if any(k in lower for k in ["管理", "项目", "manage", "project"]):
            return IntentDomain.MANAGEMENT
        if any(k in lower for k in ["学", "学习", "learn", "tutorial"]):
            return IntentDomain.LEARNING
        return IntentDomain.GENERAL

    def _infer_complexity(self, text: str) -> IntentComplexity:
        word_count = len(text)
        if word_count < 20:
            return IntentComplexity.SIMPLE
        if word_count < 80:
            return IntentComplexity.MODERATE
        if word_count < 200:
            return IntentComplexity.COMPLEX
        return IntentComplexity.PROJECT

    def _extract_tags(self, text: str) -> list[str]:
        tags = []
        lower = text.lower()
        # 简单关键词标签提取
        keywords = ["python", "javascript", "api", "database", "frontend", "backend",
                     "opensource", "optimization", "refactoring", "testing", "deployment"]
        for kw in keywords:
            if kw in lower:
                tags.append(kw)
        return tags[:5]

    def process(
        self,
        raw_text: str,
        tick_id: int = 0,
    ) -> OSResponse:
        """处理用户意图 —— 统一入口。

        完整链路: classify → enrich → route → decide → execute → learn → respond
        """
        intent = self.classify_intent(raw_text)

        # 实际生产中这里会调用各子系统
        # 本次是统一接口层的实现

        reasoning = [
            f"classify: domain={intent.domain.value} complexity={intent.complexity.value}",
            f"enrich: tags={intent.context_tags}",
        ]

        # 能力检查
        available = self._find_capability(intent.domain)
        if available:
            reasoning.append(f"route: capability={available.name} status={available.status.value}")

        self.response_count += 1
        return OSResponse(
            intent_id=intent.intent_id,
            result=f"[{intent.domain.value}] {raw_text[:100]}",
            reasoning_chain=reasoning,
            confidence=0.8,
            tick_id=tick_id,
        )

    def call_capability(self, provider_name: str, input_text: str) -> CapabilityResult:
        """调用外部能力 (OS50-06: 工具调用)。"""
        self.capability_calls += 1
        provider = self.capability_providers.get(provider_name)
        if not provider:
            return CapabilityResult(
                provider=provider_name,
                success=False,
                error=f"Provider '{provider_name}' not registered",
            )
        if provider.status != CapabilityStatus.AVAILABLE:
            return CapabilityResult(
                provider=provider_name,
                success=False,
                error=f"Provider '{provider_name}' is {provider.status.value}",
            )
        return CapabilityResult(
            provider=provider_name,
            success=True,
            output=f"[{provider_name}] processed: {input_text[:100]}",
            duration_ticks=1,
        )

    def _find_capability(self, domain: IntentDomain) -> CapabilityProvider | None:
        domain_str = domain.value
        for p in self.capability_providers.values():
            if p.domain == domain_str and p.status == CapabilityStatus.AVAILABLE:
                return p
        return None

    def capability_summary(self) -> dict[str, str]:
        return {name: p.status.value for name, p in self.capability_providers.items()}


__all__ = ["PersonalCognitiveOS"]
