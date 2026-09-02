"""Phase U: SleepDream — 自主睡眠与梦境。

核心能力：
- 自主睡眠决策：基于稳态、空闲时长、内存压力
- 梦境生成：回放+重组记忆，生成新洞察
- 睡眠周期管理：REM/NREM 交替模拟
- 睡眠报告：巩固统计、梦境日志
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SleepState(Enum):
    """睡眠状态。"""
    AWAKE = auto()
    FALLING_ASLEEP = auto()
    SLEEPING = auto()
    DREAMING = auto()
    WAKING_UP = auto()


class DreamType(Enum):
    """梦境类型。"""
    MEMORY_REPLAY = auto()     # 记忆回放
    PATTERN_SIMULATION = auto()  # 模式模拟
    CREATIVE_COMBO = auto()    # 创意组合
    PROBLEM_SOLVE = auto()     # 问题解决
    EMOTION_PROCESS = auto()   # 情绪处理


@dataclass
class SleepDecision:
    """睡眠决策。"""
    should_sleep: bool
    reason: str
    estimated_duration: float  # 秒
    sleep_type: str  # "power_nap" / "full_sleep" / "rem_cycle"


@dataclass
class DreamRecord:
    """梦境记录。"""
    dream_id: str
    dream_type: DreamType
    content: str
    source_memories: list[str]
    insight: str = ""
    confidence: float = 0.5
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SleepCycleStats:
    """睡眠周期统计。"""
    total_sleeps: int = 0
    total_dreams: int = 0
    total_sleep_time: float = 0.0
    total_dream_time: float = 0.0
    average_sleep_duration: float = 0.0
    average_dream_duration: float = 0.0
    consolidation_count: int = 0
    insights_generated: int = 0
    last_sleep_start: Optional[float] = None
    last_sleep_end: Optional[float] = None
    last_dream_type: Optional[str] = None


class DreamGenerator:
    """梦境生成器。"""

    def __init__(
        self,
        memory_source: Any = None,
        knowledge_graph: Any = None,
    ) -> None:
        self._memory_source = memory_source
        self._knowledge_graph = knowledge_graph
        self._dream_history: list[DreamRecord] = []
        self._max_history = 100

    def generate_dream(
        self,
        dream_type: DreamType,
        source_memories: Optional[list[str]] = None,
    ) -> DreamRecord:
        """生成一个梦境。"""
        memories = source_memories or self._collect_sources(dream_type)
        content = self._create_content(dream_type, memories)
        insight = self._extract_insight(dream_type, content, memories)

        record = DreamRecord(
            dream_id=f"DREM-{int(time.time())}-{random.randint(1000, 9999)}",
            dream_type=dream_type,
            content=content,
            source_memories=memories[:5],
            insight=insight,
            confidence=random.uniform(0.3, 0.8),
        )
        self._dream_history.append(record)
        if len(self._dream_history) > self._max_history:
            self._dream_history = self._dream_history[-self._max_history:]
        return record

    def _collect_sources(self, dream_type: DreamType) -> list[str]:
        """收集梦境素材。"""
        sources = []
        if self._memory_source is not None:
            try:
                if hasattr(self._memory_source, "get_recent"):
                    recent = self._memory_source.get_recent(n=5)
                    sources.extend(str(m) for m in recent)
                elif hasattr(self._memory_source, "replay_important"):
                    important = self._memory_source.replay_important(count=3)
                    sources.extend(str(m) for m in important)
            except Exception:
                pass
        if self._knowledge_graph is not None:
            try:
                if hasattr(self._knowledge_graph, "get_stats"):
                    stats = self._knowledge_graph.get_stats()
                    sources.append(f"knowledge: {stats.get('entity_count', 0)} entities")
            except Exception:
                pass
        return sources or ["default_memory_fragment"]

    def _create_content(self, dream_type: DreamType, sources: list[str]) -> str:
        """创建梦境内容。"""
        if dream_type == DreamType.MEMORY_REPLAY:
            return f"[回放] 重温: {' | '.join(sources[:3])}"
        elif dream_type == DreamType.PATTERN_SIMULATION:
            return f"[模拟] 模式探索: 基于 {' '.join(sources[:2])} 生成假设场景"
        elif dream_type == DreamType.CREATIVE_COMBO:
            combo = " + ".join(random.sample(sources, min(2, len(sources))))
            return f"[创意] 组合联想: {combo}"
        elif dream_type == DreamType.PROBLEM_SOLVE:
            return f"[求解] 问题重构: 从 {sources[0] if sources else '记忆'} 中寻找线索"
        elif dream_type == DreamType.EMOTION_PROCESS:
            return f"[情绪] 处理: 反思近期交互体验"
        return f"[梦境] {sources[0] if sources else '无素材'}"

    def _extract_insight(self, dream_type: DreamType, content: str, sources: list[str]) -> str:
        """提取梦境洞察。"""
        if dream_type == DreamType.MEMORY_REPLAY:
            return f"记忆巩固: 强化了 {len(sources)} 条相关记忆的神经连接"
        elif dream_type == DreamType.PATTERN_SIMULATION:
            return "发现潜在模式关联"
        elif DreamType.CREATIVE_COMBO:
            return "产生新的概念组合可能"
        elif dream_type == DreamType.PROBLEM_SOLVE:
            return "重新框架了问题空间"
        elif dream_type == DreamType.EMOTION_PROCESS:
            return "情绪状态趋于平衡"
        return "梦境处理完成"

    def get_recent_dreams(self, n: int = 5) -> list[DreamRecord]:
        return self._dream_history[-n:]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._dream_history)
        insights = sum(1 for d in self._dream_history if d.insight)
        return {
            "total_dreams": total,
            "dreams_with_insights": insights,
            "insight_rate": insights / total if total > 0 else 0.0,
            "recent_types": [d.dream_type.name for d in self._dream_history[-5:]],
        }


class SleepDreamManager:
    """Phase U: 自主睡眠与梦境管理器。"""

    def __init__(
        self,
        memory_source: Any = None,
        knowledge_graph: Any = None,
        homeostasis: Any = None,
    ) -> None:
        self._state = SleepState.AWAKE
        self._sleep_start: Optional[float] = None
        self._dream_generator = DreamGenerator(
            memory_source=memory_source,
            knowledge_graph=knowledge_graph,
        )
        self._stats = SleepCycleStats()
        self._homeostasis = homeostasis

        # 睡眠参数
        self._idle_threshold = 300.0  # 5分钟无活动触发睡眠
        self._memory_pressure_threshold = 0.8  # 内存使用率阈值
        self._power_nap_duration = 60.0  # 1分钟
        self._full_sleep_duration = 300.0  # 5分钟
        self._rem_cycle_duration = 120.0  # 2分钟

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def state(self) -> SleepState:
        return self._state

    def decide_sleep(self) -> SleepDecision:
        """自主睡眠决策。"""
        # 检查是否应该睡眠
        if self._state != SleepState.AWAKE:
            return SleepDecision(should_sleep=False, reason="already_sleeping", estimated_duration=0.0, sleep_type="none")

        reasons = []
        estimated_duration = 0.0

        # 1. 空闲时长检查
        idle_time = time.time() - (self._stats.last_sleep_end or self._stats.last_sleep_start or time.time())
        if idle_time > self._idle_threshold:
            reasons.append(f"idle_for_{idle_time:.0f}s")

        # 2. 稳态检查
        if self._homeostasis is not None:
            try:
                if hasattr(self._homeostasis, "get_drive"):
                    drive = self._homeostasis.get_drive()
                    if drive < 0.3:  # 低驱力状态
                        reasons.append("low_homeostasis_drive")
            except Exception:
                pass

        # 3. 内存压力（简化）
        # 实际应检查 working_memory 容量

        if not reasons:
            return SleepDecision(should_sleep=False, reason="no_need", estimated_duration=0.0, sleep_type="none")

        # 决定睡眠类型
        if idle_time < self._power_nap_duration * 2:
            sleep_type = "power_nap"
            estimated_duration = self._power_nap_duration
        elif idle_time < self._full_sleep_duration * 3:
            sleep_type = "full_sleep"
            estimated_duration = self._full_sleep_duration
        else:
            sleep_type = "rem_cycle"
            estimated_duration = self._rem_cycle_duration

        return SleepDecision(
            should_sleep=True,
            reason="; ".join(reasons),
            estimated_duration=estimated_duration,
            sleep_type=sleep_type,
        )

    def start_sleep(self) -> dict[str, Any]:
        """开始睡眠。"""
        self._state = SleepState.FALLING_ASLEEP
        self._sleep_start = time.time()
        self._stats.total_sleeps += 1
        self._stats.last_sleep_start = self._sleep_start
        logger.info("Sleep started, type=%s", getattr(self, '_current_sleep_type', 'unknown'))

        # 触发记忆巩固
        return {"status": "falling_asleep", "timestamp": self._sleep_start}

    def enter_dreaming(self, dream_type: Optional[DreamType] = None) -> DreamRecord:
        """进入梦境。"""
        self._state = SleepState.DREAMING
        dtype = dream_type or random.choice(list(DreamType))

        start = time.time()
        dream = self._dream_generator.generate_dream(dtype)
        dream.duration_seconds = time.time() - start
        self._stats.total_dreams += 1
        self._stats.total_dream_time += dream.duration_seconds
        self._stats.last_dream_type = dtype.name

        if dream.insight:
            self._stats.insights_generated += 1

        logger.info("Dream generated: type=%s, insight=%s", dtype.name, dream.insight[:50])
        return dream

    def wake_up(self) -> dict[str, Any]:
        """醒来。"""
        self._state = SleepState.WAKING_UP
        sleep_duration = time.time() - (self._sleep_start or time.time())
        self._stats.total_sleep_time += sleep_duration
        self._stats.last_sleep_end = time.time()
        self._stats.average_sleep_duration = (
            self._stats.total_sleep_time / self._stats.total_sleeps
            if self._stats.total_sleeps > 0 else 0
        )

        self._state = SleepState.AWAKE
        self._sleep_start = None

        return {
            "status": "awake",
            "sleep_duration": sleep_duration,
            "dreams_count": self._stats.total_dreams,
            "insights": self._stats.insights_generated,
        }

    def run_sleep_cycle(self) -> dict[str, Any]:
        """运行完整睡眠周期（睡眠→梦境→醒来）。"""
        decision = self.decide_sleep()
        if not decision.should_sleep:
            return {"status": "no_sleep_needed", "reason": decision.reason}

        self._current_sleep_type = decision.sleep_type
        sleep_result = self.start_sleep()

        # 执行梦境（可多次）
        dreams = []
        num_dreams = max(1, int(decision.estimated_duration / 30))
        for _ in range(num_dreams):
            dream = self.enter_dreaming()
            dreams.append({
                "type": dream.dream_type.name,
                "content": dream.content[:80],
                "insight": dream.insight[:80],
                "duration": dream.duration_seconds,
            })

        wake_result = self.wake_up()
        wake_result["dreams"] = dreams

        logger.info(
            "Sleep cycle complete: %d dreams, %d insights, %.1fs duration",
            len(dreams),
            sum(1 for d in dreams if d.get("insight")),
            wake_result.get("sleep_duration", 0),
        )
        return wake_result

    def get_stats(self) -> dict[str, Any]:
        """获取睡眠统计。"""
        dream_stats = self._dream_generator.get_stats()
        return {
            "current_state": self._state.name,
            "total_sleeps": self._stats.total_sleeps,
            "total_dreams": self._stats.total_dreams,
            "total_sleep_time": self._stats.total_sleep_time,
            "total_dream_time": self._stats.total_dream_time,
            "average_sleep_duration": self._stats.average_sleep_duration,
            "insights_generated": self._stats.insights_generated,
            **dream_stats,
        }

    def generate_report(self) -> str:
        """生成睡眠报告。"""
        stats = self.get_stats()
        recent_dreams = self._dream_generator.get_recent_dreams(3)
        lines = [
            "=" * 50,
            "睡眠与梦境报告",
            "=" * 50,
            f"当前状态: {self._state.name}",
            f"总睡眠次数: {stats['total_sleeps']}",
            f"总梦境次数: {stats['total_dreams']}",
            f"总睡眠时长: {stats['total_sleep_time']:.1f}秒",
            f"平均睡眠时长: {stats['average_sleep_duration']:.1f}秒",
            f"生成洞察数: {stats['insights_generated']}",
            "",
            "近期梦境:",
        ]
        for dream in recent_dreams:
            lines.append(f"  [{dream.dream_type.name}] {dream.content[:50]}...")
            if dream.insight:
                lines.append(f"    洞察: {dream.insight[:60]}")
        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)
