"""RecallRouter — 子记忆系统统一相关性召回（COG-V2 Phase 1）。

设计依据见 .trae/documents/cognitive_engine_optimization_plan.md：
情景/语义/程序/自传/自我 五类子记忆各管一段，决策前并行召回、统一打分、
按子系统配额竞争进入全局工作空间 MEM_CTX。

本模块只做**陈述性子记忆的 DB 直读召回**（此前生产主链完全读不到）：
  - semantic_knowledge: knowledge 表（dream/反思沉淀的事实与方法）
  - semantic_belief:    belief 表（巩固出的概括性信念）
  - episodic:           episodes 表 *.execute 单次任务处境-结果
  - self:               self_model_fact 表（Phase 2 落库后自动生效）

特性：
  - 纯确定性、零 LLM；2-gram 重叠打分（中文友好，英文按词兼容）；
  - DB 直读 → 跨重启天然连续，不依赖内存水合；
  - 只读连接 + 异常静默降级，任何子库故障不阻断决策主链；
  - 防御性过滤：rejected/低分/套娃/JSON/过期内容一律不召回。
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 与 unified_ingestor 质量门一致的套娃/垃圾模式（防御性，重复一份避免跨层私有引用）
_JUNK_RE = re.compile(
    r"evo[\s\-]?plan|new_knowledge|新知识\s*\[|deepen_topic|^\s*[\{\[]",
    re.IGNORECASE,
)
# 召回侧防御：拒答文本即使漏过入库门也不进工作空间
_REFUSAL_RE = re.compile(
    r"无法确认|无法提供|没有关于.{0,20}权威"
    r"|我没有.{0,12}(?:权威|相关知识|相关信息|资料|可靠来源)"
    r"|as an ai|i don'?t have (?:access|information|specific|enough)",
    re.IGNORECASE,
)

_EPISODIC_ACTIONS = (
    "writer.execute", "researcher.execute", "reviewer.execute",
    "conversation_reply",
)
_KNOWLEDGE_MIN_CONF = 0.60
_BELIEF_MIN_CONF = 0.60
_RECENT_DAYS = 30
_POOL_LIMIT = 300

# 子系统默认配额（全局工作空间总预算在 agent_runtime 处汇总为 9）
DEFAULT_BUDGETS = {
    "self": 1,
    "episodic": 2,
    "procedural": 2,
    "semantic": 2,
    "observation": 1,
    "gap": 1,
}


@dataclass
class RecallItem:
    """统一召回载体（dict 序列化为 agent_runtime 既有 artifact 形状）。"""

    subsystem: str
    type: str
    text: str
    confidence: float
    score: int
    artifact_id: str

    def as_artifact(self) -> dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "type": self.type,
            "text": self.text,
            "confidence": self.confidence,
            "score": self.score,
            "artifact_id": self.artifact_id,
        }


def _bigrams(text: str) -> set[str]:
    """中文按字 2-gram；纯英文/数字片段整体保留为词。"""
    grams = {text[i:i + 2] for i in range(max(len(text) - 1, 0))}
    return {g for g in grams if g.strip()}


def _overlap(text: str, grams: set[str]) -> int:
    if not grams:
        return 0
    return sum(1 for g in grams if g in text)


def _is_clean(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 8:
        return False
    if _JUNK_RE.search(t[:240]):
        return False
    if _REFUSAL_RE.search(t[:200]):
        return False
    return True


class RecallRouter:
    """子记忆 DB 统一召回器；线程安全（每次查询独立只读连接）。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        # recall_citation 表可能不存在（最小化测试库/旧库）— 探测一次后缓存，
        # 缺失时引用续命子句整体降级为纯时间窗（缺表不能拖垮召回）。
        self._citation_table: Optional[bool] = None
        self._episode_status_col: Optional[bool] = None

    def _connect_ro(self) -> Optional[sqlite3.Connection]:
        if not self._db_path or not Path(self._db_path).exists():
            return None
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def _citations_available(self, conn: sqlite3.Connection) -> bool:
        if self._citation_table is None:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='recall_citation' LIMIT 1").fetchone()
            self._citation_table = row is not None
        return self._citation_table

    def _reinforce_sql(self, conn: sqlite3.Connection, ts_expr: str,
                       id_expr: str, cutoff: str) -> tuple[str, list]:
        """生成活性窗 SQL：近窗更新 OR（若引用表存在）近窗被引用续命。"""
        if self._citations_available(conn):
            return (
                f"(substr(replace({ts_expr},'T',' '),1,19) >= datetime('now',?) "
                f"OR {id_expr} IN (SELECT artifact_id FROM recall_citation "
                f"WHERE cited_at >= datetime('now',?) AND artifact_id IS NOT NULL))",
                [cutoff, cutoff],
            )
        return (
            f"substr(replace({ts_expr},'T',' '),1,19) >= datetime('now',?)",
            [cutoff],
        )

    def recall(
        self,
        description: str,
        *,
        budgets: Optional[dict[str, int]] = None,
        task_ctx: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """按 description 召回相关记忆；返回各子库 top 候选（配额内）。

        调用方（agent_runtime）再与 lesson/WM/skill 等内存来源合并、去重、
        做全局预算截断。
        """
        budgets = budgets or DEFAULT_BUDGETS
        grams = _bigrams((description or "")[:120])
        if not grams:
            return []

        out: list[RecallItem] = []
        for getter in (
            self._recall_knowledge,
            self._recall_beliefs,
            self._recall_episodes,
            self._recall_procedural,
            self._recall_self,
        ):
            name = getter.__name__
            try:
                out.extend(getter(grams, budgets))
            except Exception:
                logger.debug("recall subsystem failed: %s", name, exc_info=True)

        # self 子系统豁免 _is_clean — 自我画像的"当前专注"可能含目标名
        # 中的关键词（如 EVO-Plan），这些不是知识垃圾。
        items = [it.as_artifact() for it in out
                 if it.subsystem == "self" or _is_clean(it.text)]
        # 同子库内 60 字前缀去重（同主题多条常共用长前缀，避免挤占配额）
        uniq: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for a in sorted(items,
                        key=lambda x: (x["score"], x["confidence"]),
                        reverse=True):
            key = (a["subsystem"],
                   re.sub(r"\s+", "", a["text"])[:60])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(a)
        logger.debug(
            "RecallRouter('%s') → %d 候选 (sem/epi/self)",
            (description or "")[:40], len(uniq),
        )
        return uniq

    # ── 语义记忆：knowledge 表 ───────────────────────────────────────────

    def _recall_knowledge(
        self, grams: set[str], budgets: dict[str, int]
    ) -> list[RecallItem]:
        conn = self._connect_ro()
        if conn is None:
            return []
        try:
            active_sql, active_params = self._reinforce_sql(
                conn, "COALESCE(updated_at, created_at)", "id",
                f"-{_RECENT_DAYS} day")
            rows = conn.execute(
                "SELECT id, statement, confidence FROM knowledge "
                "WHERE COALESCE(status,'') NOT IN ('rejected','deprecated') "
                # 工具配方由 _recall_procedural 专路召回，避免双通道重复占位
                "AND COALESCE(statement,'') NOT LIKE '【工具配方】%' "
                "AND COALESCE(confidence,0) >= ? "
                # 引用即强化：近窗被引用过的老知识续命（COG-V2 Phase4）
                f"AND {active_sql} "
                "ORDER BY updated_at DESC LIMIT ?",
                [_KNOWLEDGE_MIN_CONF, *active_params, _POOL_LIMIT],
            ).fetchall()
        finally:
            conn.close()

        scored = []
        for kid, statement, conf in rows:
            text = (statement or "").strip()
            if not _is_clean(text):
                continue
            s = _overlap(text[:500], grams)
            if s <= 0:
                continue
            scored.append(RecallItem(
                subsystem="semantic", type="knowledge",
                text=text[:180], confidence=float(conf or 0.6),
                score=s, artifact_id=str(kid),
            ))
        scored.sort(key=lambda it: (it.score, it.confidence), reverse=True)
        return scored[:budgets.get("semantic", 2)]

    # ── 语义记忆：belief 表（DB 信念，此前从不水合/召回）──────────────────

    def _recall_beliefs(
        self, grams: set[str], budgets: dict[str, int]
    ) -> list[RecallItem]:
        conn = self._connect_ro()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                "SELECT id, statement, confidence FROM belief "
                "WHERE COALESCE(status,'active') = 'active' "
                "AND COALESCE(confidence,0) >= ? "
                "ORDER BY confidence DESC, last_updated DESC LIMIT ?",
                (_BELIEF_MIN_CONF, _POOL_LIMIT),
            ).fetchall()
        finally:
            conn.close()

        scored = []
        for bid, statement, conf in rows:
            text = (statement or "").strip()
            if not _is_clean(text):
                continue
            s = _overlap(text[:300], grams)
            if s <= 0:
                continue
            scored.append(RecallItem(
                subsystem="semantic", type="belief",
                text=text[:150], confidence=float(conf or 0.6),
                # 信念是抽象概括, 同重叠度下略低于具体知识
                score=s, artifact_id=str(bid),
            ))
        scored.sort(key=lambda it: (it.score, it.confidence), reverse=True)
        # 与 knowledge 共享 semantic 配额 — 调用方合并截断，这里给候选即可
        return scored[:budgets.get("semantic", 2)]

    # ── 情景记忆：episodes 表 *.execute ──────────────────────────────────

    def _recall_episodes(
        self, grams: set[str], budgets: dict[str, int]
    ) -> list[RecallItem]:
        conn = self._connect_ro()
        if conn is None:
            return []
        placeholders = ",".join("?" for _ in _EPISODIC_ACTIONS)
        since = (datetime.now(timezone.utc) - timedelta(days=_RECENT_DAYS)).isoformat()
        # 旧库/最小测试库 episodes 可能无 status 列 — 有则排除 archived
        if self._episode_status_col is None:
            col = conn.execute(
                "SELECT 1 FROM pragma_table_info('episodes') "
                "WHERE name='status' LIMIT 1").fetchone()
            self._episode_status_col = col is not None
        status_sql = ("AND COALESCE(status,'active') != 'archived' "
                      if self._episode_status_col else "")
        try:
            rows = conn.execute(
                f"SELECT id, action, goal, decision, outcome, context "
                f"FROM episodes WHERE action IN ({placeholders}) "
                f"{status_sql}"
                f"AND created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (*_EPISODIC_ACTIONS, since, _POOL_LIMIT),
            ).fetchall()
        finally:
            conn.close()

        scored = []
        for eid, action, goal, decision, outcome, context_json in rows:
            desc_raw = ""
            success: Optional[bool] = None
            output = ""
            try:
                ctx = json.loads(context_json or "{}")
                if isinstance(ctx, dict):
                    desc_raw = str(ctx.get("description") or "")
                    success = ctx.get("success")
                    output = str(ctx.get("output") or "")[:120]
            except Exception:
                pass
            desc_raw = desc_raw or (goal or "")
            if not _is_clean(desc_raw):
                continue
            hay = f"{desc_raw}\n{decision or ''}"
            s = _overlap(hay[:600], grams)
            if s <= 0:
                continue
            verb = "成功" if success is True else (
                "失败" if success is False else "执行")
            tail = output or (decision or "").strip().replace("\n", " ")
            text = f"既往{action.split('.')[0]}任务「{desc_raw[:60]}」→{verb}：{tail[:90]}"
            conf = 0.75 if success is True else 0.6
            scored.append(RecallItem(
                subsystem="episodic", type="episode",
                text=text[:180], confidence=conf,
                score=s + (1 if success is True else 0),
                artifact_id=str(eid),
            ))
        scored.sort(key=lambda it: (it.score, it.confidence), reverse=True)
        return scored[:budgets.get("episodic", 2)]

    # ── 程序记忆：tool_recipe 成功配方（Phase 3.2）──────────────────────

    def _recall_procedural(
        self, grams: set[str], budgets: dict[str, int]
    ) -> list[RecallItem]:
        """成功配方知识（statement 以【工具配方】开头）按相关性召回。

        失败侧程序记忆（mutation_policy/failure_lesson）仍由 agent_runtime
        既有 lesson 注入路径负责（带 30min 去重），这里只补建设性的成功
        姿势，避免同一教训两处重复表达。
        """
        conn = self._connect_ro()
        if conn is None:
            return []
        try:
            active_sql, active_params = self._reinforce_sql(
                conn, "COALESCE(updated_at, created_at)", "id",
                f"-{_RECENT_DAYS} day")
            rows = conn.execute(
                "SELECT id, statement, confidence FROM knowledge "
                "WHERE COALESCE(status,'') NOT IN ('rejected','deprecated') "
                "AND statement LIKE '【工具配方】%' "
                # 引用即强化：被引用的配方跨 30 天窗续命（COG-V2 Phase4）
                f"AND {active_sql} "
                "ORDER BY updated_at DESC LIMIT 100",
                active_params,
            ).fetchall()
        finally:
            conn.close()
        scored = []
        for kid, statement, conf in rows:
            text = (statement or "").strip()
            if not _is_clean(text):
                continue
            s = _overlap(text[:500], grams)
            if s <= 0:
                continue
            scored.append(RecallItem(
                subsystem="procedural", type="tool_recipe",
                text=text[:180], confidence=float(conf or 0.75),
                # 成功姿势是高价值前验：重叠分基础上 +1
                score=s + 1, artifact_id=str(kid),
            ))
        scored.sort(key=lambda it: (it.score, it.confidence), reverse=True)
        return scored[:budgets.get("procedural", 2)]

    # ── 自我模型（P0-1 Step 3: 唯一经 S2 committed projection，不复用 S1）──

    def _recall_self(
        self, grams: set[str], budgets: dict[str, int]
    ) -> list[RecallItem]:
        """从 S2 committed projection 取紧凑自我摘要。

        P0-1 Step 3: S1.render_brief() ✗ → S2 accessor.brief()（committed 态，不读 S1）。
        brief 为 S2 的确定性聚合，无 LLM。
        """
        try:
            from ocos.self.self_state import get_self_projection
            s2 = get_self_projection(self._db_path)
            brief = s2.brief() if s2 is not None else ""
        except Exception:
            return []
        if not brief:
            return []
        s = _overlap(brief, grams)
        return [RecallItem(
            subsystem="self", type="self",
            text=brief, confidence=0.85,
            # 自我相关性始终给基础分 2，保证每条决策都进工作空间（Phase 2
            # 设计不变量：决策前必读 self）
            score=s + 2,
            artifact_id="self:brief",
        )][:budgets.get("self", 1)]
