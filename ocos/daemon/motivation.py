"""L3 (升级方案 v1.0): MotivationHub — 自主性涌现：让目标自己长出来。

信号 → 评分 → 提案 →（autonomy 闸）落地 的自生成目标管线：

    失败 lesson episodes ──┐
    低置信 belief 边界 ─────┼→ 候选目标 → 三维评分 → 去重/限速 → 提案
    goal_result 低成功率 ───┘

落地（全部在 OCOS_AUTONOMY_LEVEL 约束下）:
    LEVEL>=2 且 kind ∈ {PROBE, LEARN}（低风险只读探测/学习类）
        → goals 表 PENDING（source='autonomous'），
          daemon _claim_persisted_goals 自动认领执行；
    其余（LEVEL=1，或 REPAIR 高风险类）一律进 PendingStore 待批
        （action_type='autonomous_goal'，bridge 批准后写 goals 表）。

防跑飞:
    - PROBE/LEARN 目标描述限定只读探测/学习；REPAIR 即使 LEVEL>=2 也待批
      （自主目标不得夹带审批动作/写操作）；
    - 连续 3 次自主目标失败（goal_result outcome.success 真值）→ 自动
      降级 LEVEL 并 audit + 如实上报（record_result 返回降级信息）；
    - 每日提案上限 OCOS_AUTONOMY_GOAL_CAP（默认 5）。

主动目标循环（2026-09-08）:
    刺激通道解决导向 — 同 key 重复触发即沿 PROBE→LEARN→REPAIR 阶梯
    升级（前序响应未消除该条件），走满 3 次饱和静默；刺激与 scan 共享
    每日预算。目标完成 ≠ 问题解决，循环以"条件是否消除"为准绳。

诚实性:
    - 评分全部由真实数据推导（lesson 出现次数 / episode 成功率 / belief
      置信度），无 LLM、无随机数，每项候选携带 evidence；
    - 无信号时零提案（不编造动机）；
    - 每次提案落 episode（source='autonomous_goal_proposal'）供限速、
      去重与审计溯源。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GOAL_CAP_ENV = "OCOS_AUTONOMY_GOAL_CAP"
DEFAULT_GOAL_CAP = 5
FAILURE_DEMOTE_THRESHOLD = 3      # 连续失败 N 次 → 自动降级
SCORE_THRESHOLD = 0.5             # 综合分低于此值不成提案
CONF_MIN, CONF_MAX = 0.3, 0.6     # 低置信边界（好奇心探测区间）
LOOKBACK_DAYS = 7
LOW_GOAL_SUCCESS_RATE = 0.6       # goal_result 低于此 → LEARN 信号

# LEVEL>=2 可自主执行的低风险 kind 白名单；其余 kind 一律待批
LOW_RISK_KINDS = ("PROBE", "LEARN")

# 主动目标循环（2026-09-08）: 同刺激 key 重复触发 = 前序响应未解决 →
# kind 沿阶梯升级（PROBE 分析 → LEARN 复盘 → REPAIR 修复，REPAIR 永待批）；
# 走满 MAX_RESPONSES_PER_KEY 次后饱和静默（防噪，慢性问题交 verify_repairs/
# 防跑飞机制接管）。响应计数持久化于提案 episodes，跨重启对账。
ESCALATION_LADDER = ("PROBE", "LEARN", "REPAIR")
MAX_RESPONSES_PER_KEY = 3


@dataclass
class GoalCandidate:
    """自生成目标候选（全部字段可溯源）。"""
    kind: str                    # PROBE / LEARN / REPAIR
    description: str
    domain: str = "analysis"
    value: float = 0.0           # 价值对齐 [0,1]
    novelty: float = 1.0         # 新颖性 [0,1]（与近期提案/在途重复 → 0）
    feasibility: float = 0.0     # 可行性 [0,1]（episode 成功率语义）
    evidence: str = ""
    score: float = 0.0

    @property
    def low_risk(self) -> bool:
        return self.kind in LOW_RISK_KINDS


def _open_ro(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MotivationHub:
    """动机中枢 — 聚合信号、评分并产出自主目标提案（autonomy 闸内）。"""

    def __init__(
        self,
        db_path: str,
        goal_store: Any = None,        # ocos.goal.store.GoalStore
        pending_store: Any = None,     # ocos.execution.pending.PendingStore
        belief_store: Any = None,      # ocos.memory.belief.store.BeliefStore
        notify_fn: Any = None,         # callable(str) — outbox 通知
    ) -> None:
        from typing import Any as _Any  # noqa: F401  (annotation use)
        self._db_path = db_path
        self._goal_store = goal_store
        self._pending_store = pending_store
        self._belief_store = belief_store
        self._notify_fn = notify_fn
        self._consecutive_failures = 0   # 防跑飞计数（进程内，结果闭环驱动）
        base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
        self._audit_dir = (Path(base).expanduser() if base
                           else Path.home() / ".ocos" / "audit")

    # ── 主入口 ────────────────────────────────────────────────────────

    def scan(self) -> dict:
        """扫描信号并产出自主目标提案（daemon 每 N tick 调用一次）。

        返回统计 dict（供日志/测试断言）：
        {level, candidates, proposed, pending_enqueued, auto_enqueued,
         capped, demoted}
        """
        from ocos.execution.autonomy import can_propose, get_autonomy_level

        stats = {"level": get_autonomy_level(), "candidates": 0,
                 "proposed": 0, "pending_enqueued": 0, "auto_enqueued": 0,
                 "capped": False, "demoted": None}
        level = stats["level"]
        if level < 1 or not can_propose(level):
            return stats                       # LEVEL0: 零自主（诚实沉默）

        cap = self._daily_cap()
        already = self._count_today()
        if already >= cap:
            stats["capped"] = True
            return stats

        candidates = self.collect_candidates()
        stats["candidates"] = len(candidates)
        for c in candidates:
            c.score = round(0.4 * c.value + 0.3 * c.novelty
                            + 0.3 * c.feasibility, 4)
        candidates.sort(key=lambda x: x.score, reverse=True)

        for c in candidates:
            if stats["proposed"] + already >= cap:
                stats["capped"] = True
                break
            if c.score < SCORE_THRESHOLD:
                break                          # 排序后后面的只会更低
            if c.novelty <= 0 or self._is_duplicate(c):
                continue                       # 与近期提案/在途重复
            # PHASE-LIFE: 熔断 — 同一个 goal 描述在最近 7 天内
            # 连续失败 ≥ 3 次 → 停止 propose，写熔断 episode
            if self._is_goal_fused(c.description):
                logger.info(
                    "MotivationHub: goal fused (consecutive failures ≥3): %s",
                    c.description[:80],
                )
                self._record_fuse_episode(c.description)
                continue
            self._propose(c, level, stats)
        return stats

    # ── 信号聚合 ──────────────────────────────────────────────────────

    def collect_candidates(self) -> list[GoalCandidate]:
        """四类信号 → 候选（全部真实数据源，无信号返回空表）。

        失败 lesson / 低置信 belief 边界（模板回声已滤除）/
        自我探查（未触及模块）/ goal_result 成功率。
        """
        candidates: list[GoalCandidate] = []
        try:
            candidates.extend(self._from_lessons())
        except Exception as e:
            # warning 级（O-7 先例）：信号通道静默失败曾掩盖装配缺陷
            logger.warning("lesson signals failed: %s", e)
        try:
            candidates.extend(self._from_belief_boundary())
        except Exception as e:
            logger.warning("belief boundary signals failed: %s", e)
        try:
            candidates.extend(self._from_self_exploration())
        except Exception as e:
            logger.warning("self exploration signals failed: %s", e)
        try:
            candidates.extend(self._from_goal_results())
        except Exception as e:
            logger.warning("goal result signals failed: %s", e)
        return candidates

    def _from_lessons(self) -> list[GoalCandidate]:
        """失败 lesson（近 7 天）→ REPAIR 候选（按 cause 聚合去重）。"""
        since = (datetime.now(timezone.utc)
                 - timedelta(days=LOOKBACK_DAYS)).isoformat()
        conn = _open_ro(self._db_path)
        try:
            rows = conn.execute(
                "SELECT decision, tags, created_at FROM episodes "
                "WHERE source='lesson' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 50", (since,)).fetchall()
        finally:
            conn.close()
        by_cause: dict[str, dict] = {}
        for r in rows:
            try:
                tag_list = json.loads(r["tags"] or "[]")
            except ValueError:
                tag_list = []
            cause = "general"
            for t in tag_list if isinstance(tag_list, list) else []:
                if t and t != "failure_lesson":
                    cause = str(t)
                    break
            info = by_cause.setdefault(cause, {"count": 0})
            info["count"] += 1
        out = []
        for cause, info in by_cause.items():
            n = info["count"]
            out.append(GoalCandidate(
                kind="REPAIR",
                description=(f"复盘并验证「{cause}」类失败的修复方向"
                             f"（近 7 天出现 {n} 次）"),
                domain="development",
                value=min(1.0, 0.4 + 0.2 * n),
                feasibility=self._domain_success_rate(),
                evidence=f"lesson cause={cause} x{n}",
            ))
        return out

    def _from_belief_boundary(self) -> list[GoalCandidate]:
        """低置信边界（0.3-0.6）→ PROBE 只读探测候选（好奇心机制）。

        置信度越接近区间中央（0.5）信息增益越大 → 价值越高。
        belief_store 支持两种形态：
          - 直接实例（query_by_confidence 的持久 BeliefStore / 内存
            BeliefManager 等）；
          - 可调用提供者（daemon 装配时 memory hub 尚未 boot，惰性解析
            — 每次 scan 求值一次；boot 前解析为 None → 诚实沉默）。
        兼容两种查询 API：query_by_confidence(min, max, limit) 与
        query(min_probability=, limit=)。
        """
        store = (self._belief_store() if callable(self._belief_store)
                 else self._belief_store)
        if store is None:
            return []
        items: list[tuple[str, float, str]] = []   # (statement, conf, id)
        if hasattr(store, "query_by_confidence"):
            for b in store.query_by_confidence(
                    CONF_MIN, CONF_MAX, limit=10):
                items.append((getattr(b, "statement", "") or "",
                              float(getattr(b, "confidence", 0.5)),
                              str(getattr(b, "id", "?"))))
        else:
            for b in store.query(
                    min_probability=CONF_MIN, limit=50):
                p = float(getattr(b, "probability", 0.5))
                if p <= CONF_MAX:
                    items.append((getattr(b, "statement", "") or "",
                                  p, str(getattr(b, "belief_id", "?"))))
                if len(items) >= 10:
                    break
        out = []
        for statement, conf, bid in items:
            if not statement:
                continue
            if "相关经历持续出现" in statement:
                # 模板回声信念（pattern 派生）无信息增益——生产实证 241 个
                # 边界信念 100% 为此类，探测它们 = 好奇心空转（2026-09-08）
                continue
            out.append(GoalCandidate(
                kind="PROBE",
                description=(f"只读探测：搜集证据验证信念「{statement[:80]}」"
                             f"（当前置信度 {conf:.2f}），并更新信念库"),
                domain="research",
                value=round(1.0 - abs(conf - 0.5) * 2, 4),
                feasibility=0.9,               # 只读探测天然可行
                evidence=f"belief {bid} conf={conf:.2f}",
            ))
        return out

    def _from_self_exploration(self) -> list[GoalCandidate]:
        """自我探查（好奇心·第二源）。

        PHASE-LIFE Phase 2: EpistemicDrive.suggest_all() — 三种好奇心：
          - 【探索型】无中生有：宿主机工具/外部知识源/能力边界
          - 【成长型】弱点驱动：agent 成功率/重复失败模式
          - 【修复型】预测误差：原来的 suggest() 行为
        探索型 2x 权重优先，成长型 1.5x，修复型 1x。
        """
        candidates: list[GoalCandidate] = []

        # Step 1: EpistemicDrive.suggest_all()（三种好奇心）
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker, EpistemicDrive

            tracker = PredictionGapTracker(db_path=self._db_path)
            drive = EpistemicDrive(tracker=tracker, db_path=self._db_path, top_n=1)

            # 1a: 探索型好奇心（无中生有）
            for goal_text in drive.suggest_explore():
                candidates.append(GoalCandidate(
                    kind="EXPLORE",
                    description=goal_text,
                    domain="exploration",
                    value=0.9,           # 探索天然高价值
                    novelty=1.0,         # 全新领域 → 最大新颖度
                    feasibility=0.8,     # 都是只读/轻量操作
                    evidence="epistemic.explore: 外部世界好奇心",
                ))

            # 1b: 成长型好奇心（弱点驱动）
            for goal_text in drive.suggest_growth():
                candidates.append(GoalCandidate(
                    kind="GROW",
                    description=goal_text,
                    domain="growth",
                    value=0.8,
                    novelty=0.7,
                    feasibility=0.9,
                    evidence="epistemic.growth: 短板补齐",
                ))

            # 1c: 修复型好奇心（原来的 predict-calibrate）
            for unc in drive.suggest():
                candidates.append(GoalCandidate(
                    kind="PROBE",
                    description=unc.suggested_goal,
                    domain="research",
                    value=0.7 + unc.uncertainty_score,
                    novelty=min(1.0, 0.5 + unc.uncertainty_score),
                    feasibility=0.7,
                    evidence=(
                        f"epistemic.repair: mean_gap={unc.mean_gap:.2f} "
                        f"n={unc.sample_count} uncertainty={unc.uncertainty_score:.2f}"
                    ),
                ))

            if candidates:
                return candidates[:3]  # 最多返回 3 个（探索/成长/修复各 1）
        except Exception as e:
            logger.debug("EpistemicDrive unavailable, falling back to module inventory: %s", e)

        # Step 2: Fallback — 从未被触及的模块（原有逻辑保留）
        try:
            import pkgutil
            import ocos as _pkg
            names = sorted({m.name for m in pkgutil.iter_modules(_pkg.__path__)})
        except Exception as e:
            logger.warning("module inventory failed: %s", e)
            return []
        if not names:
            return []
        offset = datetime.now(timezone.utc).timetuple().tm_yday % len(names)
        window = [names[(offset + i) % len(names)] for i in range(min(8, len(names)))]
        unexplored: list[str] = []
        conn = _open_ro(self._db_path)
        try:
            for name in window:
                like = f"%ocos.{name}%"
                row = conn.execute(
                    "SELECT 1 FROM episodes "
                    "WHERE goal LIKE ? OR decision LIKE ? LIMIT 1",
                    (like, like)).fetchone()
                if row is None:
                    unexplored.append(name)
                if len(unexplored) >= 1:
                    break
        finally:
            conn.close()
        for name in unexplored:
            return [GoalCandidate(
                kind="PROBE",
                description=(f"自我探查：模块 ocos.{name} 从未在实践中被触及"
                             f"——只读梳理其职责、接口与被设计意图，"
                             f"产出一段结构化摘要沉淀为知识"),
                domain="research",
                value=0.6,
                novelty=1.0,
                feasibility=0.95,
                evidence=f"pkgutil inventory: ocos.{name} 无 episode 提及",
            )]
        return []

    def _from_goal_results(self) -> list[GoalCandidate]:
        """近期 goal_result 成功率走低 → LEARN 复盘候选。"""
        since = (datetime.now(timezone.utc)
                 - timedelta(days=LOOKBACK_DAYS)).isoformat()
        conn = _open_ro(self._db_path)
        try:
            rows = conn.execute(
                "SELECT outcome FROM episodes "
                "WHERE source='goal_result' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 20", (since,)).fetchall()
        finally:
            conn.close()
        rates = []
        for r in rows:
            try:
                oc = json.loads(r["outcome"] or "{}")
                if isinstance(oc.get("task_success_rate"), (int, float)):
                    rates.append(float(oc["task_success_rate"]))
            except (ValueError, TypeError):
                continue
        if len(rates) < 2:
            return []
        avg = sum(rates) / len(rates)
        if avg >= LOW_GOAL_SUCCESS_RATE:
            return []
        return [GoalCandidate(
            kind="LEARN",
            description=(f"复盘学习：分析近期目标成功率走低的原因"
                         f"（近 7 天均值 {avg:.0%}，{len(rates)} 个目标），"
                         f"产出可执行改进项"),
            domain="analysis",
            value=0.6,
            feasibility=round(1.0 - avg, 4),
            evidence=f"goal_result avg_success={avg:.2f} n={len(rates)}",
        )]

    # ── 落地 ──────────────────────────────────────────────────────────

    def _propose(self, c: GoalCandidate, level: int, stats: dict) -> None:
        """单条提案落地：GoalGenesis 提案引擎 → 分级批准 → goal_store.save().

        P1 宪法修正案 (Step 1.4): 原来直接 save，现在加 GoalProposal 中间层
        + 分级批准通道。保留 level>=2 low_risk 条件，但 authority 改为 PROPOSAL。
        """
        # ── P1: GoalGenesis 提案引擎 ──────────────────────────────────
        try:
            from ocos.autonomous.goal_genesis import GoalGenesis
            genesis = GoalGenesis(db_path=self._db_path)
            proposals = genesis.produce(
                suggestions=[c.description],
                domain=c.domain,
                source=c.kind.lower(),
            )
            prop = proposals[0]
            prop.value_score = c.score  # 复用现有 score
            genesis._persist(prop)
            prop = genesis.approve(prop)  # LOW/MEDIUM auto, HIGH reject
            if prop.status != "APPROVED":
                stats.setdefault("rejected", 0)
                stats["rejected"] += 1
                logger.info("MotivationHub: GoalGenesis REJECTED %s (risk=%s)",
                            prop.proposal_id, prop.risk_level)
                return
        except Exception:
            # GoalGenesis 不可用时回退到旧逻辑（不阻塞 motivation）
            logger.debug("GoalGenesis unavailable, falling back to direct save", exc_info=True)
            genesis = None
            prop = None

        # ── 落地: 低风险直写 goals 表，其余进待批 ────────────────────
        goal_id = f"GOAL-AUTO-{uuid.uuid4().hex[:12]}"
        if level >= 2 and c.low_risk and self._goal_store is not None:
            # P1: authority 从 AUTONOMOUS 改为 PROPOSAL（走 GoalGenesis 宪法通道）
            prop_id = prop.proposal_id if prop else None
            self._goal_store.save(
                goal_id=goal_id, level="TASK", status="PENDING",
                description=c.description,
                source="goal_genesis" if genesis else "autonomous",
                source_id=prop_id or "",
                metadata={"autonomous": True, "kind": c.kind,
                          "domain": c.domain, "score": c.score,
                          "evidence": c.evidence,
                          **({"proposal_id": prop_id, "value_score": prop.value_score,
                              "risk_level": prop.risk_level} if prop else {})},
                origin_level="SELF",
                authority="PROPOSAL" if genesis else "AUTONOMOUS")
            stats["auto_enqueued"] += 1
            if prop and genesis:
                genesis.mark_completed(prop.proposal_id)
        elif self._pending_store is not None:
            pid = self._pending_store.enqueue(
                action_type="autonomous_goal",
                target=goal_id,
                payload={"goal_id": goal_id, "description": c.description,
                         "domain": c.domain, "kind": c.kind,
                         "score": c.score, "evidence": c.evidence},
                text=c.description,
                source="l3_motivation")
            stats["pending_enqueued"] += 1
            logger.info("MotivationHub: autonomous goal pending %s (%s)",
                        pid, c.kind)
        else:
            # 装配缺陷告警（2026-09-07 生产零提案根因即此分支静默 return）
            logger.warning(
                "MotivationHub: candidate %s dropped — no landing channel "
                "(pending_store/goal_store both unwired)", c.kind)
            return                          # 无落地通道（goal/pending 皆缺）

        stats["proposed"] += 1
        self._record_proposal_episode(c, goal_id, via)
        if self._notify_fn is not None:
            try:
                tag = ("已自动提交执行" if via == "goals_table"
                       else "已进入待批队列（ocos approvals 可批准）")
                self._notify_fn(
                    f"自主目标提案（{c.kind}，评分 {c.score:.2f}）：\n"
                    f"{c.description}\n→ {tag}")
            except Exception:
                logger.debug("motivation notify failed", exc_info=True)

    def _record_proposal_episode(self, c: GoalCandidate, goal_id: str,
                                 via: str) -> None:
        """提案 episode — 限速/去重/审计的持久依据。失败不阻断提案。"""
        try:
            from ocos.memory.episode.models import Episode, EpisodeStatus
            from ocos.memory.episode.store import EpisodeStore
            store = EpisodeStore(db_path=self._db_path)
            store.initialize()
            store.save(Episode(
                id=f"EPI-MOTIV-{uuid.uuid4().hex[:12]}",
                experience_id=f"EXP-MOTIV-{uuid.uuid4().hex[:8]}",
                created_at=datetime.now(timezone.utc),
                session_id="motivation",
                context={"kind": c.kind, "goal_id": goal_id, "via": via,
                         "score": c.score},
                goal="自主目标提案",
                decision=c.description,
                action="autonomous_goal_proposal",
                outcome={"success": True, "kind": c.kind, "via": via,
                         "score": c.score, "evidence": c.evidence},
                significance_score=0.5,
                source="autonomous_goal_proposal",
                status=EpisodeStatus.ACTIVE,
                tags=["autonomous", c.kind],
            ))
        except Exception as e:
            logger.debug("proposal episode skipped: %s", e)

    # ── V3 感知-反应（2026-09-07 感知层上电） ─────────────────────────

    def propose_stimulus(self, stimuli: list[dict], level: int) -> dict:
        """环境刺激 → 候选落地（主动目标循环：解决导向，非打地鼠）。

        stimuli 来自 StimulusScanner.scan()（真实环境信号，冷却过滤后）。
        冷却结束同 key 重复触发 = 前序响应未消除该条件 → 反复生成同型
        PROBE 只会空耗每日名额（2026-09-08 生产实证：近 2 天 19 条提案
        18 条为同 key 重复 PROBE）。主动目标循环三道闸：

          1. cap 共享 — 与 scan() 共用每日提案预算（_count_today/_daily_cap），
             刺激通道不再无限额；
          2. 升级阶梯 — 同 key 第 n 次响应 kind 取 ESCALATION_LADDER[n]：
             PROBE(分析) → LEARN(复盘) → REPAIR(修复，永待批)，
             描述诚实注明"第 N 次响应，前序未消除该条件"；
          3. 饱和静默 — 阶梯走满（MAX_RESPONSES_PER_KEY）后同 key 不再
             提案（防噪；慢性问题由 verify_repairs/防跑飞机制接管）。

        响应计数持久化于 autonomous_goal_proposal episodes — 跨重启不重置
        （scanner 冷却是进程内存态，重启即失效，此处为持久对账）。
        """
        stats = {"stimuli": len(stimuli), "proposed": 0,
                 "auto_enqueued": 0, "pending_enqueued": 0, "skipped": 0,
                 "capped": False, "escalated": 0, "saturated": 0}
        if level < 1:                        # LEVEL0: 零自主（诚实沉默）
            return stats
        cap = self._daily_cap()
        for s in stimuli:
            if stats["proposed"] + self._count_today() >= cap:
                stats["capped"] = True
                break
            key = str(s.get("key", "unknown"))
            n = self._stimulus_response_count(key)
            if n >= MAX_RESPONSES_PER_KEY:
                stats["saturated"] += 1
                logger.info("Stimulus[%s] saturated (%d prior responses) "
                            "— no further proposals", key, n)
                continue
            kind = ESCALATION_LADDER[min(n, len(ESCALATION_LADDER) - 1)]
            prior_note = ("" if n == 0
                          else f"（第 {n + 1} 次响应，前序响应未消除该条件）")
            c = GoalCandidate(
                kind=kind,
                description=f"响应环境刺激[{key}]{prior_note}："
                            f"{s.get('description', '')}",
                domain="analysis",
                value=0.8,
                novelty=1.0 if n == 0 else 0.6,   # 重复条件 → 新颖性打折
                feasibility=0.9,
                # "perception" 前缀随 evidence 透传进 goals.metadata —
                # vitals._perception_metrics 据此统计刺激→行为响应率
                evidence=f"perception stimulus {key} response#{n + 1}: "
                         f"{json.dumps(s.get('evidence', {}),
                                       ensure_ascii=False)[:380]}",
                score=0.85)
            before = (stats["auto_enqueued"], stats["pending_enqueued"])
            self._propose(c, level, stats)
            if (stats["auto_enqueued"], stats["pending_enqueued"]) != before:
                if n > 0:
                    stats["escalated"] += 1
        return stats

    def _stimulus_response_count(self, key: str) -> int:
        """同 stimulus key 的历史响应次数（持久 episodes 对账）。"""
        marker = f"响应环境刺激[{key}]"
        try:
            conn = _open_ro(self._db_path)
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM episodes "
                    "WHERE source='autonomous_goal_proposal' "
                    "AND decision LIKE ?",
                    (f"%{marker}%",)).fetchone()
                return int(row[0])
            finally:
                conn.close()
        except sqlite3.Error:
            return 0

    # ── V2 行为级验收（2026-09-07: REPAIR"产出文本"→"可观测变更"） ────

    REPAIR_VERIFY_HOURS = 6

    def record_repair_completion(self, cause: str,
                                 goal_ref: str = "") -> None:
        """REPAIR 目标完成打点 — daemon 在 goal_result 落库时回调。

        行为级验收的数据起点: 没有此打点，复盘永远只是"产出文本"。
        """
        self._append_mark("repair_completed", cause=str(cause)[:40],
                          goal_ref=str(goal_ref)[:60])

    def verify_repairs(self) -> dict:
        """REPAIR 行为级验收扫描（daemon 每 120 tick 调用）。

        对每条未验收 repair_completed:
          - 验收窗（6h）未到 → pending
          - 完成后出现同 cause lesson_prior_injected → adopted_behavior
            （先验被真实注入执行 = 复盘产物被行为侧消费）
          - 完成后出现同 cause 失败 lesson → not_adopted（复发，如实记）
          - 窗到且无复发无注入 → adopted_no_recurrence
        结果写 repair_verified 打点（vitals reflection_adoption_rate
        数据源）。幂等: (cause, completed_ts) 已验收不重扫。
        """
        marks = self._read_marks()
        done = {(v.get("cause"), v.get("completed_ts"))
                for v in marks if v.get("type") == "repair_verified"}
        stats = {"checked": 0, "adopted": 0, "not_adopted": 0, "pending": 0}
        now = datetime.now(timezone.utc)
        for c in marks:
            if c.get("type") != "repair_completed":
                continue
            stats["checked"] += 1
            cause, ts0 = str(c.get("cause", "general")), str(c.get("ts", ""))
            if (cause, ts0) in done:
                continue
            try:
                t0 = datetime.fromisoformat(ts0)
                hours = (now - t0).total_seconds() / 3600.0
            except (ValueError, TypeError):
                hours = self.REPAIR_VERIFY_HOURS + 1.0
            if hours < self.REPAIR_VERIFY_HOURS:
                stats["pending"] += 1
                continue
            injected = any(
                m.get("type") == "lesson_prior_injected"
                and str(m.get("cause")) == cause
                and str(m.get("ts", "")) > ts0 for m in marks)
            recurrence = self._cause_recurred_since(cause, ts0)
            if injected:
                status = "adopted_behavior"
            elif recurrence:
                status = "not_adopted"
            else:
                status = "adopted_no_recurrence"
            self._append_mark("repair_verified", cause=cause,
                              completed_ts=ts0, status=status,
                              verified_hours=round(hours, 1))
            if status.startswith("adopted"):
                stats["adopted"] += 1
            else:
                stats["not_adopted"] += 1
        return stats

    def _cause_recurred_since(self, cause: str, since_iso: str) -> bool:
        """同 cause 失败 lesson 是否在 since 之后复发。"""
        try:
            conn = _open_ro(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT tags FROM episodes WHERE source='lesson' "
                    "AND created_at > ?", (since_iso,)).fetchall()
            finally:
                conn.close()
        except Exception:
            logger.debug("recurrence check failed", exc_info=True)
            return False
        for (tags_raw,) in rows:
            try:
                tag_list = json.loads(tags_raw or "[]")
            except ValueError:
                tag_list = []
            for t in (tag_list if isinstance(tag_list, list) else []):
                if t and t != "failure_lesson" and str(t) == cause:
                    return True
        return False

    def _read_marks(self) -> list[dict]:
        """learning.jsonl 全量解析（与 vitals/bridge 同数据源）。"""
        path = self._audit_dir / "learning.jsonl"
        if not path.exists():
            return []
        out: list[dict] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            logger.debug("learning marks read failed", exc_info=True)
        return out

    def _append_mark(self, mark_type: str, **fields: Any) -> None:
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            rec = {"ts": datetime.now(timezone.utc).isoformat(),
                   "type": mark_type, **fields}
            with (self._audit_dir / "learning.jsonl").open(
                    "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("learning mark append failed", exc_info=True)

    # ── 防跑飞：结果闭环 + 连续失败自动降级 ──────────────────────────

    def record_result(self, success: bool) -> dict | None:
        """daemon 在自主目标 goal_result 到达时调用（success 为真实 outcome）。

        连续 FAILURE_DEMOTE_THRESHOLD 次失败 → 自动降级 LEVEL 并 audit，
        返回降级信息 dict（daemon 负责 outbox 如实上报）；成功重置计数。
        """
        from ocos.execution.autonomy import (
            audit_level_change, get_autonomy_level, set_autonomy_level)

        if success:
            self._consecutive_failures = 0
            return None
        self._consecutive_failures += 1
        if self._consecutive_failures < FAILURE_DEMOTE_THRESHOLD:
            return None
        old = get_autonomy_level()
        new = max(0, old - 1)
        self._consecutive_failures = 0
        if new == old:
            return {"demoted": False, "level": old,
                    "reason": "已在 LEVEL0，无法再降级"}
        set_autonomy_level(new)
        audit_level_change(
            self._db_path, old, new,
            source=(f"连续 {FAILURE_DEMOTE_THRESHOLD} 次自主目标失败，"
                    f"防跑飞自动降级"))
        info = {"demoted": True, "from": old, "to": new,
                "reason": (f"连续 {FAILURE_DEMOTE_THRESHOLD} 次自主目标"
                           f"失败，已自动降级 LEVEL {old}→{new}")}
        logger.warning("MotivationHub: %s", info["reason"])
        if self._notify_fn is not None:
            try:
                self._notify_fn(
                    f"防跑飞触发：{info['reason']}（如实上报，"
                    f"可通过 ocos autonomy {old} 恢复）")
            except Exception:
                logger.debug("demote notify failed", exc_info=True)
        return info

    # ── 工具 ──────────────────────────────────────────────────────────

    def _daily_cap(self) -> int:
        try:
            return max(1, int(os.environ.get(GOAL_CAP_ENV, DEFAULT_GOAL_CAP)))
        except ValueError:
            return DEFAULT_GOAL_CAP

    def _count_today(self) -> int:
        """当日已提案数（UTC 日界，episode 持久化 — 重启不重置限速）。"""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            conn = _open_ro(self._db_path)
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM episodes "
                    "WHERE source='autonomous_goal_proposal' "
                    "AND created_at >= ?", (day,)).fetchone()
                return int(row[0])
            finally:
                conn.close()
        except sqlite3.Error:
            return 0

    def _is_duplicate(self, c: GoalCandidate) -> bool:
        """与近 7 天提案或在途目标语义重复 → novelty=0（跳过）。"""
        key = c.description[:40]
        since = (datetime.now(timezone.utc)
                 - timedelta(days=LOOKBACK_DAYS)).isoformat()
        try:
            conn = _open_ro(self._db_path)
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM episodes "
                    "WHERE source='autonomous_goal_proposal' "
                    "AND created_at >= ? AND decision LIKE ?",
                    (since, f"%{key}%")).fetchone()
                if int(row[0]) > 0:
                    c.novelty = 0.0
                    return True
            finally:
                conn.close()
        except sqlite3.Error:
            pass
        if self._goal_store is not None:
            try:
                for g in self._goal_store.load_active():
                    if key in str(g.get("description", "")):
                        c.novelty = 0.0
                        return True
            except Exception:
                pass
        return False

    def _is_goal_fused(self, description: str, threshold: int = 3) -> bool:
        """PHASE-LIFE 熔断: 同一个 goal 描述在近 7 天内连续失败 ≥ threshold 次。

        查询 goal_result episodes（source='goal_result'）的 outcome.success
        真值；匹配 goal 字段包含 description 前 30 字的结果。

        Returns:
            True = 熔断（连续失败 ≥ threshold）
        """
        key = (description or "")[:30]
        since = (datetime.now(timezone.utc)
                 - timedelta(days=LOOKBACK_DAYS)).isoformat()
        try:
            conn = _open_ro(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT outcome FROM episodes "
                    "WHERE source='goal_result' AND goal LIKE ? "
                    "AND created_at >= ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (f"%{key}%", since, threshold + 2),
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return False

        if len(rows) < threshold:
            return False

        consec_fail = 0
        for (outcome_blob,) in rows:
            try:
                oc = json.loads(outcome_blob) if outcome_blob else {}
            except Exception:
                oc = {}
            ok = oc.get("success", True)
            if ok is False or ok == 0:
                consec_fail += 1
                if consec_fail >= threshold:
                    return True
            else:
                break  # 成功打断连续

        return False

    def _record_fuse_episode(self, description: str) -> None:
        """写熔断 episode — 防止同一 goal 再次 propose。"""
        try:
            from ocos.memory.episode.store import EpisodeStore
            from ocos.memory.episode.models import Episode
            store = EpisodeStore(db_path=self._db_path)
            store.initialize()
            ep = Episode(
                id=f"EP-FUSE-{uuid.uuid4().hex[:10]}",
                experience_id=f"FUSE-{uuid.uuid4().hex[:8]}",
                source="lesson",
                action="goal_fuse",
                decision=(
                    f"【熔断机制】goal={description[:80]} "
                    f"连续失败 ≥3 次，暂停 propose"
                ),
                goal=description[:100],
                outcome={"success": True, "action": "fused", "reason": "consecutive_failures"},
                tags=["goal_fuse", "self_preservation"],
            )
            store.save(ep)
        except Exception as e:
            logger.debug("fuse episode record skipped: %s", e)

    def _domain_success_rate(self) -> float:
        """近 7 天 goal_result 平均成功率（OPPORTUNITY_COST 语义：可行
        性 = episode 派生成功率 × 效用，此处效用取 value 本身）。"""
        since = (datetime.now(timezone.utc)
                 - timedelta(days=LOOKBACK_DAYS)).isoformat()
        try:
            conn = _open_ro(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT outcome FROM episodes "
                    "WHERE source='goal_result' AND created_at >= ? "
                    "LIMIT 20", (since,)).fetchall()
            finally:
                conn.close()
            rates = []
            for r in rows:
                try:
                    oc = json.loads(r["outcome"] or "{}")
                    if isinstance(oc.get("task_success_rate"), (int, float)):
                        rates.append(float(oc["task_success_rate"]))
                except (ValueError, TypeError):
                    continue
            if not rates:
                return 0.5                      # 无数据 → 中性
            return round(sum(rates) / len(rates), 4)
        except sqlite3.Error:
            return 0.5


# typing.Any 延迟导入兼容（dataclass 字段注解在类体内使用 Any）
from typing import Any  # noqa: E402
