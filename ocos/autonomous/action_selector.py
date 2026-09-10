"""ActionSelector — 轻量 ACT-R 产生式规则引擎.

参考 ACT-R 认知架构的"产生式规则 + 目标驱动模块竞争"思想:
  - 产生式规则 = (conditions → module_name, priority)
  - 每 tick 评估所有规则, 按条件匹配度 × priority 排序
  - 选出 top-N 模块执行 (默认按优先级从高到低全跑)

不改变 daemon 的固定调用点 (dream_interval_ticks 仍触发),
而是在触发窗口内按规则决定跑哪些模块、什么顺序。

信号源:
  - EpistemicDrive.curiosity (suggest_explore/growth 数量)
  - PredictionGapTracker (预测误差 → gap 平均值)
  - knowledge_store_size (知识沉淀密度)
  - autonomy_level (L0-L3 约束)
  - time_since_last_run (每个模块的上次运行时间 → 饥饿度)

每个模块:
  - consolidation      (dream 巩固)
  - ingest_experience  (经验摄入)
  - epistemic_research (外部调研)
  - daily_self_evolution (自进化方案)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ── 认知信号快照 ────────────────────────────────────────────────

@dataclass
class CognitiveState:
    """当前认知状态 — 规则引擎的条件输入."""
    autonomy_level: int = 2          # L0-L3
    braked: bool = False
    curiosity_explore: int = 0       # suggest_explore 数量
    curiosity_growth: int = 0        # suggest_growth 数量
    avg_prediction_gap: float = 0.0  # 预测误差平均值 (0-1)
    knowledge_total: int = 0         # knowledge 表总行数
    knowledge_recent_rate: float = 0.0  # 近 20 条 / 近 1000 条的密度
    pattern_total: int = 0
    belief_total: int = 0
    wisdom_active: int = 0           # wisdom 表 state='active'
    pending_evolutions: int = 0      # evolution_artifacts status='pending'
    dream_cycle_tick: bool = False   # 当前 tick 是否是 dream_interval 触发

    def __repr__(self) -> str:
        return (
            f"CognitiveState(L{self.autonomy_level}{' braked' if self.braked else ''}, "
            f"expl={self.curiosity_explore},growth={self.curiosity_growth}, "
            f"gap={self.avg_prediction_gap:.2f}, k={self.knowledge_total}, "
            f"pending_evo={self.pending_evolutions})"
        )


# ── 产生式规则 ──────────────────────────────────────────────────

@dataclass
class ProductionRule:
    """产生式规则: conditions → module_name, with priority."""
    name: str
    condition: Callable[[CognitiveState], float]  # 匹配度 0.0-1.0
    module: str                                    # consolidation / ingest / research / evolution
    priority: float = 0.5                          # 基础优先级
    cooldown_ticks: int = 0                        # 最小运行间隔

    def score(self, state: CognitiveState, ticks_since_last: int) -> float:
        """综合评分 = condition_match × priority, cooldown 未到时返回 0."""
        if self.cooldown_ticks > 0 and ticks_since_last < self.cooldown_ticks:
            return 0.0
        match = self.condition(state)
        # braked 或 L0 时所有模块 score 减半 (除 consolidation 外)
        if state.braked and self.module != "consolidation":
            match *= 0.3
        return match * self.priority


# ── 构建规则库 ──────────────────────────────────────────────────

def build_default_rules() -> list[ProductionRule]:
    """ACT-R 风格的默认产生式规则集.

    规则设计原则:
      1. consolidation (dream) 是基础 — 每个 dream cycle 必跑 (priority=1.0)
      2. ingest_experience 在 autonomy >= L1 时必跑 (从经验学)
      3. epistemic_research 在 curiosity 高时优先 (好奇心驱动)
      4. daily_self_evolution 在 pending 多 或 knowledge 密度低时触发
      5. 高 gap (预测失败多) → 优先 research 找答案
      6. 低 knowledge_density → 优先 ingest+research 补充
    """
    return [
        # ── Rule 1: consolidation (dream) — 基础必跑 ──
        ProductionRule(
            name="consolidation_always",
            condition=lambda s: 1.0 if s.dream_cycle_tick else 0.0,
            module="consolidation",
            priority=1.0,
        ),

        # ── Rule 2: ingest_experience — 经验摄入 ──
        # autonomy >= L1 且 dream cycle 时跑
        ProductionRule(
            name="ingest_on_dream_L1plus",
            condition=lambda s: (
                1.0 if (s.dream_cycle_tick and s.autonomy_level >= 1) else 0.0
            ),
            module="ingest_experience",
            priority=0.8,
        ),

        # ── Rule 3: epistemic_research — 外部调研 (好奇心驱动) ──
        # curiosity 有建议 或 prediction gap 高 → 优先调研
        ProductionRule(
            name="research_when_curious",
            condition=lambda s: (
                min(1.0, (s.curiosity_explore + s.curiosity_growth) / 3 + s.avg_prediction_gap * 2)
                if (s.dream_cycle_tick and s.autonomy_level >= 1)
                else 0.0
            ),
            module="epistemic_research",
            priority=0.9,
        ),

        # ── Rule 4: daily_self_evolution — 自进化方案生成 ──
        # 每 2880 ticks (≈4h) 的 dream cycle 上触发 (daemon 侧还会再 gate 一次)
        # pending_evolutions 多 或 knowledge 密度低 也可以触发
        ProductionRule(
            name="evolve_on_schedule",
            condition=lambda s: (
                0.8 if (s.dream_cycle_tick and s.autonomy_level >= 2) else 0.0
            ),
            module="daily_self_evolution",
            priority=0.7,
            cooldown_ticks=2880,
        ),
    ]


# ── ActionSelector ──────────────────────────────────────────────

class ActionSelector:
    """轻量 ACT-R 产生式规则引擎 — 动态选择下一个执行的模块."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._rules = build_default_rules()
        self._last_run_ticks: dict[str, int] = {}

    def snapshot_state(self) -> CognitiveState:
        """从 DB + EpistemicDrive 快照当前认知状态."""
        state = CognitiveState()
        state.dream_cycle_tick = False  # daemon 侧会在调用时设置
        try:
            from ocos.execution.autonomy import get_autonomy_level
            state.autonomy_level = get_autonomy_level()
        except Exception:
            state.autonomy_level = 2

        # DB 快速计数
        try:
            c = sqlite3.connect(self._db_path)
            state.knowledge_total = c.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            state.pattern_total = c.execute("SELECT COUNT(*) FROM pattern").fetchone()[0]
            state.belief_total = c.execute("SELECT COUNT(*) FROM belief").fetchone()[0]
            state.wisdom_active = c.execute(
                "SELECT COUNT(*) FROM wisdom_items WHERE state='active'"
            ).fetchone()[0]
            state.pending_evolutions = c.execute(
                "SELECT COUNT(*) FROM evolution_artifacts WHERE status='pending'"
            ).fetchone()[0]
            # 知识密度: 近 20 条 / 总条数
            recent = c.execute(
                "SELECT COUNT(*) FROM knowledge WHERE rowid > "
                "(SELECT MAX(rowid) FROM knowledge) - 20"
            ).fetchone()[0]
            state.knowledge_recent_rate = recent / max(state.knowledge_total, 1)
            c.close()
        except Exception as e:
            logger.debug("ActionSelector DB snapshot failed: %s", e)

        # EpistemicDrive 信号
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker, EpistemicDrive
            tracker = PredictionGapTracker(db_path=self._db_path)
            drive = EpistemicDrive(tracker=tracker, db_path=self._db_path, top_n=5)
            state.curiosity_explore = len(list(drive.suggest_explore()))
            state.curiosity_growth = len(list(drive.suggest_growth()))
        except Exception:
            pass

        return state

    def select_modules(
        self,
        state: CognitiveState,
        *,
        cycle_count: int = 0,
        braked: bool = False,
        max_modules: int = 4,
    ) -> list[tuple[str, float]]:
        """评估所有规则 → 按 score 排序 → 返回要执行的模块列表.

        Returns: [(module_name, score), ...] 按 score 降序
        """
        state.braked = braked
        scored: list[tuple[float, str, ProductionRule]] = []

        for rule in self._rules:
            ticks_since = cycle_count - self._last_run_ticks.get(rule.module, 0)
            score = rule.score(state, ticks_since)
            if score > 0.0:
                scored.append((score, rule.module, rule))

        # 降序排
        scored.sort(key=lambda x: -x[0])

        selected = [(mod, score) for score, mod, _ in scored[:max_modules]]
        for mod, _ in selected:
            self._last_run_ticks[mod] = cycle_count

        if selected:
            logger.debug(
                "ActionSelector → %s",
                ", ".join(f"{m}({s:.2f})" for m, s in selected),
            )
        return selected

    def mark_run(self, module: str, cycle_count: int) -> None:
        """标记某模块刚跑过 (由 daemon 在执行后调用)."""
        self._last_run_ticks[module] = cycle_count


__all__ = [
    "ActionSelector",
    "ProductionRule",
    "CognitiveState",
    "build_default_rules",
]
