"""COG-V2 Phase 3.1 — 事件驱动慢思考（System2，预算制）。

替代已归档的 60s 持续认知循环：不再定时空转烧 LLM，只在**真实目标失败**
这一高信息量事件发生时才做一次慢思考，且受三重预算闸约束：

    1. 开关闸   OCOS_EVENT_REFLECTION != "0"（默认开，异常可即时回退）
    2. 日配额   每天 ≤ OCOS_EVENT_REFLECTION_CAP 次（默认 8）
    3. 间隔闸   距上次反思 > OCOS_EVENT_REFLECTION_INTERVAL_S 秒（默认 300）

反思产物：以真实 cause+cmd+stderr 通过 LLMTutor 求方法论 → 过 UnifiedIngestor
质量门（拒答门/套娃门）→ knowledge 表（knowledge_type=lesson，标签
lesson_note），当天同主题目标即可经 RecallRouter 工作空间读到。

诚实性：
    - 全部预算状态落 episodes（source='event_reflection'），跨重启生效；
    - LLM 不可用 / 质量门拦截 / 无失败证据 → 不写知识，只如实返回原因；
    - 本模块不直接拼 SQL 写 knowledge，一律走 ingestor（门控唯一出口）。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

ENABLE_ENV = "OCOS_EVENT_REFLECTION"
CAP_ENV = "OCOS_EVENT_REFLECTION_CAP"
INTERVAL_ENV = "OCOS_EVENT_REFLECTION_INTERVAL_S"

DEFAULT_DAILY_CAP = 8
DEFAULT_MIN_INTERVAL_S = 300
# 只采纳距失败时刻这么近的 failure_lesson（过远的教训与本次目标无关）
RECENT_LESSON_WINDOW_MIN = 60

# 与 unified_ingestor / recall_router 同源的防御（双保险：ingestor 门之外，
# 反思侧先拦一次，避免把明显拒答送进摄入统计）
_REFUSAL_MARK = (
    "无法确认", "无法提供", "作为一个ai", "as an ai",
    "i don't have", "我没有访问",
)


class EventReflector:
    """目标失败 → 一次预算制 LLM 慢思考 → lesson_note 知识。"""

    def __init__(self, db_path: str, tutor: Any = None,
                 ingestor: Any = None) -> None:
        self._db_path = db_path
        self._tutor = tutor
        self._ingestor = ingestor

    # ── 主入口 ─────────────────────────────────────────────────────────

    def reflect_failure(
        self,
        goal: str,
        outcome: Optional[dict] = None,
        *,
        now: Optional[datetime] = None,
    ) -> dict:
        """一次失败事件的反思入口。

        返回 {ran: bool, reason?, cause?, stored?, knowledge?}；
        任何闸门未过 / 依赖缺失都返回 ran=False + 原因，绝不抛异常给主链。
        """
        outcome = outcome or {}
        now = now or datetime.now(timezone.utc)
        try:
            if os.environ.get(ENABLE_ENV, "1") == "0":
                return {"ran": False, "reason": "disabled"}
            if outcome.get("success") is True:
                return {"ran": False, "reason": "not_a_failure"}
            gate = self._budget_gate(now)
            if gate is not None:
                return {"ran": False, "reason": gate}

            lesson = self._recent_failure_lesson(now)
            cause = (lesson or {}).get("cause") or "unknown"
            question = self._build_question(goal, lesson or {})
            answer = self._ask_tutor(question, lesson or {})
            if not answer:
                return {"ran": False, "reason": "tutor_unavailable",
                        "cause": cause}
            if self._looks_like_refusal(answer):
                self._record_episode(cause, goal, stored=False,
                                     detail="answer_refusal", now=now)
                return {"ran": True, "stored": False,
                        "reason": "answer_refusal", "cause": cause}

            stored = self._ingest_lesson(goal, cause, answer, lesson or {})
            self._record_episode(cause, goal, stored=stored,
                                 detail="stored" if stored else "filtered",
                                 now=now)
            return {"ran": True, "stored": stored, "cause": cause,
                    "reason": "stored" if stored else "filtered"}
        except Exception as e:  # noqa: BLE001 — 反思永不阻断结果闭环主链
            logger.debug("event reflection skipped: %s", e, exc_info=True)
            return {"ran": False, "reason": f"error:{type(e).__name__}"}

    # ── 预算闸（持久化，跨重启）─────────────────────────────────────────

    def _budget_gate(self, now: datetime) -> Optional[str]:
        """None=放行；否则返回拦截原因（cap/interval）。"""
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            try:
                day = now.strftime("%Y-%m-%d")
                n_today = conn.execute(
                    "SELECT COUNT(*) FROM episodes "
                    "WHERE source='event_reflection' AND created_at >= ?",
                    (day,)).fetchone()[0]
                cap = max(1, int(os.environ.get(CAP_ENV, DEFAULT_DAILY_CAP)))
                if n_today >= cap:
                    return "daily_cap"
                last = conn.execute(
                    "SELECT MAX(created_at) FROM episodes "
                    "WHERE source='event_reflection'").fetchone()[0]
            finally:
                conn.close()
        except (sqlite3.Error, ValueError):
            return None  # 预算状态不可查 → 不抑制反思（宁可多一次，不吞信号）
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                gap = (now - (last_dt if last_dt.tzinfo
                              else last_dt.replace(tzinfo=timezone.utc))).total_seconds()
                min_gap = float(os.environ.get(INTERVAL_ENV,
                                               DEFAULT_MIN_INTERVAL_S))
                if gap < min_gap:
                    return "interval"
            except ValueError:
                pass
        return None

    # ── 证据：最近的 failure_lesson ────────────────────────────────────

    def _recent_failure_lesson(self, now: datetime) -> dict:
        """取近 60min 内最新一条 failure_lesson 的结构化证据（无则 {}）。"""
        since = (now - timedelta(minutes=RECENT_LESSON_WINDOW_MIN)).isoformat()
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT goal, tags, context FROM episodes "
                    "WHERE action='failure_lesson' AND created_at >= ? "
                    "ORDER BY rowid DESC LIMIT 1", (since,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return {}
        if row is None:
            return {}
        try:
            ctx = json.loads(row["context"] or "{}")
        except ValueError:
            ctx = {}
        try:
            tags = json.loads(row["tags"] or "[]")
        except ValueError:
            tags = []
        cause = next((t for t in tags
                      if t and t != "failure_lesson"),
                     ctx.get("cause") or "unknown")
        fl = ctx.get("failure_lesson") or {}
        evidence = fl.get("evidence") or {}
        return {
            "cause": str(cause),
            "goal": (row["goal"] or ctx.get("goal_pattern") or "")[:200],
            "cmd": str(evidence.get("command")
                       or ctx.get("blocked_action") or "")[:200],
            "stderr": str(evidence.get("stderr")
                          or ctx.get("failure_evidence") or "")[:300],
            "recommended": str(ctx.get("recommended_response") or "")[:200],
        }

    # ── LLM 慢思考 ─────────────────────────────────────────────────────

    @staticmethod
    def _build_question(goal: str, lesson: dict) -> str:
        """确定性提问模板：只喂真实 cause/cmd/stderr，不诱导编造。"""
        cause = lesson.get("cause", "unknown")
        cmd = lesson.get("cmd", "")
        stderr = lesson.get("stderr", "")
        parts = [
            f"任务「{(goal or lesson.get('goal', ''))[:100]}」执行失败，",
            f"确定性诊断的失败原因为 {cause}。",
        ]
        if cmd:
            parts.append(f"触发失败的命令/动作：{cmd}。")
        if stderr:
            parts.append(f"错误证据（摘录）：{stderr[:200]}。")
        parts.append(
            "请用中文给出：1) 一句话失败机理；2) 下次同类任务可直接执行的"
            "替代方案（优先只读白名单命令，不要建议安装缺失依赖）；"
            "3) 两条可复用的事前检查项。直接给结论，不要复述问题或客套。")
        return "".join(parts)

    def _ask_tutor(self, question: str, lesson: dict) -> str:
        if self._tutor is None:
            return ""
        try:
            ctx = ""
            if lesson.get("recommended"):
                ctx = f"既有确定性建议：{lesson['recommended']}"
            res = self._tutor.ask(question, context_knowledge=ctx)
        except Exception as e:  # noqa: BLE001
            logger.info("event reflection tutor call failed: %s", e)
            return ""
        if not getattr(res, "success", False):
            return ""
        return (getattr(res, "answer", "") or "").strip()

    @staticmethod
    def _looks_like_refusal(text: str) -> bool:
        low = text.lower()
        return any(m in low for m in _REFUSAL_MARK)

    # ── 产物过质量门入库 ───────────────────────────────────────────────

    def _ingest_lesson(self, goal: str, cause: str, answer: str,
                       lesson: dict) -> bool:
        if self._ingestor is None:
            return False
        try:
            from ocos.learning.unified_ingestor import (
                IngestArtifact, SourceChannel,
            )
            title = f"失败反思/{cause}：{(goal or lesson.get('goal', ''))[:40]}"
            art = IngestArtifact(
                channel=SourceChannel.LLM_QA,
                content=answer[:1200],
                title=title,
                confidence=0.65,
                tags=["event_reflection", "lesson_note", str(cause)],
                knowledge_type="lesson",
                metadata={
                    "reflection": "event_failure",
                    "cause": str(cause),
                    "goal_excerpt": (goal or "")[:120],
                    "command": lesson.get("cmd", ""),
                },
            )
            results = self._ingestor.ingest(
                [art], owner="event_reflection")
        except Exception as e:  # noqa: BLE001
            logger.info("event reflection ingest failed: %s", e)
            return False
        if not results:
            return False
        status = getattr(results[0], "status", None)
        status_val = getattr(status, "value", status)
        return status_val == "stored"

    # ── 反思 episode（预算计数的持久依据 + 审计）────────────────────────

    def _record_episode(self, cause: str, goal: str, *, stored: bool,
                        detail: str, now: datetime) -> None:
        # 原生 SQL 直写（learning 包不允许 import memory.episode；
        # 与 experience_extractor 的注入/回退模式保持一致）。
        try:
            import sqlite3 as _sql
            conn = _sql.connect(self._db_path, timeout=10)
            try:
                conn.execute(
                    """
                    INSERT INTO episodes (
                        id, experience_id, session_id, context, goal,
                        decision, action, outcome, condition,
                        significance_score, evaluation_trace, source,
                        status, tags, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f"EPI-EREF-{uuid.uuid4().hex[:12]}",
                        f"EXP-EREF-{uuid.uuid4().hex[:8]}",
                        "event_reflection",
                        json.dumps({"kind": "event_reflection",
                                    "cause": cause,
                                    "goal_excerpt": (goal or "")[:160],
                                    "stored": stored, "detail": detail},
                                   ensure_ascii=False),
                        (goal or "失败目标")[:200],
                        f"event_reflection cause={cause} → {detail}",
                        "event_reflection",
                        json.dumps({"success": bool(stored), "cause": cause,
                                    "stored": bool(stored), "detail": detail},
                                   ensure_ascii=False),
                        "",
                        0.6,
                        "{}",
                        "event_reflection",
                        "active",
                        json.dumps(["event_reflection", str(cause)],
                                   ensure_ascii=False),
                        now.isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            logger.debug("event reflection episode skipped: %s", e)
