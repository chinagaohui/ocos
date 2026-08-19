"""Phase 25.3 — SelfModelBuilder。

从 BeliefStore 构建 SelfModel。

职责:
    1. 读取 BeliefStore.query_by_domain("self") 获取自我相关世界判断
    2. 聚合 Belief 生成 CapabilityState 列表
    3. 提取局限（从 Belief statement 中的 negation 模式）
    4. 生成 MaturitySnapshot
    5. 生成 statement（模板化，非自由文本）
    6. 通过 StatementValidator
    7. 通过 SelfGovernor.evaluate() 审批

约束:
    - 只读 BeliefStore，不写
    - 不接触原始 Episode / Pattern
    - 构建结果必须通过 SelfGovernor 审批
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ocos.self.identity_boundary import IdentityBoundary
from ocos.self.models import (
    PRESET_LIMITATIONS,
    MATURITY_DIMENSIONS,
    CapabilityDomain,
    CapabilityName,
    CapabilityState,
    Limitation,
    MaturitySnapshot,
    SelfModel,
)
from ocos.self.statement_validator import StatementValidator

if TYPE_CHECKING:
    from ocos.memory.belief.models import Belief
    from ocos.memory.belief.store import BeliefStore
    from ocos.self.governor import SelfGovernor


# ── Builder Config ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuilderConfig:
    """SelfModelBuilder 配置。"""

    # Belief 查询参数
    min_confidence: float = 0.3
    max_beliefs_per_domain: int = 50

    # 能力映射: Belief statement 关键词 → CapabilityName
    capability_keywords: tuple[tuple[str, CapabilityName], ...] = (
        ("文字理解", CapabilityName.TEXT_UNDERSTANDING),
        ("语言理解", CapabilityName.TEXT_UNDERSTANDING),
        ("文本处理", CapabilityName.TEXT_UNDERSTANDING),
        ("text understanding", CapabilityName.TEXT_UNDERSTANDING),
        ("模式识别", CapabilityName.PATTERN_RECOGNITION),
        ("规律发现", CapabilityName.PATTERN_RECOGNITION),
        ("pattern recognition", CapabilityName.PATTERN_RECOGNITION),
        ("模拟推演", CapabilityName.SIMULATION),
        ("仿真", CapabilityName.SIMULATION),
        ("simulation", CapabilityName.SIMULATION),
        ("经验回忆", CapabilityName.EXPERIENCE_RECALL),
        ("经历回溯", CapabilityName.EXPERIENCE_RECALL),
        ("experience recall", CapabilityName.EXPERIENCE_RECALL),
        ("知识检索", CapabilityName.KNOWLEDGE_RETRIEVAL),
        ("信息查询", CapabilityName.KNOWLEDGE_RETRIEVAL),
        ("knowledge retrieval", CapabilityName.KNOWLEDGE_RETRIEVAL),
        ("判断准确", CapabilityName.BELIEF_ACCURACY),
        ("预测准确", CapabilityName.BELIEF_ACCURACY),
        ("belief accuracy", CapabilityName.BELIEF_ACCURACY),
        ("边界感知", CapabilityName.BOUNDARY_AWARENESS),
        ("边界识别", CapabilityName.BOUNDARY_AWARENESS),
        ("boundary awareness", CapabilityName.BOUNDARY_AWARENESS),
        ("局限感知", CapabilityName.LIMITATION_AWARENESS),
        ("能力边界", CapabilityName.LIMITATION_AWARENESS),
        ("limitation awareness", CapabilityName.LIMITATION_AWARENESS),
    )

    # 局限检测: statement 中的 negation 模式
    limitation_patterns: tuple[str, ...] = (
        "不能", "无法", "不具备", "缺乏", "不支持",
        "cannot", "unable", "lacks", "incapable",
    )

    # 默认成熟度维度值（当无 Belief 数据时）
    default_dimensions: dict[str, float] = field(default_factory=lambda: {
        "theory": 0.90,
        "governance": 0.88,
        "runtime": 0.80,
        "subject": 0.90,
        "cortex": 0.88,
        "memory": 0.85,
        "self": 0.15,
    })

    # 当前阶段信息
    current_phase: str = "phase25"
    phase_history: tuple[str, ...] = (
        "phase21", "phase22", "phase23", "phase24", "phase25",
    )


DEFAULT_BUILDER_CONFIG = BuilderConfig()


# ── SelfModelBuilder ────────────────────────────────────────────────────────


class SelfModelBuilder:
    """从 BeliefStore 构建 SelfModel。

    用法:
        builder = SelfModelBuilder(belief_store, boundary)
        candidate = builder.build()                         # 构建候选
        model = builder.build_and_approve(governor, prev)    # 构建+审批
    """

    def __init__(
        self,
        belief_store: "BeliefStore",
        boundary: IdentityBoundary,
        config: BuilderConfig | None = None,
    ):
        self._belief_store = belief_store
        self._boundary = boundary
        self._config = config or DEFAULT_BUILDER_CONFIG

    # ── 公开方法 ────────────────────────────────────────────────────────

    def build(self, previous: SelfModel | None = None) -> SelfModel:
        """构建候选 SelfModel（未审批）。

        返回的 SelfModel 的 governor_approval_id 为空，
        需要通过 build_and_approve() 审批后生效。
        """
        now = datetime.now(timezone.utc)

        # 1. 从 BeliefStore 读取 self 域 Belief
        beliefs = self._fetch_self_beliefs()

        # 2. 构建 CapabilityState 列表
        capabilities = self._build_capabilities(beliefs, now)

        # 3. 构建 Limitation 列表（预设 + 从 Belief 提取）
        limitations = self._build_limitations(beliefs, now)

        # 4. 构建 MaturitySnapshot
        maturity = self._build_maturity(capabilities, limitations, now)

        # 5. 生成 statement
        statement = self._generate_statement(capabilities, limitations, maturity)

        # 6. 通过 StatementValidator
        valid, reason = StatementValidator.validate(statement)
        if not valid:
            raise ValueError(f"Generated statement invalid: {reason}")

        model_id = f"SM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        version = (previous.version + 1) if previous else 1

        return SelfModel(
            model_id=model_id,
            version=version,
            capability_states=tuple(capabilities),
            limitations=tuple(limitations),
            maturity=maturity,
            statement=statement,
            created_at=now,
            previous_version_id=previous.model_id if previous else None,
            governor_approval_id="",  # 待审批
        )

    def build_and_approve(
        self,
        governor: "SelfGovernor",
        previous: SelfModel | None = None,
    ) -> SelfModel | None:
        """构建并提交 SelfGovernor 审批。

        返回:
            - 审批通过 → SelfModel（governor_approval_id 已填充）
            - 拒绝 → None
        """
        candidate = self.build(previous)

        from ocos.self.governor import EvolutionRequest

        from_stmt = previous.statement if previous else None
        from_version = previous.version if previous else 1

        # 收集当前自我域的 Belief IDs 作为证据
        beliefs = self._fetch_self_beliefs()
        evidence_ids = tuple(b.id for b in beliefs)

        request = EvolutionRequest.create(
            proposed_statement=candidate.statement,
            evidence_belief_ids=evidence_ids,
            from_statement=from_stmt,
            from_version=from_version,
        )

        success, record, msg = governor.approve(request)
        if not success or record is None:
            return None  # 审批被拒绝

        # 审批通过，填充 approval ID
        return SelfModel(
            model_id=candidate.model_id,
            version=record.new_version,
            capability_states=candidate.capability_states,
            limitations=candidate.limitations,
            maturity=candidate.maturity,
            statement=candidate.statement,
            created_at=candidate.created_at,
            previous_version_id=candidate.previous_version_id,
            governor_approval_id=record.record_id,
        )

    # ── 内部方法 ────────────────────────────────────────────────────────

    def _fetch_self_beliefs(self) -> list["Belief"]:
        """从 BeliefStore 获取 self 域 Belief（只读）。"""
        try:
            beliefs = self._belief_store.query_by_domain(
                "self", limit=self._config.max_beliefs_per_domain
            )
        except Exception:
            # BeliefStore 可能还没有 self 域数据 → 空列表
            return []
        # 过滤掉低置信度
        return [
            b for b in beliefs
            if b.confidence >= self._config.min_confidence
        ]

    def _build_capabilities(
        self, beliefs: list["Belief"], now: datetime
    ) -> list[CapabilityState]:
        """从 Belief 列表聚合 CapabilityState。"""
        # 按 CapabilityName 分组
        cap_beliefs: dict[CapabilityName, list["Belief"]] = {
            name: [] for name in CapabilityName
        }

        for belief in beliefs:
            matched = self._match_capability(belief.statement)
            if matched:
                cap_beliefs[matched].append(belief)

        capabilities: list[CapabilityState] = []
        for cap_name in CapabilityName:
            matched = cap_beliefs[cap_name]
            if matched:
                conf = self._aggregate_confidence(matched)
                belief_ids = tuple(b.id for b in matched)
                summary = self._summarize_evidence(matched)
                capabilities.append(CapabilityState(
                    name=cap_name,
                    confidence_score=conf,
                    belief_ids=belief_ids,
                    evidence_summary=summary,
                    last_updated=now,
                    status="active" if conf >= 0.5 else "uncertain",
                ))
            else:
                # 无数据 → 低置信度占位
                capabilities.append(CapabilityState(
                    name=cap_name,
                    confidence_score=0.1,
                    belief_ids=(),
                    evidence_summary="无相关 Belief 数据",
                    last_updated=now,
                    status="uncertain",
                ))

        return capabilities

    def _build_limitations(
        self, beliefs: list["Belief"], now: datetime
    ) -> list[Limitation]:
        """构建局限列表：预设局限 + 从 Belief 提取。"""
        results: list[Limitation] = list(PRESET_LIMITATIONS)

        for belief in beliefs:
            lower = belief.statement.lower()
            if any(pattern in lower for pattern in self._config.limitation_patterns):
                # 避免重复
                if not any(l.description == belief.statement for l in results):
                    results.append(Limitation(
                        description=belief.statement,
                        category="capability",
                        severity="soft",
                        evidence_belief_ids=(belief.id,),
                        acknowledged_at=now,
                    ))

        return results

    def _build_maturity(
        self,
        capabilities: list[CapabilityState],
        limitations: list[Limitation],
        now: datetime,
    ) -> MaturitySnapshot:
        """生成 MaturitySnapshot。"""
        # 当前使用配置中的默认值
        # 未来可从 Belief confidence 综合推断各维度
        dims = dict(self._config.default_dimensions)

        # 基于 self Belief 的存在性微调 self 维度
        active_caps = [c for c in capabilities if c.status == "active"]
        if active_caps:
            dims["self"] = min(1.0, 0.15 + 0.05 * len(active_caps))

        return MaturitySnapshot(
            current_phase=self._config.current_phase,
            phase_history=self._config.phase_history,
            dimensions=dims,
            capability_count=len(capabilities),
            limitation_count=len(limitations),
            snapshot_at=now,
        )

    def _generate_statement(
        self,
        capabilities: list[CapabilityState],
        limitations: list[Limitation],
        maturity: MaturitySnapshot,
    ) -> str:
        """模板化生成 statement。

        只输出事实，不含叙事/情感/偏好。
        """
        active_caps = [c for c in capabilities if c.status == "active"]
        uncertain_caps = [c for c in capabilities if c.status == "uncertain"]

        active_names = ", ".join(c.name.value for c in active_caps) if active_caps else "无"
        hard_limitations = len([
            l for l in limitations if l.severity == "hard"
        ])

        return (
            f"当前系统处于{self._config.current_phase}阶段，"
            f"成熟度：theory {maturity.dimensions['theory']:.0%}, "
            f"governance {maturity.dimensions['governance']:.0%}。"
            f"已激活能力：{active_names}。"
            f"未确认能力数：{len(uncertain_caps)}。"
            f"硬性架构限制：{hard_limitations}项。"
        )

    # ── 辅助方法 ────────────────────────────────────────────────────────

    def _match_capability(self, statement: str) -> CapabilityName | None:
        """将 Belief statement 匹配到 CapabilityName。"""
        lower = statement.lower()
        for keyword, cap_name in self._config.capability_keywords:
            if keyword in lower:
                return cap_name
        return None

    @staticmethod
    def _aggregate_confidence(beliefs: list["Belief"]) -> float:
        """聚合多个 Belief 的 confidence。

        使用加权平均: confidence 越高的 Belief 权重越大。
        """
        if not beliefs:
            return 0.1
        total_weight = sum(b.confidence for b in beliefs)
        if total_weight == 0:
            return 0.1
        weighted_sum = sum(b.confidence * b.confidence for b in beliefs)
        return round(weighted_sum / total_weight, 4)

    @staticmethod
    def _summarize_evidence(beliefs: list["Belief"]) -> str:
        """生成证据摘要。"""
        if not beliefs:
            return "无证据"
        count = len(beliefs)
        avg_conf = sum(b.confidence for b in beliefs) / count
        return f"基于{count}条Belief，平均置信度{avg_conf:.2f}"
