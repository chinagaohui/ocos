"""COG-V2 Phase 4.1 — 记忆经济学：引用强化 + 衰减/过期/归档。

设计依据：cognitive_engine_optimization_plan.md 三、五（Phase 4）
- 语义记忆：30d 无引用衰减（confidence 折半至下限），90d 无引用过期
  （status=deprecated，RecallRouter 不再召回）。
- 程序记忆（【工具配方】）：滚动 7 天数据再沉淀，30d 无引用即过期，
  新鲜配方自然替代旧行。
- 情景记忆：180d 归档（active/consolidated → archived，不删除）。
- 引用即强化：recall_citation 近窗内命中过的知识一律续命，不限年龄。

硬约束：
- 纯确定性、零 LLM；挂在 dream cycle 末尾，全 try 包裹不阻断巩固。
- 只改状态位/置信度，不 DELETE。
- 每类操作有单轮上限，防失控批量更新。
- env OCOS_FORGETTING=0 一键回退（默认开）。
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

FORGET_ENV = "OCOS_FORGETTING"

SEMANTIC_DECAY_DAYS = 30
SEMANTIC_EXPIRE_DAYS = 90
RECIPE_DECAY_DAYS = 30
EPISODE_ARCHIVE_DAYS = 180

# 衰减下限：到 floor 即停止折半（幂等防反复写）
DECAY_FACTOR = 0.5
DECAY_FLOOR = 0.35

# 单轮更新上限（dream 附属流程，分批消化）
MAX_KNOWLEDGE_UPDATES = 200
MAX_EPISODE_UPDATES = 1000

RECIPE_PREFIX = "【工具配方】"

# 时间列归一化：knowledge/episodes 存 ISO（...T...+00:00），
# recall_citation.cited_at 存 'YYYY-MM-DD HH:MM:SS'。统一取前 19 字符、
# T→空格后与 datetime('now','-N day') 字典序可比（均为 UTC）。
_TS = "substr(replace(COALESCE({col}, ''), 'T', ' '), 1, 19)"

# 近窗被引用过的知识 id（跨 subsystem 匹配，artifact_id 即 knowledge.id）
_CITED_RECENT = (
    "EXISTS (SELECT 1 FROM recall_citation c "
    "WHERE c.artifact_id = k.id AND c.artifact_id IS NOT NULL "
    "AND c.cited_at >= datetime('now', ?))"
)


class ForgettingService:
    """dream 遗忘服务：扫描 → 衰减/过期/归档，返回统计 dict。"""

    def __init__(self, db_path: str, *, now: Optional[datetime] = None) -> None:
        self._db_path = db_path
        self._now = now  # 测试注入；生产走 SQL datetime('now')

    def run(self) -> dict:
        stats = {
            "ran": False, "reason": "",
            "semantic_decayed": 0, "semantic_expired": 0,
            "recipes_expired": 0, "episodes_archived": 0,
        }
        if os.environ.get(FORGET_ENV, "1") == "0":
            stats["reason"] = "disabled"
            return stats
        try:
            stats["semantic_decayed"] = self._decay_semantic()
            stats["recipes_expired"] = self._expire_recipes()
            stats["semantic_expired"] = self._expire_semantic()
            stats["episodes_archived"] = self._archive_episodes()
            stats["ran"] = True
        except sqlite3.Error as e:
            # DB 层异常不留半状态误判：每步独立提交，已提交的不回滚
            stats["reason"] = f"db_error: {e}"
            logger.warning("forgetting run aborted: %s", e)
        except Exception as e:  # noqa: BLE001 — dream 附属，不抛主链
            stats["reason"] = f"error: {e}"
            logger.exception("forgetting run failed")
        return stats

    # ── 语义：30d 无引用衰减 ───────────────────────────────────────────

    def _decay_semantic(self) -> int:
        """confidence 折半到下限；只动非终态、非配方（配方走 TTL 过期）。"""
        cutoff = f"-{SEMANTIC_DECAY_DAYS} day"
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            rows = conn.execute(
                f"""
                SELECT id, confidence FROM knowledge k
                WHERE COALESCE(status, '') NOT IN ('rejected', 'deprecated')
                  AND COALESCE(statement, '') NOT LIKE ?
                  AND {_TS.format(col='k.created_at')} < datetime('now', ?)
                  AND COALESCE(confidence, 0) > ?
                  AND NOT {_CITED_RECENT}
                LIMIT ?
                """,
                (f"{RECIPE_PREFIX}%", cutoff, DECAY_FLOOR,
                 cutoff, MAX_KNOWLEDGE_UPDATES),
            ).fetchall()
            n = 0
            for kid, conf in rows:
                new_conf = max(round(float(conf or 0) * DECAY_FACTOR, 4),
                               DECAY_FLOOR)
                cur = conn.execute(
                    "UPDATE knowledge SET confidence = ? "
                    "WHERE id = ? AND COALESCE(confidence, 0) > ?",
                    (new_conf, kid, DECAY_FLOOR),
                )
                n += cur.rowcount
            conn.commit()
            return n
        finally:
            conn.close()

    # ── 语义：90d 无引用过期 ───────────────────────────────────────────

    def _expire_semantic(self) -> int:
        cutoff = f"-{SEMANTIC_EXPIRE_DAYS} day"
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            cur = conn.execute(
                f"""
                UPDATE knowledge SET status = 'deprecated',
                    updated_at = ?
                WHERE COALESCE(status, '') NOT IN ('rejected', 'deprecated')
                  AND COALESCE(statement, '') NOT LIKE ?
                  AND {_TS.format(col='created_at')} < datetime('now', ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM recall_citation c
                      WHERE c.artifact_id = knowledge.id
                        AND c.artifact_id IS NOT NULL
                        AND c.cited_at >= datetime('now', ?))
                """,
                (self._now_iso(), f"{RECIPE_PREFIX}%", cutoff, cutoff),
            )
            n = min(cur.rowcount, MAX_KNOWLEDGE_UPDATES)
            conn.commit()
            return n
        finally:
            conn.close()

    # ── 程序：配方 30d 无引用过期（滚动 7 天再沉淀自然替代）────────────

    def _expire_recipes(self) -> int:
        cutoff = f"-{RECIPE_DECAY_DAYS} day"
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            cur = conn.execute(
                f"""
                UPDATE knowledge SET status = 'deprecated',
                    updated_at = ?
                WHERE COALESCE(status, '') NOT IN ('rejected', 'deprecated')
                  AND statement LIKE ?
                  AND {_TS.format(col='created_at')} < datetime('now', ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM recall_citation c
                      WHERE c.artifact_id = knowledge.id
                        AND c.artifact_id IS NOT NULL
                        AND c.cited_at >= datetime('now', ?))
                """,
                (self._now_iso(), f"{RECIPE_PREFIX}%", cutoff, cutoff),
            )
            n = min(cur.rowcount, MAX_KNOWLEDGE_UPDATES)
            conn.commit()
            return n
        finally:
            conn.close()

    # ── 情景：180d 归档（active/consolidated → archived，不删除）──────

    def _archive_episodes(self) -> int:
        cutoff = f"-{EPISODE_ARCHIVE_DAYS} day"
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            cur = conn.execute(
                f"""
                UPDATE episodes SET status = 'archived'
                WHERE COALESCE(status, 'active') IN ('active', 'consolidated')
                  AND {_TS.format(col='created_at')} < datetime('now', ?)
                LIMIT ?
                """,
                (cutoff, MAX_EPISODE_UPDATES),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def _now_iso(self) -> str:
        return (self._now or datetime.now(timezone.utc)).isoformat()
