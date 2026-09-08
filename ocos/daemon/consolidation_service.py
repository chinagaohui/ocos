"""LearningConsolidationService — Runtime 侧学习巩固服务（收敛裁决 R2 RE-HOST）。

依据 docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md：
LearningEngine 是唯一明确的 Legacy→New RE-HOST 候选。本服务承接原
daemon._run_dream_cycle 的巩固触发编排语义，使"Runtime → Consolidation
Service → 巩固语义实现"成为显式宿主链，不再依赖 daemon 内联方法。

职责（一个巩固周期）：
  1. 生命周期相位修复（BOOTING → ACTIVE，保证 sleep/dream 合法迁移）
  2. agent.sleep() → WM 巩固 + 持久化
  3. agent.dream() → lessons 合成 / 快慢通路学习 / belief-pattern 巩固 /
     wisdom 提炼 / 连续性 checkpoint（LearningEngine 语义现驻 agent，
     渐进抽取见裁决文档 R2 第二段）
  4. learning rules 持久化（persist_latest_rules）
  5. 技能合成（同型成功经验 ≥2 次 → SkillGraph，无 LLM）

学习语义仍经 MasterAgent.dream 行使（Dream Host 暂态，随 R2 深化逐步
剥离）；本服务持有全部触发编排权，daemon 不再内联巩固逻辑。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path as _Path
from typing import Any

logger = logging.getLogger(__name__)


class LearningConsolidationService:
    """巩固周期编排器 — 唯一 dream 触发宿主（daemon/未来多运行时共用）。"""

    def __init__(self, db_path: str | None) -> None:
        self._db_path = db_path or ""

    # ── 巩固周期 ─────────────────────────────────────────────────────

    def run_dream_cycle(self, agent: Any) -> dict[str, Any] | None:
        """完整睡眠巩固序列 — 修复生命周期相位后 sleep→dream→persist→skills。"""
        if agent is None or not hasattr(agent, "dream"):
            return None
        self._fix_lifecycle_phase(agent)
        agent.sleep()          # ACTIVE → SLEEPING（WM 巩固 + 持久化）
        out = agent.dream()    # SLEEPING → DREAMING → 巩固 → wake
        self._persist_learning_rules(agent)
        created = self._synthesize_skills()
        logger.info(
            "Dream consolidation: wisdom_total=%s consolidation=%s skills_created=%d",
            (out.get("wisdom_stats") or {}).get("wisdom_total", "?"),
            out.get("consolidation_stats", {}),
            created,
        )
        return out

    # ── 内部环节 ─────────────────────────────────────────────────────

    def _fix_lifecycle_phase(self, agent: Any) -> None:
        """相位修复：BOOTING 状态下直接 dream 会抛非法迁移。

        合法路径要求 BOOTING→ACTIVE→SLEEPING→DREAMING；tick 常驻即活跃，
        BOOTING → ACTIVE 是合法迁移。
        """
        from ocos.agent.lifecycle import LifecyclePhase
        cl = getattr(agent, "_control_loop", None)
        if cl is not None:
            lc = getattr(cl, "_lifecycle", None)
            phase = getattr(lc, "phase", None)
            if phase == LifecyclePhase.BOOTING:
                lc.transition_to_phase(LifecyclePhase.ACTIVE)

    def _persist_learning_rules(self, agent: Any) -> None:
        """FIX-08/FIX-20: dream 后持久化 learning rules（从真实引擎取最新模型）。"""
        if not self._db_path:
            return
        try:
            from ocos.learning.persistence import persist_latest_rules
            saved = persist_latest_rules(agent, self._db_path)
            if saved:
                logger.info("Persisted %d learning rule(s) after dream", saved)
        except Exception:
            logger.debug("dream rules persistence skipped")

    def _synthesize_skills(self) -> int:
        """V2/S1: 技能合成 — 同型成功经验 ≥2 次 → SkillGraph（无 LLM）。

        口径: goal_result 成功记录（decision 以 ✓/✅ 开头）按目标描述
        （context.goal，缺省取 decision 摘要）前 40 字聚合；同型 ≥2 次
        且注册表无同名图 → 合成单步 decision 技能图落 capability.db
        （与主库同目录）。重放读侧 = bridge._skill_replay_hint。
        """
        if not self._db_path:
            return 0
        from ocos.capability.models import Skill, SkillGraph
        from ocos.capability.skill_registry import SkillRegistry
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT decision, context FROM episodes "
                "WHERE source='goal_result' AND action='goal_result' "
                "ORDER BY created_at DESC LIMIT 120").fetchall()
        finally:
            conn.close()
        patterns: dict = {}
        for r in rows:
            d = str(r["decision"] or "").strip()
            if not (d.startswith("✓") or d.startswith("✅")):
                continue
            try:
                ctx = json.loads(r["context"] or "{}")
            except (ValueError, TypeError):
                ctx = {}
            goal = str(ctx.get("goal") or "").strip()
            key = (goal or d.split("→", 1)[0]).strip()[:40]
            if key:
                patterns.setdefault(key, []).append(d[:200])
        if not patterns:
            return 0
        reg = SkillRegistry(
            db_path=str(_Path(self._db_path).parent / "capability.db"))
        reg.init_db()
        try:
            existing = {g.name for g in reg.list_graphs()}
        except Exception:
            existing = set()
        created = 0
        for key, results in patterns.items():
            if len(results) < 2 or key in existing:
                continue
            import uuid as _uuid
            from datetime import datetime, timezone
            skill = Skill(
                id=f"SK-{_uuid.uuid4().hex[:10]}",
                name=key,
                description=("已验证经验（成功 %d 次）：%s"
                             % (len(results), results[0][:120])),
                input_state={"task": key},
                required_capability="decision",
            )
            graph = SkillGraph(
                id=f"SG-{_uuid.uuid4().hex[:10]}",
                name=key,
                description="同型成功经验 ≥2 次自动合成（dream 巩固）",
                skills=[skill],
                entry_point=skill.id,
            )
            try:
                reg.save_skill(skill)
                reg.save_graph(graph)
                created += 1
            except Exception as e:
                logger.debug("skill save failed: %s", e)
        if created:
            logger.info("Synthesized %d skill graph(s) from "
                        "successful experience", created)
            import os
            base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
            audit_dir = (_Path(base).expanduser() if base
                         else _Path.home() / ".ocos" / "audit")
            try:
                audit_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime, timezone as _tz
                with (audit_dir / "learning.jsonl").open(
                        "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": datetime.now(_tz.utc).isoformat(),
                        "type": "skill_synthesized", "count": created,
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return created
