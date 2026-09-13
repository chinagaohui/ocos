"""P0-4 B — Decision₂ Trace（D→Thinking→Decision₂→Action₂ 同链 attribution identity）。

目的（解锁 P0-4 F4/F5）：让 P0-4 能在同一条 identity 上回答
"这次 Decision₂ 到底有没有消费那个 D？"，而不是只能证明"S2 更新后 Prompt 变了"。

同链 identity：
    thinking_trace_id
        ├── self_version
        ├── consumed_delta_ids[]      (committed SelfClaim ids 进入本决策所见投影)
        ├── consumed_evidence_ids[]
        ↓
    decision_id  → decision / strategy / action / action_ids[] → y_ref/ Y

本模块只做**记录**（append-only），零行为偏移：不改 prompt、不改采样、不改控制流。
不重构 DecisionRuntime / Planning / DecisionBridge / TaskDAG / TextGenerator。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.schema import (
    TABLE_DECISION_TRACE,
    TABLE_DECISION_TRACE_DECISION,
)

logger = logging.getLogger(__name__)


@dataclass
class ThinkingTrace:
    """一次产生决策的 Thinking 快照：决策时刻所见 S2 版本与已消费的 D。"""

    thinking_trace_id: str
    self_version: int = 0
    consumed_delta_ids: tuple[str, ...] = ()
    consumed_evidence_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DecisionRecord:
    """与 thinking_trace_id 同链的决策记录：决策/策略/动作身份 → Y。"""

    decision_id: str
    thinking_trace_id: str
    decision: str = ""
    strategy: str = ""
    action: str = ""
    action_ids: tuple[str, ...] = ()
    y_ref: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionTraceStore:
    """ThinkingTrace / DecisionRecord 的 append-only 持久化。只记录、不决策。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        from ocos.storage.migrations import ensure_schema
        ensure_schema(db_path)

    # ── 写入 ─────────────────────────────────────────────────────────

    def record_thinking(
        self,
        self_version: int,
        consumed_delta_ids=(),
        consumed_evidence_ids=(),
        thinking_trace_id: str = "",
    ) -> ThinkingTrace:
        trace = ThinkingTrace(
            thinking_trace_id=thinking_trace_id or _new_id("TNG"),
            self_version=self_version,
            consumed_delta_ids=tuple(consumed_delta_ids),
            consumed_evidence_ids=tuple(consumed_evidence_ids),
        )
        with transaction(self._db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE_DECISION_TRACE} "
                f"(thinking_trace_id, self_version, consumed_delta_ids_json, "
                f" consumed_evidence_ids_json, created_at) VALUES (?,?,?,?,?)",
                (
                    trace.thinking_trace_id, trace.self_version,
                    _json(list(trace.consumed_delta_ids)),
                    _json(list(trace.consumed_evidence_ids)),
                    trace.created_at.isoformat(),
                ),
            )
        return trace

    def record_decision(
        self,
        thinking_trace_id: str,
        decision: str = "",
        action_ids=(),
        strategy: str = "",
        action: str = "",
        y_ref: Optional[str] = None,
        decision_id: str = "",
    ) -> DecisionRecord:
        rec = DecisionRecord(
            decision_id=decision_id or _new_id("DEC"),
            thinking_trace_id=thinking_trace_id,
            decision=decision,
            strategy=strategy,
            action=action,
            action_ids=tuple(action_ids),
            y_ref=y_ref,
        )
        with transaction(self._db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE_DECISION_TRACE_DECISION} "
                f"(decision_id, thinking_trace_id, decision, strategy, action, "
                f" action_ids_json, y_ref, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    rec.decision_id, rec.thinking_trace_id, rec.decision,
                    rec.strategy, rec.action,
                    _json(list(rec.action_ids)),
                    rec.y_ref,
                    rec.created_at.isoformat(),
                ),
            )
        return rec

    def record_decision_contemporaneous(
        self,
        self_version: int,
        consumed_delta_ids=(),
        consumed_evidence_ids=(),
        decision: str = "",
        strategy: str = "",
        action: str = "",
        action_ids=(),
        y_ref: Optional[str] = None,
        thinking_trace_id: str = "",
        decision_id: str = "",
    ) -> tuple[ThinkingTrace, DecisionRecord]:
        """P0-4A：同一事务原子持久化 ThinkingTrace + DecisionRecord。

        本方法遵守冻结红线 —— `DecisionTraceStore` 是**记录器，不是 Decision Runtime**：
          - 不重读 S2、不重算决策、不决定 Action。
          - `consumed_delta_ids / consumed_evidence_ids / self_version` 由调用方
            在【实际读取 S2 组件的那一刻】形成并传入（decision-relevant consumption）。
          - 一个事务同时写入 ThinkingTrace 与 DecisionRecord，保证同一 identity、
            同一时刻、先于 Action 效果持久化。
        """
        trace = ThinkingTrace(
            thinking_trace_id=thinking_trace_id or _new_id("TNG"),
            self_version=self_version,
            consumed_delta_ids=tuple(consumed_delta_ids),
            consumed_evidence_ids=tuple(consumed_evidence_ids),
        )
        rec = DecisionRecord(
            decision_id=decision_id or _new_id("DEC"),
            thinking_trace_id=trace.thinking_trace_id,
            decision=decision,
            strategy=strategy,
            action=action,
            action_ids=tuple(action_ids),
            y_ref=y_ref,
        )
        with transaction(self._db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE_DECISION_TRACE} "
                f"(thinking_trace_id, self_version, consumed_delta_ids_json, "
                f" consumed_evidence_ids_json, created_at) VALUES (?,?,?,?,?)",
                (
                    trace.thinking_trace_id, trace.self_version,
                    _json(list(trace.consumed_delta_ids)),
                    _json(list(trace.consumed_evidence_ids)),
                    trace.created_at.isoformat(),
                ),
            )
            conn.execute(
                f"INSERT INTO {TABLE_DECISION_TRACE_DECISION} "
                f"(decision_id, thinking_trace_id, decision, strategy, action, "
                f" action_ids_json, y_ref, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    rec.decision_id, rec.thinking_trace_id, rec.decision,
                    rec.strategy, rec.action,
                    _json(list(rec.action_ids)),
                    rec.y_ref,
                    rec.created_at.isoformat(),
                ),
            )
        return trace, rec

    # ── 读取 ─────────────────────────────────────────────────────────

    def thinking(self, thinking_trace_id: str) -> Optional[ThinkingTrace]:
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT * FROM {TABLE_DECISION_TRACE} WHERE thinking_trace_id = ?",
            (thinking_trace_id,),
        ).fetchone()
        if row is None:
            return None
        return ThinkingTrace(
            thinking_trace_id=row["thinking_trace_id"],
            self_version=int(row["self_version"]),
            consumed_delta_ids=tuple(_loads(row["consumed_delta_ids_json"])),
            consumed_evidence_ids=tuple(_loads(row["consumed_evidence_ids_json"])),
            created_at=_dt(row["created_at"]),
        )

    def decision(self, decision_id: str) -> Optional[DecisionRecord]:
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT * FROM {TABLE_DECISION_TRACE_DECISION} WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        return _row_to_decision(row) if row else None

    def decisions_for_trace(self, thinking_trace_id: str) -> list[DecisionRecord]:
        conn = get_connection(self._db_path)
        rows = conn.execute(
            f"SELECT * FROM {TABLE_DECISION_TRACE_DECISION} "
            f"WHERE thinking_trace_id = ? ORDER BY created_at",
            (thinking_trace_id,),
        ).fetchall()
        return [_row_to_decision(r) for r in rows]

    def all_thinking(self) -> list[ThinkingTrace]:
        conn = get_connection(self._db_path)
        rows = conn.execute(f"SELECT * FROM {TABLE_DECISION_TRACE} ORDER BY created_at").fetchall()
        return [ThinkingTrace(
            thinking_trace_id=r["thinking_trace_id"],
            self_version=int(r["self_version"]),
            consumed_delta_ids=tuple(_loads(r["consumed_delta_ids_json"])),
            consumed_evidence_ids=tuple(_loads(r["consumed_evidence_ids_json"])),
            created_at=_dt(r["created_at"]),
        ) for r in rows]


def _row_to_decision(row) -> DecisionRecord:
    return DecisionRecord(
        decision_id=row["decision_id"],
        thinking_trace_id=row["thinking_trace_id"],
        decision=row["decision"] or "",
        strategy=row["strategy"] or "",
        action=row["action"] or "",
        action_ids=tuple(_loads(row["action_ids_json"])),
        y_ref=row["y_ref"],
        created_at=_dt(row["created_at"]),
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _json(obj) -> str:
    import json as _jsonlib
    return _jsonlib.dumps(obj, ensure_ascii=False)


def _loads(s) -> list:
    import json as _jsonlib
    try:
        return _jsonlib.loads(s or "[]")
    except Exception:
        return []


def _dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# 生产接线便利函数（converse.py respond() in-place hook 使用）
# ═══════════════════════════════════════════════════════════════════════════════


def record_thinking_trace(db_path: str) -> Optional[ThinkingTrace]:
    """在决策装入 S2 投影处记录 ThinkingTrace（consumed D 清单）。

    仅当存在 committed S2 projection 时记录；否则返回 None（trace 缺省）。
    只读 S2（get_self_projection + committed_claims），不改写任何 S2 内容。
    """
    try:
        from ocos.self.self_state import get_self_projection
        s2 = get_self_projection(db_path)
        if s2 is None:
            return None
        claims = s2.committed_claims()
        delta_ids = [c["claim_id"] for c in claims]
        evidence_ids: list[str] = []
        for c in claims:
            evidence_ids.extend(c.get("evidence_ids") or [])
        return DecisionTraceStore(db_path).record_thinking(
            self_version=s2.version,
            consumed_delta_ids=tuple(delta_ids),
            consumed_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        )
    except Exception:
        logger.debug("thinking trace unavailable", exc_info=True)
        return None


def record_decision_trace(
    db_path: str,
    thinking_trace_id: str,
    decision: str = "",
    action_ids=(),
    strategy: str = "",
    action: str = "",
    y_ref: Optional[str] = None,
) -> Optional[DecisionRecord]:
    """把一次决策结果以同 thinking_trace_id 落 DecisionRecord（→ action_ids → Y）。"""
    if not thinking_trace_id:
        return None
    try:
        return DecisionTraceStore(db_path).record_decision(
            thinking_trace_id=thinking_trace_id,
            decision=decision,
            action_ids=tuple(action_ids),
            strategy=strategy,
            action=action,
            y_ref=y_ref,
        )
    except Exception:
        logger.debug("decision trace unavailable", exc_info=True)
        return None


__all__ = [
    "ThinkingTrace",
    "DecisionRecord",
    "DecisionTraceStore",
    "record_thinking_trace",
    "record_decision_trace",
]