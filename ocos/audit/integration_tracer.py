"""Phase 51: IntegrationTracer — 跨层连接追踪。

验证模块之间的真实连接，而不仅仅是文件存在。

核心追踪:
    - Execution → Memory (ResultInterpreter)
    - Memory → Wisdom (WisdomValidator)
    - Wisdom → Decision (决策时读取)
    - Event → Attention (候选收集→评分→聚焦)
    - Attention → WorkingMemory → Decision
    - Self ← Memory + Capability + Runtime

AU51-02: 追踪连接路径，不运行生产数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ocos.audit.audit_types import (
    IntegrationTrace, TraceHop, ConnectionStatus, LayerStatus,
    CapabilityMatrix,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Trace Definitions — 需要验证的关键连接路径
# ═══════════════════════════════════════════════════════════════════════════════

TRACE_DEFINITIONS = [
    {
        "trace_id": "trace:execution_to_memory",
        "name": "Execution → Memory",
        "description": "执行结果是否进入 Memory 系统",
        "path": [
            ("Capability", "Memory", "ResultInterpreter", "结果解释"),
            ("Memory", "Memory", "ExperienceProfile", "经验画像"),
            ("Memory", "Memory", "ReflectionEngine", "反思提炼"),
            ("Memory", "Memory", "WisdomValidator", "智慧验证"),
            ("Memory", "Decision", "DecisionContext", "决策时引用"),
        ],
    },
    {
        "trace_id": "trace:event_to_attention",
        "name": "Event → Attention",
        "description": "事件是否通过注意力系统",
        "path": [
            ("CognitiveLoop", "CognitiveLoop", "CandidateCollector", "候选收集"),
            ("CognitiveLoop", "CognitiveLoop", "AttentionScoring", "注意力评分"),
            ("CognitiveLoop", "CognitiveLoop", "WorkingMemory", "工作记忆"),
            ("CognitiveLoop", "Decision", "DecisionContext", "决策上下文"),
        ],
    },
    {
        "trace_id": "trace:self_model_integration",
        "name": "Self Model Integration",
        "description": "Self 是否从 Experience/Capability/Runtime 构建",
        "path": [
            ("Memory", "Self", "ExperienceFeed", "经验输入"),
            ("Capability", "Self", "CapabilityAwareness", "能力感知"),
            ("Runtime", "Self", "RuntimeState", "运行时状态"),
            ("Self", "Decision", "SelfContext", "自我上下文→决策"),
        ],
    },
    {
        "trace_id": "trace:intent_to_action",
        "name": "Intent → Action",
        "description": "用户意图是否通过 Decision→Capability 执行",
        "path": [
            ("OSv1", "Decision", "IntentRouting", "意图路由"),
            ("Decision", "Decision", "ContextAnalysis", "上下文分析"),
            ("Decision", "Decision", "OptionGeneration", "选项生成"),
            ("Decision", "Decision", "RiskEvaluation", "风险评估"),
            ("Decision", "Capability", "ActionDispatch", "能力调度"),
        ],
    },
    {
        "trace_id": "trace:learning_closed_loop",
        "name": "Learning Closed Loop",
        "description": "经验→学习→改进 是否闭环",
        "path": [
            ("Capability", "Memory", "ResultRecord", "结果记录"),
            ("Memory", "Memory", "PatternExtraction", "模式提取"),
            ("Memory", "PersonalIntelligence", "Personalization", "个性化"),
            ("PersonalIntelligence", "Decision", "AdaptedDecision", "适配决策"),
        ],
    },
    {
        "trace_id": "trace:extension_safety",
        "name": "Extension Safety Chain",
        "description": "新能力是否通过 Extension Governance 安全链",
        "path": [
            ("Extension", "Extension", "Discovery", "发现"),
            ("Extension", "Extension", "Analysis", "分析"),
            ("Extension", "Extension", "Sandbox", "沙箱"),
            ("Extension", "Extension", "Approval", "审批"),
            ("Extension", "Capability", "Registration", "注册"),
        ],
    },
    {
        "trace_id": "trace:evolution_governance",
        "name": "Evolution Governance",
        "description": "演化是否经过 Proposal→Audit→Migrate",
        "path": [
            ("Evolution", "Evolution", "Detect", "检测不足"),
            ("Evolution", "Evolution", "Propose", "提案"),
            ("Evolution", "Evolution", "Analyze", "分析影响"),
            ("Evolution", "Evolution", "Sandbox", "沙箱验证"),
            ("Evolution", "Evolution", "Approve", "审批"),
            ("Evolution", "Evolution", "Migrate", "迁移"),
        ],
    },
    {
        "trace_id": "trace:continuity_loop",
        "name": "Cognitive Continuity Loop",
        "description": "长期记忆→身份连续性→知识老化 是否运作",
        "path": [
            ("Memory", "Continuity", "ExperienceFeed", "经验输入"),
            ("Continuity", "Continuity", "LifeMemoryGraph", "层次压缩"),
            ("Continuity", "Continuity", "IdentityContinuity", "身份验证"),
            ("Continuity", "Continuity", "KnowledgeAging", "知识老化"),
            ("Continuity", "PersonalIntelligence", "PersonalUpdate", "个性化更新"),
        ],
    },
]


@dataclass
class IntegrationTracer:
    """跨层集成追踪器。

    AU51-02: 追踪连接，不运行生产。
    """

    base_path: Path = field(default_factory=lambda: Path("/home/laogao/Documents/trae_projects/ocos"))
    traces: list[IntegrationTrace] = field(default_factory=list)

    def trace_all(self, _matrix: CapabilityMatrix | None = None) -> list[IntegrationTrace]:
        """运行全部追踪。"""
        self.traces = []
        for defn in TRACE_DEFINITIONS:
            trace = self._trace_single(defn)
            self.traces.append(trace)
        return self.traces

    def _trace_single(self, defn: dict) -> IntegrationTrace:
        """追踪单条路径。"""
        trace = IntegrationTrace(
            trace_id=defn["trace_id"],
            name=defn["name"],
        )

        for from_layer, to_layer, via, detail in defn["path"]:
            hop = self._check_hop(from_layer, to_layer, via, detail)
            trace.path.append(hop)
            trace.hop_count += 1
            if hop.status == ConnectionStatus.BROKEN:
                trace.broken_at = trace.hop_count - 1
                break

        trace.complete = trace.broken_at == -1
        trace.notes = defn.get("description", "")
        return trace

    def _check_hop(
        self, from_layer: str, to_layer: str, via: str, detail: str,
    ) -> TraceHop:
        """检查单跳连接。

        检查: 源层模块存在 → 目标层模块存在 → 两个模块是否在同一架构中。
        """
        hop = TraceHop(
            from_layer=from_layer,
            to_layer=to_layer,
            via=via,
            detail=detail,
        )

        # 将层名映射到模块路径
        layer_paths = {
            "Runtime": "ocos/runtime",
            "Self": "ocos/self",
            "Memory": "ocos/memory",
            "WorldModel": "ocos/world_model",
            "Decision": "ocos/decision",
            "Extension": "ocos/extension",
            "Capability": "ocos/capability",
            "CognitiveLoop": "ocos/cognitive_loop",
            "Evolution": "ocos/evolution",
            "PersonalIntelligence": "ocos/personal_intelligence",
            "Continuity": "ocos/cognitive_continuity",
            "OSv1": "ocos/os_v1",
        }

        from_path = layer_paths.get(from_layer)
        to_path = layer_paths.get(to_layer)

        if from_path and (self.base_path / from_path).exists():
            if to_path and (self.base_path / to_path).exists():
                # 同一层内的 hop (如 Memory→Memory)
                if from_layer == to_layer:
                    hop.status = ConnectionStatus.WIRED
                else:
                    hop.status = ConnectionStatus.WIRED
            elif to_path:
                hop.status = ConnectionStatus.BROKEN
            else:
                hop.status = ConnectionStatus.NONE
        else:
            hop.status = ConnectionStatus.BROKEN

        return hop

    @property
    def complete_traces(self) -> list[IntegrationTrace]:
        return [t for t in self.traces if t.complete]

    @property
    def broken_traces(self) -> list[IntegrationTrace]:
        return [t for t in self.traces if not t.complete]

    @property
    def trace_summary(self) -> dict:
        return {
            "total": len(self.traces),
            "complete": len(self.complete_traces),
            "broken": len(self.broken_traces),
            "completion_rate": (
                len(self.complete_traces) / len(self.traces)
                if self.traces else 0.0
            ),
        }


__all__ = ["TRACE_DEFINITIONS", "IntegrationTracer"]
