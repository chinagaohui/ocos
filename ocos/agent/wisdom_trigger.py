"""PW-1.1: wisdom_trigger — dream 巩固期从 Episode 提炼智慧候选。

互补学习系统（CLS）的慢通路落地:
  快通路: 对话/任务 → Episode（已完成, ChatResponder._remember_conversation）
  慢通路: 本模块 — dream() 巩固时把重复出现的成败经验聚类成
          ExperiencePattern → PatternInterpreter 解释 → WisdomItem 候选
          → WisdomStore（SQLite 落盘）→ ChatResponder 上下文回注

设计约束:
  - 纯确定性（零 LLM）: 统计聚类即可解释的才成智慧
  - 幂等: 同一组 pattern 产出同一 wisdom_id（INSERT OR IGNORE）
  - 上电方式: master_agent.dream() 巩固完成后调用 consolidate_wisdom()
"""

from __future__ import annotations

from ocos.logging import get_logger

logger = get_logger(__name__)

WISDOM_USER_ID = "master"   # 单主人模型 — 与 ChatResponder 消费端一致


def _wisdom_count(store) -> int:
    """全部智慧条数（candidate+confirmed+active — 候选也是资产）。"""
    coll = store.get_collection(WISDOM_USER_ID)
    return len(coll.items) if coll else 0


def consolidate_wisdom(hub, current_tick: int = 0,
                       min_episodes: int = 2) -> dict:
    """从 hub 的近期 Episode 聚类经验模式并提炼智慧候选。

    Args:
        hub: MemoryHub（已 initialize）
        current_tick: 巩固时的 tick（参与 wisdom_id 幂等）
        min_episodes: 形成一个 ExperiencePattern 所需的最少同类 Episode

    Returns:
        {patterns, candidates, persisted, wisdom_total}
    """
    from ocos.personal_memory.pattern_interpreter import PatternInterpreter
    from ocos.personal_memory.wisdom_store import WisdomStore
    from ocos.self.self_types import ExperiencePattern

    # FIX: active_only=False — 和 _consolidate_episodes 同修复.
    # 只扫 ACTIVE 会导致第一次 dream 后所有 episode 被 consolidated → 后续 wisdom 永远空.
    episodes = hub.episode.query_by_time(limit=200, active_only=False)
    if len(episodes) < min_episodes:
        return {"patterns": 0, "candidates": 0, "persisted": 0,
                "wisdom_total": 0, "reason": "insufficient_episodes"}

    # 1. 聚类: (action, 成败) → ExperiencePattern
    groups: dict[tuple[str, bool], list] = {}
    for ep in episodes:
        outcome = getattr(ep, "outcome", {}) or {}
        success = bool(outcome.get("success", True))
        action = getattr(ep, "action", "") or "unknown"
        groups.setdefault((action, success), []).append(ep)

    patterns = []
    for (action, success), eps in groups.items():
        if len(eps) < min_episodes:
            continue
        # P2-3: wisdom label 去模板化 — 加入 action 类型 + 样本量
        result_word = "成功" if success else "失败"
        total_ep = len(eps)
        # 从 condition 里提取 agent 类型
        agents = set()
        for ep in eps:
            cond = getattr(ep, "condition", "") or ""
            if "agent=" in cond:
                ag = cond.split("agent=")[1].split(",")[0].strip()
                if ag and ag not in ("self_fix", "unknown"):
                    agents.add(ag)
        agent_hint = f"（{','.join(sorted(agents))}）" if agents else ""
        label = f"「{action}」类任务{result_word}率高 {agent_hint} — {total_ep} 次观察"
        patterns.append(ExperiencePattern(
            pattern_id=f"PAT-{action}-{'ok' if success else 'fail'}",
            label=label,  # P2-3: 不再硬编码"重复成功的「X」类经历"
            category="successful" if success else "failure",
            frequency=total_ep,
            confidence=min(0.95, 0.5 + 0.05 * total_ep),
            evidence_ids=tuple(e.id for e in eps),
            abstracted_at_tick=current_tick,
        ))

    # 2. 解释 → 候选智慧 → 落盘
    db_path = getattr(hub, "_db_path", None)
    connection = None
    if db_path and db_path != ":memory:":
        from ocos.storage.connection import get_connection
        connection = get_connection(db_path)
        # 自愈建表（CLI/测试独立运行时未经 run.py ensure_schema）
        connection.execute(
            """CREATE TABLE IF NOT EXISTS wisdom_items (
                user_id TEXT NOT NULL,
                wisdom_id TEXT NOT NULL,
                principle TEXT NOT NULL,
                state TEXT NOT NULL,
                source_patterns TEXT NOT NULL DEFAULT '[]',
                evidence TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (user_id, wisdom_id)
            )""")
        connection.commit()
    store = WisdomStore.load_from_db(connection)
    store.get_or_create_collection(WISDOM_USER_ID)

    interpreter = PatternInterpreter()
    candidates = 0
    persisted = 0
    for category in ("successful", "failure"):
        group = [p for p in patterns if p.category == category]
        if not group:
            continue
        # 同一组 qualified patterns 共享同一候选对象 — 每候选只处理一次
        seen_ids: set[str] = set()
        for result in interpreter.interpret(group, current_tick):
            if result.rejected or result.candidate_wisdom is None:
                continue
            wisdom = result.candidate_wisdom
            if wisdom.wisdom_id in seen_ids:
                continue
            seen_ids.add(wisdom.wisdom_id)
            candidates += 1
            if store.get_wisdom(WISDOM_USER_ID, wisdom.wisdom_id) is not None:
                # 幂等跳过 — 已在库（load_from_db 保证内存即 DB 真相）
                logger.debug("Wisdom idempotent skip: %s", wisdom.wisdom_id)
                continue
            store.add_wisdom(WISDOM_USER_ID, wisdom)
            persisted += 1
            logger.info("Wisdom candidate persisted: %s",
                        wisdom.principle[:60])

    return {"patterns": len(patterns), "candidates": candidates,
            "persisted": persisted, "wisdom_total": _wisdom_count(store)}


def load_wisdom_context(db_path: str, limit: int = 5) -> list[str]:
    """ChatResponder 消费端 — 读已沉淀的智慧原则（供上下文回注）。"""
    if not db_path or db_path == ":memory:":
        return []
    try:
        from ocos.personal_memory.wisdom_store import WisdomStore
        from ocos.storage.connection import get_connection
        store = WisdomStore.load_from_db(get_connection(db_path))
        coll = store.get_collection(WISDOM_USER_ID)
        items = list(coll.items.values()) if coll else []
        # confirmed/active 优先, 候选垫后
        items.sort(key=lambda w: 0 if w.state.value in ("confirmed", "active")
                   else 1)
        return [w.principle[:80] for w in items[:limit]]
    except Exception as e:
        logger.debug("wisdom context read failed: %s", e)
        return []
