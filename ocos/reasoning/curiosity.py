"""OCOS 好奇心驱动：PredictionGapTracker + EpistemicDrive。

Phase 1 of OCOS Brain Evolution — 让好奇心自驱动（不是硬编码模板）。

核心洞见（Nemori Predict-Calibrate Principle + Genesis Free-Energy Principle）:
  每一次 goal_result 发生时 → SymbolicReasoner.predict(task, agent) → expected
  实际 outcome → actual
  误差 gap = |expected - actual|
  gap 大 → 我的世界模型在这个领域不准 → 主动探查来补知识

零 LLM 调用，纯 Belief/Pattern/Episode 数据驱动。
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── 数据类 ──────────────────────────────────────────────────────────────────

@dataclass
class GapRecord:
    """单次预测误差记录。"""
    id: str                       # gap-{timestamp}-{random}
    task_hash: str                # task 描述哈希（用于聚合）
    task_text: str                # 原始任务描述（截断 200 字）
    agent_type: str               # agent 类型
    predicted_success: float     # SymbolicReasoner 预测值
    actual_success: bool          # 实际结果
    gap: float                    # |predicted - actual| = 误差
    confidence: float             # 预测时的置信度（低 confidence 的 gap 无意义）
    over_predicted: bool          # 预测比实际乐观 → True; 悲观 → False
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


@dataclass
class DomainUncertainty:
    """某个领域的不确定性评分（EpistemicDrive 的输出）。"""
    domain_key: str               # 聚合键：task 关键词 + agent_type
    domain_text: str              # 人类可读的领域描述
    mean_gap: float               # 平均预测误差
    sample_count: int             # 样本数
    domain_confidence: float      # 这个领域的总置信度（BeliefStore 贡献）
    uncertainty_score: float      # 综合不确定性：mean_gap × log(sample_count+1) × (1 - domain_confidence)
    suggested_goal: str           # MotivationHub 可以直接用的 goal 文本

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_key": self.domain_key,
            "domain_text": self.domain_text,
            "mean_gap": round(self.mean_gap, 3),
            "sample_count": self.sample_count,
            "domain_confidence": round(self.domain_confidence, 3),
            "uncertainty_score": round(self.uncertainty_score, 3),
            "suggested_goal": self.suggested_goal,
        }


# ── PredictionGapTracker ────────────────────────────────────────────────────

class PredictionGapTracker:
    """记录每次 goal_result 的预测误差。

    不是 db table——直接在 memory 里聚合，避免 DB 写压力。
    每次 goal_result 发生时 goal_result_store.record(...) 调用。
    EpistemicDrive.suggest() 从内存聚合出"最不确定的领域"。
    """

    # 最低 confidence 阈值：低于此值的 gap 丢弃（纯粹的无知 ≠ 有用的好奇心）
    MIN_CONFIDENCE_FOR_GAP = 0.12

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        # task_hash → list[GapRecord]（内存缓存）
        self._gaps: dict[str, list[GapRecord]] = defaultdict(list)
        self._max_per_domain = 50
        # 确保 DB 有表
        self._ensure_table()

    def _ensure_table(self) -> None:
        """创建 prediction_gap 表（如果不存在）。"""
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS prediction_gap (
                    id TEXT PRIMARY KEY,
                    task_hash TEXT NOT NULL,
                    task_text TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    predicted_success REAL NOT NULL,
                    actual_success INTEGER NOT NULL,
                    gap REAL NOT NULL,
                    confidence REAL NOT NULL,
                    over_predicted INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                )"""
            )
            # 保留最近 3000 条（防膨胀）
            conn.execute(
                "DELETE FROM prediction_gap WHERE id IN ("
                "SELECT id FROM prediction_gap ORDER BY timestamp DESC LIMIT -1 OFFSET 3000)"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("prediction_gap table init skipped: %s", e)

    def record(
        self,
        task_text: str,
        agent_type: str,
        predicted_success: float,
        actual_success: bool,
        confidence: float,
    ) -> GapRecord | None:
        """记录一次预测误差。confidence 太低则丢弃。"""
        if confidence < self.MIN_CONFIDENCE_FOR_GAP:
            return None

        gap = abs(predicted_success - (1.0 if actual_success else 0.0))
        over = predicted_success > (1.0 if actual_success else 0.0)
        task_hash = self._hash_task(task_text, agent_type)

        rec = GapRecord(
            id=f"gap-{int(time.time())}{task_hash[:6]}",
            task_hash=task_hash,
            task_text=task_text[:200],
            agent_type=agent_type,
            predicted_success=predicted_success,
            actual_success=actual_success,
            gap=gap,
            confidence=confidence,
            over_predicted=over,
        )

        self._gaps[task_hash].append(rec)
        if len(self._gaps[task_hash]) > self._max_per_domain:
            self._gaps[task_hash] = self._gaps[task_hash][-self._max_per_domain:]

        # 同时落 DB（关键修复：让 MotivationHub 能读到这些 gap）
        self._persist_to_db(rec)

        logger.info(
            "PHASE-LIFE: gap recorded task='%s' agent=%s predicted=%.2f actual=%s "
            "gap=%.2f confidence=%.2f over=%s",
            task_text[:50], agent_type, predicted_success, actual_success,
            gap, confidence, over,
        )
        return rec

    def _persist_to_db(self, rec: GapRecord) -> None:
        """把 GapRecord 写入 prediction_gap 表。"""
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR IGNORE INTO prediction_gap "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rec.id, rec.task_hash, rec.task_text, rec.agent_type,
                 rec.predicted_success, 1 if rec.actual_success else 0,
                 rec.gap, rec.confidence, 1 if rec.over_predicted else 0,
                 rec.timestamp),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("prediction_gap persist failed: %s", e)

    @staticmethod
    def _hash_task(task_text: str, agent_type: str) -> str:
        """任务描述的轻量哈希（用关键词而非全文）。"""
        import hashlib
        # 提取前 30 字 + agent_type → 哈希
        key = (task_text or "")[:30] + "|" + (agent_type or "")
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    def domains(self) -> dict[str, list[GapRecord]]:
        """返回所有 gap 聚合域。"""
        return dict(self._gaps)

    def clear(self) -> None:
        self._gaps.clear()

    def stats(self) -> dict[str, Any]:
        total = sum(len(v) for v in self._gaps.values())
        return {
            "domains": len(self._gaps),
            "total_gaps": total,
            "mean_gap_all": (
                sum(r.gap for v in self._gaps.values() for r in v) / total
                if total else 0.0
            ),
        }


# ── EpistemicDrive ───────────────────────────────────────────────────────────

class EpistemicDrive:
    """从 PredictionGapTracker 聚合出"最不确定的领域"。

    核心思想：
      uncertainty_score = mean_gap × log(sample_count + 1) × (1 - domain_confidence)
      - mean_gap 大 → 预测不准
      - sample_count 多 → 这个领域我真的在碰壁（不是偶然）
      - domain_confidence 低 → BeliefStore 对这个领域没信心

    输出 MotivationHub 可以直接用的 goal 候选。
    """

    def __init__(
        self,
        tracker: PredictionGapTracker,
        db_path: str | None = None,
        top_n: int = 3,
    ):
        self._tracker = tracker
        self._db_path = db_path
        self._top_n = top_n

    def suggest(self) -> list[DomainUncertainty]:
        """返回 top-N 最不确定的领域。

        PHASE-LIFE: 先从 DB prediction_gap 读持久化数据，
        再叠加 tracker 内存数据（Step 10 记录的）。
        """
        # Step 1: 从 DB 读持久化 gap（关键修复——让 MotivationHub 能读到
        # Step 10 记录的误差，不再依赖内存 tracker 实例）
        db_records = self._load_from_db()

        # Step 2: 合并内存 tracker 数据
        all_domains: dict[str, list[GapRecord]] = {}
        for domain_key, records in self._tracker.domains().items():
            all_domains.setdefault(domain_key, []).extend(records)
        for domain_key, records in db_records.items():
            all_domains.setdefault(domain_key, []).extend(records)

        domains: list[DomainUncertainty] = []
        for domain_key, records in all_domains.items():
            if len(records) < 2:
                continue

            mean_gap = sum(r.gap for r in records) / len(records)
            # domain_confidence：查 BeliefStore 这个领域的平均 confidence
            domain_conf = self._query_domain_confidence(records)

            import math
            uncertainty = mean_gap * math.log(len(records) + 1) * (1.0 - domain_conf)

            # 从 records 聚合出 task_text
            task_text = max(records, key=lambda r: r.timestamp).task_text
            agent = records[-1].agent_type
            # v2: 看 actual 结果而不是 predicted
            actual_success_rate = sum(1 for r in records if r.actual_success) / len(records)
            direction = "成功" if actual_success_rate >= 0.5 else "失败"

            suggested = self._format_goal(task_text, agent, mean_gap, direction)

            domains.append(DomainUncertainty(
                domain_key=domain_key,
                domain_text=task_text[:80],
                mean_gap=mean_gap,
                sample_count=len(records),
                domain_confidence=domain_conf,
                uncertainty_score=uncertainty,
                suggested_goal=suggested,
            ))

        domains.sort(key=lambda d: d.uncertainty_score, reverse=True)
        return domains[:self._top_n]

    def _load_from_db(self) -> dict[str, list[GapRecord]]:
        """从 prediction_gap 表读最近 500 条 gap → 按 task_hash 聚合。"""
        if not self._db_path:
            return {}
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM prediction_gap "
                "ORDER BY timestamp DESC LIMIT 500"
            ).fetchall()
            conn.close()
        except sqlite3.Error:
            return {}

        out: dict[str, list[GapRecord]] = {}
        for r in rows:
            rec = GapRecord(
                id=r["id"], task_hash=r["task_hash"],
                task_text=r["task_text"], agent_type=r["agent_type"],
                predicted_success=r["predicted_success"],
                actual_success=bool(r["actual_success"]),
                gap=r["gap"], confidence=r["confidence"],
                over_predicted=bool(r["over_predicted"]),
                timestamp=r["timestamp"],
            )
            out.setdefault(rec.task_hash, []).append(rec)
        return out

    def _query_domain_confidence(self, records: list[GapRecord]) -> float:
        """查 BeliefStore 对这些 records 所属领域的平均 confidence。"""
        if not self._db_path:
            return 0.5  # 无 DB → 先验
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            # 简化：拿所有 belief 的平均 confidence
            row = conn.execute(
                "SELECT AVG(confidence) as avg FROM belief"
            ).fetchone()
            conn.close()
            return float(row["avg"]) if row and row["avg"] else 0.5
        except Exception:
            return 0.5

    @staticmethod
    def _format_goal(
        task_text: str, agent_type: str, mean_gap: float, direction: str
    ) -> str:
        """DomainUncertainty → MotivationHub 可用的 goal 文本。"""
        return (
            f"【知识补全】探查 {agent_type} 在 {task_text[:40]} "
            f"方向的表现不确定性（预测误差 {mean_gap:.0%}，实际{direction}）"
        )
