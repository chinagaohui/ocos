"""Lightweight Symbolic Simulator — OCOS 的内部世界模型（Phase 3）。

核心洞见（WALL-E NeurIPS 2025 + ExoPredicator 2025）:
 给定一个 Plan [step1, step2, step3, ...]
  → SymbolicSimulator.simulate(plan, agent)
  → {success_prob, risk_points, expected_outcome}

实现：
  1. 每个 step → 查 PatternStore 有没有 "X action triggers Y" 规则
  2. step 成功率 → 从 BeliefStore 取 confidence / PatternStore
  3. step 之间的依赖 → 前向推演（如果 step1 失败 → step2 还能执行吗）
  4. 聚合 → 整个 plan 的成功率分布 + 风险点

不做像素级渲染，只做符号级概率推演——够 OCOS 用了。
零 LLM 调用。
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StepSimulation:
    """单个 step 的模拟结果。"""
    step_index: int
    step_text: str
    agent_type: str
    base_success_prob: float       # 基础成功率
    risk_probability: float        # 风险（失败）概率
    confidence: float               # 这个预测的置信度
    dependencies: list[int] = field(default_factory=list)  # 依赖哪些 step
    notes: list[str] = field(default_factory=list)  # 建议


@dataclass
class SimulationResult:
    """整个 plan 的模拟结果。"""
    plan_success_prob: float       # 整体成功率（各 step 串行概率）
    risk_points: list[StepSimulation]  # 风险最高的 steps
    step_simulations: list[StepSimulation]
    counterfactuals: list[dict] = field(default_factory=list)  # 反事实推演

    def summary(self) -> str:
        lines = [f"Plan success prob: {self.plan_success_prob:.0%}"]
        if self.risk_points:
            lines.append("Risk points:")
            for r in self.risk_points[:3]:
                lines.append(f"  Step {r.step_index}: risk={r.risk_probability:.0%} {r.step_text[:50]}")
        if self.counterfactuals:
            for cf in self.counterfactuals:
                lines.append(f"  IF step{cf['step']} fails → overall prob={cf['overall_prob']:.0%}")
        return "\n".join(lines)


class SymbolicSimulator:
    """轻量符号模拟器。

    依赖 PatternStore（trigger_condition → observed_relation 规则）
    + BeliefStore（agent_type 历史成功率）。
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def simulate(
        self,
        steps: list[str],
        agent_type: str | None = None,
        context: str | None = None,
    ) -> SimulationResult:
        """模拟一个 plan 的执行。

        Args:
            steps: plan 的每个 step 描述
            agent_type: 执行 agent 类型
            context: 额外上下文（合并进相似度匹配）
        """
        if not steps:
            return SimulationResult(
                plan_success_prob=0.5,
                risk_points=[],
                step_simulations=[],
            )

        conn = self._connect()
        if conn is None:
            return self._fallback(steps, agent_type)

        # Step 1: 预加载 Pattern + Belief
        patterns = self._load_patterns(conn)
        agent_success_rates = self._load_agent_success_rates(conn)
        conn.close()

        # Step 2: 每个 step 单独评估
        sims: list[StepSimulation] = []
        for i, step_text in enumerate(steps):
            base_prob, risk, conf, notes = self._eval_step(
                step_text, agent_type, patterns, agent_success_rates
            )
            sims.append(StepSimulation(
                step_index=i,
                step_text=step_text,
                agent_type=agent_type or "unknown",
                base_success_prob=base_prob,
                risk_probability=1.0 - base_prob,
                dependencies=[],
                confidence=conf,
                notes=notes,
            ))

        # Step 3: 串行聚合成功率（每步独立的话直接相乘）
        overall = 1.0
        for s in sims:
            overall *= s.base_success_prob

        # Step 4: 反事实推演：如果最脆弱的 step 失败了，整体概率怎样
        counterfactuals = []
        fragile = sorted(sims, key=lambda s: s.risk_probability, reverse=True)[:2]
        for f in fragile:
            reduced = 1.0
            for s in sims:
                if s.step_index == f.step_index:
                    reduced *= 0.1  # 这个 step 失败了
                else:
                    reduced *= s.base_success_prob
            counterfactuals.append({
                "step": f.step_index,
                "if_fails": f.step_text[:50],
                "overall_prob": round(reduced, 3),
            })

        risk_points = sorted(sims, key=lambda s: s.risk_probability, reverse=True)[:3]

        return SimulationResult(
            plan_success_prob=round(overall, 3),
            risk_points=risk_points,
            step_simulations=sims,
            counterfactuals=counterfactuals,
        )

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None

    def _fallback(
        self, steps: list[str], agent_type: str | None
    ) -> SimulationResult:
        """无 DB 时的 fallback — 每步给 0.7 基础成功率。"""
        sims = [
            StepSimulation(
                step_index=i, step_text=s,
                agent_type=agent_type or "unknown",
                base_success_prob=0.7, risk_probability=0.3,
                dependencies=[], confidence=0.0, notes=["no DB data"],
            )
            for i, s in enumerate(steps)
        ]
        overall = 0.7 ** len(sims) if sims else 0.5
        return SimulationResult(
            plan_success_prob=overall,
            risk_points=sims,
            step_simulations=sims,
        )

    def _load_patterns(
        self, conn: sqlite3.Connection
    ) -> list[tuple[str, str, float]]:
        """(trigger, relation, confidence) 列表。"""
        try:
            rows = conn.execute(
                "SELECT trigger_condition, observed_relation, confidence "
                "FROM pattern ORDER BY confidence DESC LIMIT 50"
            ).fetchall()
            return [
                (str(r["trigger_condition"] or "").lower(),
                 str(r["observed_relation"] or "").lower(),
                 float(r["confidence"]))
                for r in rows
            ]
        except sqlite3.Error:
            return []

    def _load_agent_success_rates(
        self, conn: sqlite3.Connection
    ) -> dict[str, float]:
        """{agent_type: 历史成功率}。"""
        try:
            rows = conn.execute(
                "SELECT action, outcome FROM episodes "
                "WHERE source='goal_result' AND datetime(created_at) >= datetime('now','-30 days')"
            ).fetchall()
        except sqlite3.Error:
            return {}

        success_by_agent: dict[str, list[bool]] = {}
        for r in rows:
            action = str(r["action"] or "").split(".")[0]
            if action not in {"researcher", "writer", "reviewer", "planner", "summarizer"}:
                continue
            try:
                oc = json.loads(r["outcome"] or "{}")
            except Exception:
                continue
            ok = bool(oc.get("success", True))
            success_by_agent.setdefault(action, []).append(ok)

        return {
            agent: sum(results) / len(results) if results else 0.5
            for agent, results in success_by_agent.items()
        }

    def _eval_step(
        self,
        step_text: str,
        agent_type: str | None,
        patterns: list[tuple[str, str, float]],
        agent_rates: dict[str, float],
    ) -> tuple[float, float, float, list[str]]:
        """评估单个 step → (base_prob, risk, confidence, notes)。"""
        text_lower = step_text.lower()
        notes: list[str] = []

        # 1. Agent 历史成功率
        agent_prob = 0.7  # 先验
        if agent_type and agent_type in agent_rates:
            agent_prob = agent_rates[agent_type]

        # 2. Pattern 匹配
        pattern_hits: list[float] = []
        for trigger, relation, conf in patterns:
            if trigger and trigger in text_lower:
                pattern_hits.append(conf)
                # relation 含 failure → 拉低 base_prob
                if any(k in relation for k in ("fail", "error", "失败", "错")):
                    agent_prob = min(agent_prob, 0.3)
                    notes.append(f"pattern: {trigger}→{relation[:40]}")

        # 3. 关键词扫描（硬编码）
        risk_keywords = [
            ("探查", "探查未知模块", 0.3),
            ("模块", "涉及模块操作", 0.4),
            ("执行", "执行 shell/命令", 0.5),
            ("部署", "部署操作", 0.3),
        ]
        for kw, note, prob in risk_keywords:
            if kw in text_lower or kw in step_text:
                agent_prob = min(agent_prob, prob)
                notes.append(f"risk: {note}")

        # 4. 置信度
        conf = 0.2  # 基础
        if pattern_hits:
            conf += sum(pattern_hits) / len(pattern_hits) * 0.3
        if agent_type and agent_type in agent_rates:
            conf += 0.2

        return max(0.05, min(0.99, agent_prob)), 1.0 - agent_prob, min(conf, 1.0), notes
