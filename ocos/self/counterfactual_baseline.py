"""P0-4 A — Counterfactual Baseline Freeze（Z）— 一等、独立、只写一次的证据对象。

目的（解锁 P0-4 F6/F7）：在 Attempt 2 之前生成并**冻结**一个反事实基线 Z，
描述"若无 D，同一 Goal/初始态下最有证据支持的决策/策略/动作/预测结果"。
归因必须对照**已冻结**的 Z，杜绝 post-hoc：

    A2 成功 → 回头构造"若无 D 会怎样"的 Z → 宣布 Y≠Z   （❌ 禁止）

强不变式：
    Freeze(Z) ─→ Attempt 2 ─→ Z 不得改变
  - frozen_at 为空 ⇒ 草稿：**不可**用于归因；同 (goal, state_key) 的新草稿可替换。
  - frozen_at 非空 ⇒ 已冻结：`baseline_hash` 锁定；任何改写（save_draft/freeze
    指向同一 baseline_id 或同 key）一律 reject。
  - 每个 (goal, state_key) 至多一份**已冻结** Z（实体层 + 部分唯一索引双重强制）。

本模块不写 S2、不碰 SelfEvidencePipeline、不碰任何决策运行时（P0-4 Preconditions A 边界）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import typing
import uuid
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.schema import TABLE_COUNTERFACTUAL_BASELINE

logger = logging.getLogger(__name__)


class CounterfactualBaselineError(Exception):
    """Z 基线基类异常。"""


class BaselineNotFrozenError(CounterfactualBaselineError):
    """试图用未冻结的草稿做归因基准。"""


class BaselineImmutableError(CounterfactualBaselineError):
    """已冻结的基线的任何改写/重冻结意图（防 post-hoc）。"""


class BaselineKeyConflictError(CounterfactualBaselineError):
    """同 (goal, state_key) 已有一份已冻结 Z，拒绝重复冻结。"""


class BaselineNotFoundError(CounterfactualBaselineError):
    """指定的 baseline_id 不存在。"""


@dataclass
class CounterfactualBaseline:
    """Z：反事实基线（一等证据对象）。

    判定用于归因 ⟺ `frozen_at` 非空 且 `baseline_hash` 非空。
    """

    baseline_id: str
    goal: str
    initial_state: Any                      # 初始环境/状态快照（可哈希 canonical 化）
    decision: str = ""                      # 若无 D，最有证据的决策
    strategy: str = ""                      # 策略
    action: str = ""                        # 动作
    predicted_result: Any = None            # 预测结果
    source: str = ""                        # 基线来源（experiment harness / projection）
    evidence: tuple[str, ...] = ()          # 支撑 evidence_ids
    confidence: float = 0.0                 # 基线置信度 [0,1]
    frozen_at: Optional[datetime] = None    # 冻结时刻；None = 草稿，不可归因
    frozen_by: str = ""                     # 冻结属主
    baseline_hash: str = ""                 # 冻结时锁定（不含 freeze 元数据）

    # ── 判定 ─────────────────────────────────────────────────────────

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None and bool(self.baseline_hash)

    @property
    def state_key(self) -> str:
        """初始态规范化指纹（用于 (goal, state_key) 唯一性 / 检索）。"""
        return _fingerprint(self.initial_state)

    def require_frozen(self) -> None:
        """断言可用作归因基准（未冻结则抛错）。"""
        if not self.is_frozen:
            raise BaselineNotFrozenError(
                f"baseline {self.baseline_id} is draft (frozen_at={self.frozen_at}); "
                "draft Z cannot be used for attribution"
            )

    # ── 冻结内容规范 ────────────────────────────────────────────────

    def content_payload(self) -> dict:
        """冻结内容：不含 freeze 元数据/身份，hash 依赖于此。"""
        return {
            "goal": self.goal,
            "initial_state": self.initial_state,
            "decision": self.decision,
            "strategy": self.strategy,
            "action": self.action,
            "predicted_result": self.predicted_result,
            "source": self.source,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
        }


def _canonical(obj):
    """任意的 dataclass/Enum/datetime/dict/list → 固定顺序 primitive 树。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        out: dict = {"__type": type(obj).__name__}
        for f in fields(obj):
            if f.name == "update_history":  # 保守：绝不把可变史带入指纹
                continue
            out[f.name] = _canonical(getattr(obj, f.name))
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(_canonical(k)): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)  # 其余退化为确定性字符串


def _fingerprint(obj) -> str:
    payload = json.dumps(_canonical(obj), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _content_hash(baseline: "CounterfactualBaseline") -> str:
    payload = json.dumps(_canonical(baseline.content_payload()),
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_to_baseline(row) -> CounterfactualBaseline:
    ind = json.loads(row["initial_state_json"] or "null")
    pr = json.loads(row["predicted_result_json"] or "null")
    ev = json.loads(row["evidence_json"] or "[]")
    frozen_at = None
    if row["frozen_at"]:
        frozen_at = datetime.fromisoformat(str(row["frozen_at"]))
    return CounterfactualBaseline(
        baseline_id=row["baseline_id"],
        goal=row["goal"],
        initial_state=ind,
        decision=row["decision"] or "",
        strategy=row["strategy"] or "",
        action=row["action"] or "",
        predicted_result=pr,
        source=row["source"] or "",
        evidence=tuple(ev),
        confidence=float(row["confidence"] or 0.0),
        frozen_at=frozen_at,
        frozen_by=row["frozen_by"] or "",
        baseline_hash=row["baseline_hash"] or "",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CounterfactualBaselineStore
# ═══════════════════════════════════════════════════════════════════════════════


class CounterfactualBaselineStore:
    """Z 基线的 append-only 持久化载件。

    生命周期：
      save_draft → 草稿（frozen_at NULL）       可被同 key 新草稿替换
      freeze     → 已冻结（frozen_at+hash 锁定） 任何改写 reject
      baseline_for → 只返回**已冻结**的 Z（否则 None → 该 Goal 归因 BLOCKED）
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        from ocos.storage.migrations import ensure_schema
        ensure_schema(db_path)

    # ── 草稿 ─────────────────────────────────────────────────────────

    def save_draft(self, baseline: CounterfactualBaseline) -> None:
        """写/替换一份草稿。已冻结的 baseline 或同 key 已冻结 → reject。"""
        if baseline.is_frozen:
            raise BaselineImmutableError(
                f"{baseline.baseline_id} is already frozen; cannot draft it again")
        key = baseline.state_key
        with transaction(self._db_path) as conn:
            # 同 (goal,state_key) 已冻结 → 不可被草稿覆盖
            existing = conn.execute(
                f"SELECT baseline_id, frozen_at FROM {TABLE_COUNTERFACTUAL_BASELINE} "
                f"WHERE goal = ? AND state_key = ?",
                (baseline.goal, key),
            ).fetchall()
            for r in existing:
                if r["frozen_at"]:
                    raise BaselineImmutableError(
                        f"(goal,init_state) already has frozen baseline {r['baseline_id']}"
                    )
            conn.execute(
                f"INSERT OR REPLACE INTO {TABLE_COUNTERFACTUAL_BASELINE} "
                f"(baseline_id, goal, state_key, initial_state_json, decision, "
                f" strategy, action, predicted_result_json, source, evidence_json, "
                f" confidence, frozen_at, frozen_by, baseline_hash, created_at) "
                f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    baseline.baseline_id, baseline.goal, key,
                    json.dumps(_canonical(baseline.initial_state), ensure_ascii=False),
                    baseline.decision, baseline.strategy, baseline.action,
                    json.dumps(_canonical(baseline.predicted_result), ensure_ascii=False),
                    baseline.source,
                    json.dumps(list(baseline.evidence), ensure_ascii=False),
                    baseline.confidence,
                    None, None, None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # ── 冻结（唯一可转入归因态的入口）───────────────────────────────────

    def freeze(self, baseline_id: str, frozen_by: str = "experiment") -> CounterfactualBaseline:
        """冻结一份草稿为归因基准 Z。任何重复/覆盖意图 reject。"""
        with transaction(self._db_path) as conn:
            row = conn.execute(
                f"SELECT * FROM {TABLE_COUNTERFACTUAL_BASELINE} WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchone()
            if row is None:
                raise BaselineNotFoundError(f"no baseline {baseline_id}")
            if row["frozen_at"]:
                raise BaselineImmutableError(
                    f"baseline {baseline_id} already frozen; cannot re-freeze")
            bl = _row_to_baseline(row)
            # 同 (goal,state_key) 已冻结，禁止第二份
            dup = conn.execute(
                f"SELECT baseline_id FROM {TABLE_COUNTERFACTUAL_BASELINE} "
                f"WHERE goal = ? AND state_key = ? AND frozen_at IS NOT NULL",
                (bl.goal, bl.state_key),
            ).fetchone()
            if dup is not None:
                raise BaselineKeyConflictError(
                    f"(goal,init_state) already frozen as {dup['baseline_id']}")
            now = datetime.now(timezone.utc)
            bl.frozen_at = now
            bl.frozen_by = frozen_by
            bl.baseline_hash = _content_hash(bl)  # 锁定内容，不含 freeze 元数据
            conn.execute(
                f"UPDATE {TABLE_COUNTERFACTUAL_BASELINE} "
                f"SET frozen_at = ?, frozen_by = ?, baseline_hash = ? "
                f"WHERE baseline_id = ?",
                (now.isoformat(), frozen_by, bl.baseline_hash, baseline_id),
            )
        return self.get(baseline_id)  # type: ignore[return-value]

    # ── 读取 ──────────────────────────────────────────────────────────

    def get(self, baseline_id: str) -> Optional[CounterfactualBaseline]:
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT * FROM {TABLE_COUNTERFACTUAL_BASELINE} WHERE baseline_id = ?",
            (baseline_id,),
        ).fetchone()
        return _row_to_baseline(row) if row else None

    def baseline_for(self, goal: str, initial_state: Any) -> Optional[CounterfactualBaseline]:
        """返回 (goal, init_state) 匹配的**已冻结** Z；无 → None（归因 BLOCKED）。"""
        key = _fingerprint(initial_state)
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT * FROM {TABLE_COUNTERFACTUAL_BASELINE} "
            f"WHERE goal = ? AND state_key = ? AND frozen_at IS NOT NULL",
            (goal, key),
        ).fetchone()
        if row is None:
            return None
        bl = _row_to_baseline(row)
        bl.require_frozen()
        return bl

    def all(self) -> list[CounterfactualBaseline]:
        conn = get_connection(self._db_path)
        rows = conn.execute(
            f"SELECT * FROM {TABLE_COUNTERFACTUAL_BASELINE} ORDER BY created_at"
        ).fetchall()
        return [_row_to_baseline(r) for r in rows]


__all__ = [
    "CounterfactualBaselineError",
    "BaselineNotFrozenError",
    "BaselineImmutableError",
    "BaselineKeyConflictError",
    "BaselineNotFoundError",
    "CounterfactualBaseline",
    "CounterfactualBaselineStore",
]