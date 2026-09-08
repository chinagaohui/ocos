"""L2-4: self_improve 待批引擎流 — 反思产物 → 自改进提案 → 待批队列。

升级方案 v1.0 §L2: self_improve 上电 — 对接 L1 ReflectionEngine 产物，
自改进提案入待批（V8 约束下：提案不自动执行，人工批准 = authority）。

链路（复用既有治理链，不重写）:
    lesson/reflection episodes → 提炼改进点（确定性规则）
      → self_evolution_link.propose_upgrade（主权冻结域守门 + 治理链）
        → 通过者入 pending_actions（action_type='self_upgrade'）
          → 人工 `ocos approvals approve` → bridge _handler_self_upgrade
            → apply_approved（迁移+快照+真实应用+记账）

诚实性约束:
  - 只读反思产物，不发明改进点（episode.decision 即教训原文）
  - 去重：同一改进点不重复入队（含待批/已执行记录比对）
  - 限速：单次最多提取 limit 条，提案入待批即止（绝不自动执行）
"""

from __future__ import annotations

import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

_IMPROVE_SOURCES = ("lesson", "reflection", "failure_lesson")


def _recent_improvement_episodes(db_path: str, limit: int) -> list[dict]:
    """取最近的 lesson/reflection episodes（含 tags LIKE lesson 兜底）。"""
    if not db_path:
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows: list = []
    try:
        placeholders = ", ".join("?" for _ in _IMPROVE_SOURCES)
        rows = conn.execute(
            f"SELECT id, decision, tags, source FROM episodes "
            f"WHERE (source IN ({placeholders}) OR tags LIKE '%lesson%') "
            f"AND LENGTH(decision) >= 8 "
            f"ORDER BY created_at DESC LIMIT ?",
            (*_IMPROVE_SOURCES, limit)).fetchall()
    except sqlite3.Error as e:
        logger.debug("improve_link episode query failed: %s", e)
    finally:
        conn.close()
    out = []
    for ep_id, decision, tags_json, source in rows:
        try:
            tags = json.loads(tags_json or "[]")
        except ValueError:
            tags = []
        out.append({"id": ep_id, "decision": str(decision or "").strip(),
                    "tags": tags, "source": source})
    return out


def _already_proposed(db_path: str, change: str) -> bool:
    """去重：同改进点已在待批/已执行记录中 → 跳过。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        marker = json.dumps({"change": change}, ensure_ascii=False)[1:-1][:120]
        row = conn.execute(
            "SELECT COUNT(*) FROM pending_actions WHERE "
            "action_type = 'self_upgrade' AND payload_json LIKE ?",
            (f"%{marker}%",)).fetchone()
        return bool(row and row[0])
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def propose_from_reflections(db_path: str, limit: int = 10) -> dict:
    """反思产物 → 治理链提案 → 待批。返回统计（供日志/测试断言）。"""
    stats = {"episodes": 0, "proposed": 0, "pending_enqueued": 0,
             "rejected": 0, "duplicates": 0, "pending_ids": []}
    episodes = _recent_improvement_episodes(db_path, limit)
    stats["episodes"] = len(episodes)
    if not episodes:
        return stats

    from ocos.agent.self_evolution_link import propose_upgrade
    from ocos.execution.pending import PendingStore
    store = PendingStore(db_path=db_path)

    for ep in episodes:
        change = ep["decision"]
        title = f"自改进（lesson {ep['id'][-8:]}）"
        if _already_proposed(db_path, change):
            stats["duplicates"] += 1
            continue
        try:
            result = propose_upgrade(title, change)
        except Exception as e:
            logger.debug("propose_upgrade failed for %s: %s", ep["id"], e)
            continue
        if not result.get("accepted"):
            stats["rejected"] += 1
            continue
        stats["proposed"] += 1
        pid = store.enqueue(
            action_type="self_upgrade",
            target="~/.ocos/self_knowledge.md",
            payload={"proposal_id": result.get("proposal_id", ""),
                     "title": title, "change": change},
            text=title,
            source="l2_self_improve")
        stats["pending_ids"].append(pid)
        stats["pending_enqueued"] += 1
    if stats["pending_enqueued"]:
        logger.info("improve_link: %s", stats)
    return stats


__all__ = ["propose_from_reflections"]
