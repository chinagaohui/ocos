"""Phase 51: GapAnalyzer — 能力缺口扫描。

扫描当前架构，识别:
    - 已设计但未实现的连接
    - 缺少的感知层
    - 缺少的主动交互
    - Runtime 调度未接通的链路

AU51-04: Gap ≠ Blocker — 发现缺口不阻止运行，只记录。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.audit.audit_types import GapReport


# ═══════════════════════════════════════════════════════════════════════════════
# 已知缺口定义
# ═══════════════════════════════════════════════════════════════════════════════

KNOWN_GAPS = [
    GapReport(
        gap_id="G-PERCEPTION-01",
        category="perception",
        description="缺少真正的 Perception Layer — OCOS 没有从外部世界获取输入的标准通道。"
                    "目前只有 EventBus 事件，缺少: 文本输入→语义提取→世界模型更新。",
        impact="无法感知外部世界的结构化信息。只能被动等待事件。",
        suggested_phase="Phase 52",
        priority="high",
    ),
    GapReport(
        gap_id="G-RUNTIME-01",
        category="runtime",
        description="TickPipeline 存在但缺少真实的持续调度器。"
                    "各模块的 tick() 方法已定义，但缺少: cron-like 调度、优先级队列、背压控制。",
        impact="长期运行时可能出现调度不均衡或资源泄漏。",
        suggested_phase="Phase 51+",
        priority="medium",
    ),
    GapReport(
        gap_id="G-EVENTBUS-01",
        category="event",
        description="EventBus 定义了接口但缺少: 持久化事件队列、事件重放、死信队列。",
        impact="事件丢失后无法恢复。",
        suggested_phase="Phase 51+",
        priority="medium",
    ),
    GapReport(
        gap_id="G-MEMORYHUB-01",
        category="memory",
        description="MemoryHub 的 Result→Episode→Pattern→Knowledge→Belief 链路已设计，"
                    "但缺少: 真实持久化后端 (SQLite/file)、跨 session 恢复。",
        impact="重启后记忆丢失。",
        suggested_phase="Phase 51+",
        priority="high",
    ),
    GapReport(
        gap_id="G-CAPABILITY-01",
        category="capability",
        description="Capability Adapters 已定义接口，但缺少: 真实外部工具连接器"
                    " (Codex/OpenTale/Browser 的实际 HTTP/gRPC 客户端)。",
        impact="能力调用停留在 mock 层。",
        suggested_phase="Phase 52-53",
        priority="medium",
    ),
    GapReport(
        gap_id="G-INTERACTION-01",
        category="interaction",
        description="缺少主动输出系统 — OCOS 目前只能响应输入，"
                    "不能: 主动推送通知、主动发起对话、主动报告状态变化。",
        impact="OCOS 是被动的思考者，不是主动的伙伴。",
        suggested_phase="Phase 53",
        priority="high",
    ),
    GapReport(
        gap_id="G-EXTENSION-01",
        category="extension",
        description="Extension Discovery 已定义流程但缺少: 动态插件发现机制、"
                    "热加载、版本兼容性检查。",
        impact="新能力需要手动编码注册。",
        suggested_phase="Phase 52+",
        priority="medium",
    ),
    GapReport(
        gap_id="G-OBSERVABILITY-01",
        category="observability",
        description="缺少可观测性基础设施: 结构化日志、Metrics、分布式追踪。"
                    "当前测试依赖 pytest 输出，生产环境无法监控内部状态。",
        impact="运行中的 OCOS 是黑盒。无法诊断问题。",
        suggested_phase="Phase 51+",
        priority="medium",
    ),
    GapReport(
        gap_id="G-CONTINUITY-01",
        category="continuity",
        description="Cognitive Continuity 的 Checkpoint 系统缺少: "
                    "实际序列化/反序列化、跨 session 状态恢复。",
        impact="长期连续性停留在内存中。",
        suggested_phase="Phase 51+",
        priority="medium",
    ),
    GapReport(
        gap_id="G-PERSISTENCE-01",
        category="persistence",
        description="整个 OCOS 缺少统一的持久化层: "
                    "状态快照、冷启动恢复、优雅关闭。",
        impact="OCOS 是短命进程，不是持续运行的数字生命。",
        suggested_phase="Phase 51+",
        priority="critical",
    ),
]


@dataclass
class GapAnalyzer:
    """能力缺口分析器。

    AU51-04: 只识别缺口，不视为阻塞。
    """

    gaps: list[GapReport] = field(default_factory=lambda: list(KNOWN_GAPS))

    def analyze(self) -> list[GapReport]:
        """分析所有已知和可检测的缺口。"""
        return self.gaps

    def gaps_by_priority(self) -> dict[str, list[GapReport]]:
        result: dict[str, list[GapReport]] = {}
        for gap in self.gaps:
            result.setdefault(gap.priority, []).append(gap)
        return result

    def gaps_by_category(self) -> dict[str, list[GapReport]]:
        result: dict[str, list[GapReport]] = {}
        for gap in self.gaps:
            result.setdefault(gap.category, []).append(gap)
        return result

    @property
    def critical_gaps(self) -> list[GapReport]:
        return [g for g in self.gaps if g.priority == "critical"]

    @property
    def high_priority_gaps(self) -> list[GapReport]:
        return [g for g in self.gaps if g.priority in ("critical", "high")]

    def roadmap(self) -> list[str]:
        """根据缺口生成 V1.1 路线图建议。"""
        phases: dict[str, list[str]] = {}
        for gap in self.gaps:
            phases.setdefault(gap.suggested_phase, []).append(
                f"[{gap.priority}] {gap.description}"
            )
        roadmap = []
        for phase in sorted(phases):
            items = phases[phase]
            items_str = "; ".join(items)
            roadmap.append(f"{phase}: {items_str}")
        return roadmap


__all__ = ["KNOWN_GAPS", "GapAnalyzer"]
