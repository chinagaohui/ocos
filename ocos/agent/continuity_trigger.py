"""PW-1.3: continuity_trigger — dream 巩固期的身份连续性检查点。

认知连续性子系统上电（此前纯内存、仅测试引用）:
  - LifeMemoryEngine: 近期 Episode → 生命记忆图（重要度筛选）
  - TimelineEngine: 决策/里程碑 → 认知时间线
  - KnowledgeAgingEngine: 智慧条目注册 + 老化分级（FRESH/AGING/LEGACY）
  - IdentityContinuityEngine: 身份快照 + 漂移检测
  - ContinuityCheckpoint: 汇总为检查点，持久化 ~/.ocos/continuity.json
    （跨进程可读，内视面板消费）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ocos.logging import get_logger

logger = get_logger(__name__)

_CONTINUITY_FILE = Path.home() / ".ocos" / "continuity.json"


def run_continuity_checkpoint(hub, tick_id: int = 0,
                              wisdom_count: int = 0) -> dict:
    """dream 巩固期执行一次完整连续性检查点。"""
    from ocos.cognitive_continuity.continuity_checkpoint import (
        ContinuityCheckpoint,
    )
    from ocos.cognitive_continuity.cognitive_timeline import TimelineEngine
    from ocos.cognitive_continuity.identity_continuity import (
        IdentityContinuityEngine,
    )
    from ocos.cognitive_continuity.knowledge_aging import (
        KnowledgeAgingEngine,
    )
    from ocos.cognitive_continuity.life_memory_graph import LifeMemoryEngine

    memory_engine = LifeMemoryEngine()
    timeline = TimelineEngine()
    identity_engine = IdentityContinuityEngine()
    knowledge_engine = KnowledgeAgingEngine()

    # 1. 生命记忆图: 近期 Episode 按重要度筛选记录
    episodes = hub.episode.query_by_time(limit=30)
    for ep in episodes:
        summary = (str(getattr(ep, "decision", "") or "")
                   or str(getattr(ep, "context", {}).get("content", "")))
        importance = float(getattr(ep, "significance_score", 0.5) or 0.5)
        memory_engine.record_experience(
            tick_id=tick_id, summary=summary,
            importance=importance, tags=list(getattr(ep, "tags", []) or []))

    # 2. 时间线: 近期决策记为决策点
    for ep in episodes[:8]:
        decision = str(getattr(ep, "decision", "") or "")[:80]
        if decision:
            timeline.record_decision(tick_id=tick_id, label="dream",
                                     summary=decision)

    # 3. 知识老化: 智慧条目注册（核心知识=confirmed/active）
    try:
        from ocos.agent.wisdom_trigger import WISDOM_USER_ID, load_wisdom_context
        from ocos.personal_memory.wisdom_store import WisdomStore
        from ocos.storage.connection import get_connection
        db_path = getattr(hub, "_db_path", None)
        if db_path and db_path != ":memory:":
            store = WisdomStore.load_from_db(get_connection(db_path))
            coll = store.get_collection(WISDOM_USER_ID)
            for w in coll.items.values():
                knowledge_engine.register(
                    knowledge_id=w.wisdom_id, content=w.principle,
                    is_core=(w.state.value in ("confirmed", "active")))
            knowledge_engine.age_all(current_tick=tick_id)
    except Exception as e:
        logger.debug("knowledge aging skipped: %s", e)

    # 4. 身份快照 + 连续性检查
    snapshot = identity_engine.create_snapshot(
        tick_id=tick_id, label=f"dream@{tick_id}",
        risk_tolerance="moderate",     # 确定性画像: 稳健默认
        decision_style="deliberative",
        key_memories=[m.summary[:60] for m in
                      memory_engine.important_memories()[:5]],
        wisdom_count=wisdom_count,
    )
    check = identity_engine.check_continuity(snapshot)

    checkpoint = ContinuityCheckpoint().create_checkpoint(
        tick_id=tick_id, label=f"dream@{tick_id}",
        identity=identity_engine, memory=memory_engine,
        timeline=timeline, knowledge=knowledge_engine,
    )

    report = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experience_count": checkpoint.experience_count,
        "timeline_past": checkpoint.timeline_past_count,
        "timeline_intent": checkpoint.timeline_intent_count,
        "knowledge": {"fresh": checkpoint.knowledge_fresh,
                      "aging": checkpoint.knowledge_aging,
                      "legacy": checkpoint.knowledge_legacy,
                      "archived": checkpoint.knowledge_archived},
        "identity_anomalies": list(check.anomalies),
        "identity_severity": check.severity,
        "important_memories": [m.summary[:60] for m in
                               memory_engine.important_memories()[:5]],
    }
    _persist(report)
    return report


def _persist(report: dict) -> None:
    """检查点落盘 ~/.ocos/continuity.json（内视面板消费）。"""
    try:
        _CONTINUITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if _CONTINUITY_FILE.exists():
            try:
                data = json.loads(_CONTINUITY_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("history"):
                    history = data["history"]
                elif isinstance(data, dict):
                    history = [data]  # 旧单报告格式迁移
            except ValueError:
                pass
        history.append(report)
        history = history[-26:]   # 保留半年
        _CONTINUITY_FILE.write_text(
            json.dumps({"latest": report, "history": history},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        logger.warning("continuity persist failed: %s", e)


def load_continuity() -> dict:
    """内视消费端 — 读取最近检查点。"""
    try:
        if _CONTINUITY_FILE.exists():
            data = json.loads(_CONTINUITY_FILE.read_text(encoding="utf-8"))
            return data.get("latest", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}
