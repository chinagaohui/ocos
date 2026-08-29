"""Phase 29: Homeostasis Monitor — 稳态监控系统。

Freeze §HOMEOSTASIS_MODEL v1.0 — Homeostasis 是数字生命体区别于普通程序的关键特征:
  Recovery 是"坏了修"，Homeostasis 是"始终保持不坏"。

架构:
  HomeostasisManager
    ├── Monitor（6 维度采样）
    │   ├── ResourceMonitor  CPU/Memory/Storage/LLM calls
    │   ├── MemoryMonitor    记忆体大小/碎片率
    │   ├── GoalMonitor      Goal 数量/阻塞率/过期率
    │   ├── HealthMonitor    错误率/延迟/崩溃计数
    │   ├── ContextMonitor   Token 消耗/疲劳度
    │   └── IdentityMonitor  身份完整性检查
    ├── Thresholds（告警阈值配置）
    ├── Regulator（调节动作 — Phase 29 为 stub，由后续 Phase 实现）
    └── HealthReport（健康报告）

约束:
  - 优先级高于 Goal，但不打断用户交互
  - SLEEP/DREAM 阶段执行全面维护
  - 紧急告警可暂停用户交互（通知主人）
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

from ocos.kernel.goal_types import (
    Goal,
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
    GoalStatus,
)
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────


class AlertLevel(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


class RegulatorAction(Enum):
    """调节器可以执行的动作类型。"""
    COMPRESS_MEMORY = auto()
    FORGET_LOW_CONFIDENCE = auto()
    ARCHIVE_OLD_DATA = auto()
    PAUSE_LOW_PRIORITY = auto()
    DEGRADE_QUALITY = auto()
    THROTTLE_LLM = auto()
    TRIGGER_SLEEP = auto()
    COMPRESS_CONTEXT = auto()
    NONE = auto()


# ── 内生驱力（P2-A: Regulator 内生目标引擎）──────────────────────────────────


class DriveType(Enum):
    """内生驱力类型（升级报告 §4 五驱力）。"""

    EXPLORE = "EXPLORE"      # 探索：目标匮乏时寻找新输入/新领域
    MASTERY = "MASTERY"      # 胜任：阻塞/失败积累时攻坚与技能巩固
    CONNECTION = "CONNECTION"  # 联结：交互稀薄时主动发起联结
    RESTORE = "RESTORE"      # 恢复：资源高水位时整理与回收
    REFLECT = "REFLECT"      # 反思：身份/记忆完整性受损时回溯一致性


@dataclass(frozen=True)
class DriveSignal:
    """单个驱力信号（确定性推导，无 I/O）。"""

    drive: DriveType
    intensity: float  # [0.3, 1.0]
    reason: str
    metric: str


@dataclass(frozen=True)
class RegulateResult:
    """一次 regulate() 的完整结果。"""

    drives: list[DriveSignal]
    goals: list[Goal]
    actions: list[RegulatorAction]
    gated: list[str]  # 被门控拒绝的目标描述


class Regulator:
    """调节器 — 稳态偏差 → 驱力 → 内生目标（P2-A 实现）。

    确定性函数式组件：无状态、无 I/O、无 LLM。
    输入 MonitorSnapshot，输出 DriveSignal 列表与 SELF 级 Goal 列表。
    目标生成可挂 gate 回调（生产由 GoalOriginEnforcer 门控）。
    """

    MAX_GOALS_PER_CYCLE = 3
    HUMAN_PRIORITY_FLOOR = 1.0  # SELF 优先级恒低于 HUMAN

    def __init__(self, thresholds: HomeostasisThresholds | None = None) -> None:
        self._thresholds = thresholds or HomeostasisThresholds()

    # 驱力 → 目标模板（确定性）
    _GOAL_TEMPLATES: dict[DriveType, tuple[str, float, GoalLevel]] = {
        DriveType.EXPLORE: (
            "探索新领域：识别并吸收一条当前认知盲区的新信息",
            0.5, GoalLevel.SHORT,
        ),
        DriveType.MASTERY: (
            "攻克阻塞目标：处理当前阻塞中的任务并巩固对应技能",
            0.6, GoalLevel.SHORT,
        ),
        DriveType.CONNECTION: (
            "发起一次主动联结：向用户或外部环境发起一次有意义的交互",
            0.4, GoalLevel.SHORT,
        ),
        DriveType.RESTORE: (
            "执行一次资源整理：清理低价值数据并压缩上下文",
            0.7, GoalLevel.SHORT,
        ),
        DriveType.REFLECT: (
            "进行一次身份反思：回顾近期信念与行为的一致性",
            0.3, GoalLevel.SHORT,
        ),
    }

    @staticmethod
    def _clamp(value: float, lo: float = 0.3, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))

    def derive_drives(self, snapshot: MonitorSnapshot) -> list[DriveSignal]:
        """确定性规则表：偏差 → 驱力（intensity 按偏差比例映射 [0.3, 1.0]）。"""
        t = self._thresholds
        drives: list[DriveSignal] = []

        # RESTORE — 资源高水位（内存/存储）
        if snapshot.resource.memory_percent > t.memory_percent_max:
            drives.append(DriveSignal(
                DriveType.RESTORE,
                self._clamp((snapshot.resource.memory_percent - t.memory_percent_max) / 20.0),
                "系统内存高水位",
                "resource.memory_percent",
            ))
        if snapshot.resource.storage_percent > t.storage_percent_max:
            drives.append(DriveSignal(
                DriveType.RESTORE,
                self._clamp((snapshot.resource.storage_percent - t.storage_percent_max) / 15.0),
                "系统存储高水位",
                "resource.storage_percent",
            ))

        # EXPLORE — ① 目标匮乏（active 少且无阻塞 → 无事可做）② 好奇心（novelty 信号，P2-B）
        # 强度取两者较大者；注意力预算（fatigue ≥ 0.70）→ ×0.5 抑制（防探索失控）。
        explore_intensity = 0.0
        explore_reason = ""
        explore_source = ""
        if snapshot.goal.active_goal_count < 2 and snapshot.goal.blocked_goal_count == 0:
            explore_intensity = 0.5
            explore_reason = "目标匮乏：当前无事可做"
            explore_source = "goal.active_goal_count"
        if snapshot.context.novelty >= 0.6:
            novelty_intensity = self._clamp((snapshot.context.novelty - 0.6) / 0.4)
            if novelty_intensity > explore_intensity:
                explore_intensity = novelty_intensity
                explore_reason = f"好奇心：新信息增量 {snapshot.context.novelty:.2f}"
                explore_source = "context.novelty"
        if explore_intensity > 0.0:
            if snapshot.context.attention_fatigue >= 0.70:
                explore_intensity *= 0.5  # 注意力预算抑制（L5 防失控）
                explore_reason += "（注意力预算抑制 ×0.5）"
            drives.append(DriveSignal(
                DriveType.EXPLORE,
                explore_intensity,
                explore_reason,
                explore_source,
            ))

        # MASTERY — 阻塞/失败积累
        if snapshot.goal.blocked_goal_count > t.blocked_goal_max:
            drives.append(DriveSignal(
                DriveType.MASTERY,
                self._clamp(0.4 + 0.1 * (snapshot.goal.blocked_goal_count - t.blocked_goal_max)),
                f"阻塞目标积累：{snapshot.goal.blocked_goal_count} 个阻塞",
                "goal.blocked_goal_count",
            ))
        if snapshot.health.error_rate > t.error_rate_max:
            drives.append(DriveSignal(
                DriveType.MASTERY,
                self._clamp(0.4 + snapshot.health.error_rate),
                "错误率超阈：需要技能巩固",
                "health.error_rate",
            ))

        # CONNECTION — 交互稀薄（低 token 负载 + 低疲劳 + 无活跃目标）
        if (
            snapshot.context.current_tokens < 500
            and snapshot.context.attention_fatigue < 0.1
            and snapshot.goal.active_goal_count == 0
        ):
            drives.append(DriveSignal(
                DriveType.CONNECTION,
                0.4,
                "交互稀薄：长期无外部联结",
                "context.current_tokens",
            ))

        # REFLECT — 身份/记忆完整性
        if not snapshot.identity.integrity_ok:
            drives.append(DriveSignal(
                DriveType.REFLECT,
                0.7,
                "身份完整性受损",
                "identity.integrity_ok",
            ))
        if snapshot.memory.fragmentation_percent > t.memory_fragmentation_max:
            drives.append(DriveSignal(
                DriveType.REFLECT,
                self._clamp(0.3 + snapshot.memory.fragmentation_percent),
                "记忆碎片率高：需要整理反思",
                "memory.fragmentation_percent",
            ))

        return drives

    def generate_self_goals(
        self,
        drives: list[DriveSignal],
        now: datetime | None = None,
        gate: Any = None,
    ) -> tuple[list[Goal], list[str]]:
        """驱力 → SELF 级 Goal（确定性模板）。

        gate: Callable[[Goal], bool] — 返回 False 的目标被门控拒绝（不入列表）。
        gated: 被拒绝目标的描述列表。
        """
        now = now or datetime.now(timezone.utc)
        goals: list[Goal] = []
        gated: list[str] = []

        for drive in drives[: self.MAX_GOALS_PER_CYCLE]:
            template, priority, level = self._GOAL_TEMPLATES[drive.drive]
            goal = Goal(
                level=level,
                description=template,
                priority=min(priority, self.HUMAN_PRIORITY_FLOOR - 0.1),
                created_at=now,
                status=GoalStatus.PENDING,
                origin_level=GoalOriginLevel.SELF,
                authority=GoalAuthority.AUTONOMOUS,
                metadata={"drive": drive.drive.value, "intensity": drive.intensity},
            )
            if gate is not None and not gate(goal):
                gated.append(template)
                continue
            goals.append(goal)

        return goals, gated


# ── 阈值配置 ─────────────────────────────────────────────────────────────────


@dataclass
class HomeostasisThresholds:
    """系统稳态阈值配置（HOMEOSTASIS_MODEL v1.0 §Threshold）。"""

    # 资源
    cpu_percent_max: float = 80.0
    memory_percent_max: float = 80.0
    storage_percent_max: float = 85.0

    # 记忆
    working_memory_items_max: int = 1000
    episode_memory_items_max: int = 10000
    long_term_memory_bytes_max: int = 1_000_000_000  # 1GB
    belief_count_max: int = 5000
    memory_fragmentation_max: float = 0.30

    # Goal
    active_goal_max: int = 10
    blocked_goal_max: int = 3
    expired_goal_max: int = 5

    # 健康
    error_rate_max: float = 0.05
    latency_max: float = 30.0  # seconds
    crash_count_max: int = 3

    # Context
    context_tokens_max: int = 4096
    context_tokens_critical: int = 8192
    attention_fatigue_max: float = 0.70
    attention_fatigue_critical: float = 0.90
    context_switches_per_hour_max: int = 30

    # LLM
    llm_calls_per_hour_max: int = 100

    # Identity
    identity_integrity_required: bool = True


# ── 指标数据类 ───────────────────────────────────────────────────────────────


@dataclass
class ResourceMetrics:
    """资源维度采样。"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    storage_percent: float = 0.0
    llm_calls_this_hour: int = 0
    latency_avg_ms: float = 0.0


@dataclass
class MemoryMetrics:
    """记忆维度采样。"""
    working_memory_items: int = 0
    episode_memory_items: int = 0
    long_term_memory_bytes: int = 0
    belief_count: int = 0
    fragmentation_percent: float = 0.0


@dataclass
class GoalMetrics:
    """Goal 维度采样。"""
    active_goal_count: int = 0
    blocked_goal_count: int = 0
    expired_goal_count: int = 0
    orphan_goal_count: int = 0


@dataclass
class HealthMetrics:
    """健康维度采样。"""
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    crash_count: int = 0
    uptime_seconds: float = 0.0


@dataclass
class ContextMetrics:
    """Context 维度采样。"""
    current_tokens: int = 0
    attention_fatigue: float = 0.0
    context_switches_this_hour: int = 0
    # P2-B (2026-08-29): 好奇心驱动 — 本 tick 感知到的最新颖信号（AttentionScoreTrace.novelty 最大值）
    # 确定性来源：AttentionScoringEngine 输出，外部不可注入（防伪造）。
    novelty: float = 0.0


@dataclass
class IdentityMetrics:
    """Identity 完整性采样。"""
    integrity_ok: bool = True
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class MonitorSnapshot:
    """所有 6 个维度的单次采样快照。"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resource: ResourceMetrics = field(default_factory=ResourceMetrics)
    memory: MemoryMetrics = field(default_factory=MemoryMetrics)
    goal: GoalMetrics = field(default_factory=GoalMetrics)
    health: HealthMetrics = field(default_factory=HealthMetrics)
    context: ContextMetrics = field(default_factory=ContextMetrics)
    identity: IdentityMetrics = field(default_factory=IdentityMetrics)


# ── Alert / Report ───────────────────────────────────────────────────────────


@dataclass
class Alert:
    """单个告警。"""
    level: AlertLevel
    dimension: str
    metric: str
    current_value: float
    threshold: float
    message: str = ""


@dataclass
class HealthReport:
    """系统健康报告（HOMEOSTASIS_MODEL §Health Report）。"""
    score: float  # [0, 100]
    alerts: list[Alert] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    snapshot: MonitorSnapshot = field(default_factory=MonitorSnapshot)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Monitors ─────────────────────────────────────────────────────────────────


class ResourceMonitor:
    """资源监控：CPU / Memory / Storage / LLM calls。"""

    def sample(self) -> ResourceMetrics:
        m = ResourceMetrics()
        try:
            m.cpu_percent = self._get_cpu()
        except Exception:
            pass
        try:
            m.memory_percent = self._get_memory()
        except Exception:
            pass
        try:
            m.storage_percent = self._get_storage()
        except Exception:
            pass
        return m

    def _get_cpu(self) -> float:
        try:
            cpu_count = os.cpu_count() or 1
            return os.getloadavg()[0] / cpu_count * 100
        except Exception:
            return 0.0

    def _get_memory(self) -> float:
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            return 0.0

    def _get_storage(self) -> float:
        try:
            import psutil
            return psutil.disk_usage("/").percent
        except ImportError:
            return 0.0


class MemoryMonitor:
    """记忆监控：Working/Episode/Long-term Memory 状态。"""

    def __init__(self) -> None:
        self._wm: Any = None  # WorkingMemory ref
        self._em: Any = None  # EpisodeMemory ref
        self._kg: Any = None  # KnowledgeGraph ref（替代 LTM 大小查询）

    def sample(self) -> MemoryMetrics:
        return MemoryMetrics()


class GoalMonitor:
    """Goal 监控：活跃/阻塞/过期数量。"""

    def sample(self) -> GoalMetrics:
        return GoalMetrics()


class HealthMonitor:
    """健康监控：错误率 / 延迟 / 崩溃。"""

    def __init__(self) -> None:
        self._error_count: int = 0
        self._total_count: int = 0
        self._latency_samples: list[float] = []
        self._crash_count: int = 0
        self._start_time: float = time.monotonic()

    def record_success(self, latency_ms: float = 0.0) -> None:
        self._total_count += 1
        if latency_ms > 0:
            self._latency_samples.append(latency_ms)

    def record_error(self, latency_ms: float = 0.0) -> None:
        self._error_count += 1
        self._total_count += 1
        if latency_ms > 0:
            self._latency_samples.append(latency_ms)

    def record_crash(self) -> None:
        self._crash_count += 1

    def sample(self) -> HealthMetrics:
        total = max(self._total_count, 1)
        return HealthMetrics(
            error_rate=self._error_count / total,
            avg_latency_ms=sum(self._latency_samples[-100:]) / max(len(self._latency_samples[-100:]), 1),
            crash_count=self._crash_count,
            uptime_seconds=time.monotonic() - self._start_time,
        )


class ContextMonitor:
    """Context 监控：Token 消耗 / 注意力疲劳。"""

    def __init__(self) -> None:
        self._current_tokens: int = 0
        self._fatigue: float = 0.0
        self._switch_count: int = 0

    def update_tokens(self, count: int) -> None:
        self._current_tokens = count

    def update_fatigue(self, value: float) -> None:
        self._fatigue = max(0.0, min(1.0, value))

    def record_switch(self) -> None:
        self._switch_count += 1

    def sample(self) -> ContextMetrics:
        return ContextMetrics(
            current_tokens=self._current_tokens,
            attention_fatigue=self._fatigue,
            context_switches_this_hour=self._switch_count,
        )


class IdentityMonitor:
    """身份完整性检查。"""

    def sample(self, identity: Any = None) -> IdentityMetrics:
        if identity is None:
            return IdentityMetrics(integrity_ok=True)

        missing: list[str] = []
        if not hasattr(identity, "name") or not identity.name:
            missing.append("name")
        if not hasattr(identity, "version"):
            missing.append("version")

        return IdentityMetrics(
            integrity_ok=len(missing) == 0,
            missing_fields=missing,
        )


# ── HomeostasisManager ───────────────────────────────────────────────────────


class HomeostasisManager:
    """稳态管理器（HOMEOSTASIS_MODEL v1.0）。

    始终运行、优先级高于 Goal 的底层模块。
    集成 6 个 Monitor + Threshold + HealthReport + Regulator stub。

    用法:
        hm = HomeostasisManager()
        snapshot = hm.check()          # 采样 + 对比阈值
        report = hm.health_report()     # 生成健康报告
        actions = hm.recommend_actions()  # 获取建议调节动作
    """

    def __init__(
        self,
        thresholds: HomeostasisThresholds | None = None,
    ) -> None:
        self._thresholds = thresholds or HomeostasisThresholds()

        # 6 monitors
        self._resource = ResourceMonitor()
        self._memory = MemoryMonitor()
        self._goal = GoalMonitor()
        self._health = HealthMonitor()
        self._context = ContextMonitor()
        self._identity = IdentityMonitor()

        # 健康历史
        self._history: list[HealthReport] = []
        self._alert_history: list[Alert] = []

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def health(self) -> HealthMonitor:
        return self._health

    @property
    def context(self) -> ContextMonitor:
        return self._context

    @property
    def resource(self) -> ResourceMonitor:
        return self._resource

    @property
    def thresholds(self) -> HomeostasisThresholds:
        return self._thresholds

    # ── Core API ──────────────────────────────────────────────────────────

    def check(self) -> MonitorSnapshot:
        """全维度采样并生成快照。"""
        return MonitorSnapshot(
            resource=self._resource.sample(),
            memory=self._memory.sample(),
            goal=self._goal.sample(),
            health=self._health.sample(),
            context=self._context.sample(),
            identity=self._identity.sample(),
        )

    def health_report(self, snapshot: MonitorSnapshot | None = None) -> HealthReport:
        """生成健康报告：对比阈值，生成告警和建议。

        Args:
            snapshot: 可选，不传则自动采样
        """
        snap = snapshot or self.check()
        alerts: list[Alert] = []
        recommendations: list[str] = []

        t = self._thresholds

        # ── 资源检查 ──────────────────────────────────────────────────
        r = snap.resource
        self._check("resource", "cpu_percent", r.cpu_percent, t.cpu_percent_max,
                    alerts, recommendations, "CPU 过载，建议暂停低优先级任务")
        self._check("resource", "memory_percent", r.memory_percent, t.memory_percent_max,
                    alerts, recommendations, "内存不足，建议触发记忆压缩")
        self._check("resource", "storage_percent", r.storage_percent, t.storage_percent_max,
                    alerts, recommendations, "存储空间不足，建议归档旧数据")
        if r.llm_calls_this_hour > t.llm_calls_per_hour_max:
            alerts.append(Alert(AlertLevel.WARNING, "resource", "llm_calls",
                                r.llm_calls_this_hour, t.llm_calls_per_hour_max,
                                "LLM 调用频率过高"))
            recommendations.append("启用响应缓存 / 降级推理质量")

        # ── 记忆检查 ──────────────────────────────────────────────────
        m = snap.memory
        self._check("memory", "working_memory_items", m.working_memory_items,
                    t.working_memory_items_max, alerts, recommendations,
                    "Working Memory 过多，建议触发 Episode 写入")
        self._check("memory", "episode_memory_items", m.episode_memory_items,
                    t.episode_memory_items_max, alerts, recommendations,
                    "Episode Memory 过多，建议 Consolidation")
        self._check("memory", "long_term_memory_bytes", m.long_term_memory_bytes,
                    t.long_term_memory_bytes_max, alerts, recommendations,
                    "长期记忆过大，建议激活遗忘策略")
        self._check("memory", "fragmentation_percent", m.fragmentation_percent,
                    t.memory_fragmentation_max, alerts, recommendations,
                    "记忆碎片率过高，建议整理索引")

        # ── Goal 检查 ─────────────────────────────────────────────────
        g = snap.goal
        self._check("goal", "active_goal_count", g.active_goal_count,
                    t.active_goal_max, alerts, recommendations,
                    "活跃 Goal 过多，建议暂停低优先级 Goal")
        self._check("goal", "blocked_goal_count", g.blocked_goal_count,
                    t.blocked_goal_max, alerts, recommendations,
                    "阻塞 Goal 过多，建议分析阻塞原因")
        self._check("goal", "expired_goal_count", g.expired_goal_count,
                    t.expired_goal_max, alerts, recommendations,
                    "过期 Goal 过多，建议归档清理")

        # ── 健康检查 ──────────────────────────────────────────────────
        h = snap.health
        self._check("health", "error_rate", h.error_rate, t.error_rate_max,
                    alerts, recommendations,
                    "错误率过高，建议降级运行模式")
        self._check("health", "avg_latency_ms", h.avg_latency_ms, t.latency_max * 1000,
                    alerts, recommendations,
                    "响应延迟过高，检查阻塞点 / 熔断")
        self._check("health", "crash_count", h.crash_count, t.crash_count_max,
                    alerts, recommendations,
                    "崩溃次数过多，建议全系统健康检查")

        # ── Context 检查 ──────────────────────────────────────────────
        ctx = snap.context
        if ctx.current_tokens > t.context_tokens_critical:
            alerts.append(Alert(AlertLevel.CRITICAL, "context", "tokens",
                                ctx.current_tokens, t.context_tokens_critical,
                                "Context 严重溢出，强制 REFLECT 后丢弃"))
            recommendations.append("强制 REFLECT → 归档到 Episode Memory")
        elif ctx.current_tokens > t.context_tokens_max:
            alerts.append(Alert(AlertLevel.WARNING, "context", "tokens",
                                ctx.current_tokens, t.context_tokens_max,
                                "Context 过长，建议压缩历史轮次"))

        if ctx.attention_fatigue > t.attention_fatigue_critical:
            alerts.append(Alert(AlertLevel.CRITICAL, "context", "fatigue",
                                ctx.attention_fatigue, t.attention_fatigue_critical,
                                "注意力严重疲劳，建议强制 SLEEP"))
            recommendations.append("强制 SLEEP")
        elif ctx.attention_fatigue > t.attention_fatigue_max:
            alerts.append(Alert(AlertLevel.WARNING, "context", "fatigue",
                                ctx.attention_fatigue, t.attention_fatigue_max,
                                "注意力疲劳"))
            recommendations.append("建议切换到简单任务")

        self._check("context", "context_switches", ctx.context_switches_this_hour,
                    t.context_switches_per_hour_max, alerts, recommendations,
                    "上下文切换过于频繁，提示专注模式")

        # ── Identity 检查 ─────────────────────────────────────────────
        if t.identity_integrity_required and not snap.identity.integrity_ok:
            alerts.append(Alert(AlertLevel.CRITICAL, "identity", "integrity",
                                0, 1, f"身份不完整：{snap.identity.missing_fields}"))
            recommendations.append("重新验证 Identity")

        # ── 计算健康分 ────────────────────────────────────────────────
        score = self._calculate_score(alerts, snap)
        report = HealthReport(
            score=round(score, 1),
            alerts=alerts,
            recommendations=recommendations,
            snapshot=snap,
        )
        self._history.append(report)
        self._alert_history.extend(alerts)
        return report

    def _check(
        self,
        dimension: str,
        metric: str,
        current: float,
        threshold: float,
        alerts: list[Alert],
        recommendations: list[str],
        rec_message: str,
    ) -> None:
        if current > threshold:
            level = AlertLevel.WARNING if current < threshold * 1.5 else AlertLevel.CRITICAL
            alerts.append(Alert(level, dimension, metric, current, threshold,
                                f"{dimension}/{metric}: {current:.1f} > {threshold:.1f}"))
            if rec_message not in recommendations:
                recommendations.append(rec_message)

    def _calculate_score(self, alerts: list[Alert], _snap: MonitorSnapshot) -> float:
        """计算健康分 [0, 100]。

        基础分 100，每个 WARNING -5，每个 CRITICAL -15。
        """
        penalty = sum(
            -15 if a.level == AlertLevel.CRITICAL
            else -5 if a.level == AlertLevel.WARNING
            else -1
            for a in alerts
        )
        return max(0.0, min(100.0, 100.0 + penalty))

    # ── Regulator stub ──────────────────────────────────────────────────

    def recommend_actions(self, report: HealthReport | None = None) -> list[RegulatorAction]:
        """从健康报告推导调节动作（Phase 29: 返回动作列表，由后续 Phase 实现执行逻辑）。"""
        rpt = report or self.health_report()
        actions: list[RegulatorAction] = []

        for alert in rpt.alerts:
            dim = alert.dimension
            metric = alert.metric

            if dim == "memory":
                if "working_memory" in metric:
                    actions.append(RegulatorAction.COMPRESS_MEMORY)
                if "episode" in metric:
                    actions.append(RegulatorAction.ARCHIVE_OLD_DATA)
                if "long_term" in metric:
                    actions.append(RegulatorAction.FORGET_LOW_CONFIDENCE)
            elif dim == "goal":
                if "active" in metric:
                    actions.append(RegulatorAction.PAUSE_LOW_PRIORITY)
            elif dim == "health":
                if "error_rate" in metric:
                    actions.append(RegulatorAction.DEGRADE_QUALITY)
            elif dim == "resource":
                if "llm_calls" in metric:
                    actions.append(RegulatorAction.THROTTLE_LLM)
            elif dim == "context":
                if "fatigue" in metric:
                    actions.append(RegulatorAction.TRIGGER_SLEEP)
                if "tokens" in metric:
                    actions.append(RegulatorAction.COMPRESS_CONTEXT)

        # 去重
        seen: set[RegulatorAction] = set()
        unique: list[RegulatorAction] = []
        for a in actions:
            if a not in seen:
                seen.add(a)
                unique.append(a)
        return unique

    # ── Regulator 内生目标引擎（P2-A）──────────────────────────────────

    def regulate(
        self,
        enforcer: Any | None = None,
        now: datetime | None = None,
        novelty: float | None = None,
        attention_fatigue: float | None = None,
    ) -> RegulateResult:
        """全链路调节：check → derive_drives → generate_self_goals。

        enforcer: GoalOriginEnforcer 实例（Phase 25 放行 SELF）；为 None 则无门控
                  （测试/纯推导场景）。
        novelty / attention_fatigue: P2-B 外部覆盖（AgentRuntime Step 4.5 注入
                  AttentionScoringEngine 的 novelty 与 controller.fatigue）；
                  None = 使用 check() 采样值。
        返回 RegulateResult(drives, goals, actions, gated)。
        """
        snapshot = self.check()
        if novelty is not None or attention_fatigue is not None:
            snapshot.context = replace(
                snapshot.context,
                novelty=novelty if novelty is not None else snapshot.context.novelty,
                attention_fatigue=(
                    attention_fatigue
                    if attention_fatigue is not None
                    else snapshot.context.attention_fatigue
                ),
            )
        report = self.health_report(snapshot)
        actions = self.recommend_actions(report)

        regulator = Regulator(thresholds=self._thresholds)
        drives = regulator.derive_drives(snapshot)

        if enforcer is not None:
            gate = lambda goal: bool(enforcer.verify_creation(goal).allowed)
        else:
            gate = None
        goals, gated = regulator.generate_self_goals(drives, now=now, gate=gate)

        return RegulateResult(
            drives=drives,
            goals=goals,
            actions=actions,
            gated=gated,
        )

    # ── Lifecycle / History ─────────────────────────────────────────────

    @property
    def history(self) -> list[HealthReport]:
        return list(self._history)

    @property
    def alert_count(self) -> int:
        return len(self._alert_history)

    def clear_history(self) -> None:
        self._history.clear()
        self._alert_history.clear()
