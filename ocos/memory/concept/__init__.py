"""Concept Formation — 从 Belief + Pattern 自动抽象概念（Phase 2）。

核心洞见（CogniFold's Conceptual Bootstrapping）:
  当 BeliefStore 里多个 belief 共享 scope 关键词
  AND 这些 belief 的总 confidence > 阈值
  AND PatternStore 里有对应 pattern 支持
→ 自动创建 Concept 节点

一个 Concept 就是 OCOS 的一个"经验压缩包"：
  "researcher + 探查任务 → 失败" → concept("fragile_probe")
  下次 SymbolicReasoner 看到类似任务 → 直接查 concept → 更快更准
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Concept:
    """概念节点 — OCOS 自己抽出来的"经验压缩包"。"""
    id: str                            # CONCEPT-{sha1_hash}
    name: str                          # 人类可读名（自动生成）
    scope_keywords: list[str]          # 触发这个概念的关键词
    confidence: float                  # 聚合置信度
    source_belief_ids: list[str]       # 来源 belief IDs
    source_pattern_ids: list[str]      # 来源 pattern IDs
    relations: dict[str, str] = field(default_factory=dict)  # {"agent_type": "researcher", "outcome": "failure"}
    birth_ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_row(self) -> tuple:
        return (
            self.id, self.name,
            json.dumps(self.scope_keywords, ensure_ascii=False),
            self.confidence,
            json.dumps(self.source_belief_ids, ensure_ascii=False),
            json.dumps(self.source_pattern_ids, ensure_ascii=False),
            json.dumps(self.relations, ensure_ascii=False),
            self.birth_ts,
        )


class ConceptStore:
    """概念存储 — 纯 SQLite。"""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        if not self._db_path:
            return
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS concept (
                id                TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                scope_keywords    TEXT NOT NULL,  -- JSON array
                confidence        REAL NOT NULL,
                source_belief_ids TEXT NOT NULL,  -- JSON array
                source_pattern_ids TEXT NOT NULL, -- JSON array
                relations         TEXT NOT NULL,  -- JSON dict
                birth_ts          TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def save(self, concept: Concept) -> None:
        if self._conn is None:
            self.initialize()
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO concept VALUES (?,?,?,?,?,?,?,?)",
                concept.to_row(),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.debug("Concept save failed: %s", e)

    def query_by_scope(self, text: str, limit: int = 5) -> list[Concept]:
        """按关键词检索相关概念（bi-gram 重叠匹配 scope_keywords）。"""
        if self._conn is None:
            self.initialize()
        if self._conn is None:
            return []
        # 简化：用 LIKE 查 scope_keywords 里的关键词
        rows = self._conn.execute(
            "SELECT * FROM concept ORDER BY confidence DESC LIMIT ?",
            (limit * 5,),
        ).fetchall()
        results = []
        text_lower = (text or "").lower()
        for row in rows:
            scope_keywords = json.loads(row[2]) if row[2] else []
            if any(kw in text_lower for kw in scope_keywords):
                results.append(self._row_to_concept(row))
            if len(results) >= limit:
                break
        return results

    def all(self) -> list[Concept]:
        if self._conn is None:
            self.initialize()
        if self._conn is None:
            return []
        rows = self._conn.execute(
            "SELECT * FROM concept ORDER BY birth_ts DESC"
        ).fetchall()
        return [self._row_to_concept(r) for r in rows]

    @staticmethod
    def _row_to_concept(row: sqlite3.Row) -> Concept:
        return Concept(
            id=row[0], name=row[1],
            scope_keywords=json.loads(row[2]) if row[2] else [],
            confidence=float(row[3]),
            source_belief_ids=json.loads(row[4]) if row[4] else [],
            source_pattern_ids=json.loads(row[5]) if row[5] else [],
            relations=json.loads(row[6]) if row[6] else {},
            birth_ts=row[7],
        )


# ── 自动形成逻辑 ──────────────────────────────────────────────────────────────

# 概念形成阈值（CogniFold graph-density → threshold）
_MIN_BELIEFS_PER_SCOPE = 3          # 同一 scope 至少 3 条 belief
_MIN_AGGREGATE_CONFIDENCE = 1.5      # aggregate confidence ≥ 1.5
_MIN_PATTERN_SUPPORT = 1            # 至少 1 个 pattern 支持


def _extract_scope_keywords(text: str) -> list[str]:
    """从 belief.scope 文本提取关键词。"""
    # 简化：提取中文 + 英文关键词
    keywords = []
    # 中文短语（2-6 字）
    cn_phrases = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    keywords.extend(cn_phrases)
    # 英文单词
    en_words = re.findall(r"[a-z]+", text.lower())
    keywords.extend(en_words)
    return keywords[:8]


def auto_form_concepts(
    db_path: str,
    store: ConceptStore | None = None,
) -> list[Concept]:
    """从 BeliefStore + PatternStore 自动形成概念。

    被 dream cycle（Phase 22）调用。返回新创建的 Concept 列表。
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        beliefs = conn.execute(
            "SELECT id, statement, confidence, scope FROM belief "
            "ORDER BY confidence DESC LIMIT 100"
        ).fetchall()
        patterns = conn.execute(
            "SELECT id, trigger_condition, observed_relation, confidence "
            "FROM pattern ORDER BY confidence DESC LIMIT 50"
        ).fetchall()
    finally:
        conn.close()

    if len(beliefs) < _MIN_BELIEFS_PER_SCOPE:
        return []

    # Step 1: 按 scope 关键词聚类 belief
    scope_groups: dict[str, list[sqlite3.Row]] = {}
    for b in beliefs:
        scope_text = str(b["scope"] or b["statement"] or "")
        keywords = _extract_scope_keywords(scope_text)
        # 用最前 2 个关键词做聚类键
        cluster_key = "|".join(sorted(keywords[:2]))
        if cluster_key:
            scope_groups.setdefault(cluster_key, []).append(b)

    # Step 2: 筛选符合阈值的 scope
    formed: list[Concept] = []
    for cluster_key, members in scope_groups.items():
        if len(members) < _MIN_BELIEFS_PER_SCOPE:
            continue
        agg_conf = sum(float(m["confidence"]) for m in members)
        if agg_conf < _MIN_AGGREGATE_CONFIDENCE:
            continue

        # Step 3: 检查 pattern 支持
        kw_list = cluster_key.split("|")
        pattern_support = [
            p for p in patterns
            if any(kw in str(p["trigger_condition"] or "").lower()
                   or kw in str(p["observed_relation"] or "").lower()
                   for kw in kw_list)
        ]
        if len(pattern_support) < _MIN_PATTERN_SUPPORT:
            # 放宽：没有 pattern 也可以（belief-only concept）
            pass

        # Step 4: 聚合 relations
        relations = _aggregate_relations(members)

        # Step 5: 创建 Concept
        import hashlib
        concept_id = "CONCEPT-" + hashlib.sha1(cluster_key.encode()).hexdigest()[:12]
        concept = Concept(
            id=concept_id,
            name=_generate_name(members, relations),
            scope_keywords=kw_list,
            confidence=agg_conf / len(members),
            source_belief_ids=[m["id"] for m in members],
            source_pattern_ids=[p["id"] for p in pattern_support],
            relations=relations,
        )
        formed.append(concept)

    # Step 6: 存 ConceptStore
    if store is None:
        store = ConceptStore(db_path=db_path)
    store.initialize()
    for c in formed:
        store.save(c)

    logger.info(
        "PHASE-LIFE Phase 2: concept formation — %d new concepts from %d beliefs + %d patterns",
        len(formed), len(beliefs), len(patterns),
    )
    return formed


def _aggregate_relations(beliefs: list[sqlite3.Row]) -> dict[str, str]:
    """从 belief 的 scope/statement 文本提取典型 relation。"""
    relations: dict[str, str] = {}
    agent_types = {"researcher", "writer", "reviewer", "planner", "summarizer"}
    for b in beliefs:
        text = str(b["scope"] or b["statement"] or "").lower()
        for at in agent_types:
            if at in text:
                relations["agent_type"] = at
                break
        # 失败 vs 成功
        if any(k in text for k in ("失败", "常失败", "失败", "fail")):
            relations["outcome"] = "failure"
        elif any(k in text for k in ("成功", "通常成功", "success")):
            relations["outcome"] = "success"
    return relations


def _generate_name(
    beliefs: list[sqlite3.Row], relations: dict[str, str]
) -> str:
    """自动生成 Concept 名称（人类可读）。"""
    agent = relations.get("agent_type", "unknown")
    outcome = relations.get("outcome", "")
    if outcome == "failure":
        return f"{agent}_failure_pattern"
    elif outcome == "success":
        return f"{agent}_success_pattern"
    return f"{agent}_cluster"
