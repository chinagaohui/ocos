"""L4-2 (升级方案 v1.0): AgentSelfModel — 自我模型（agent_self_model 表）。

"我是谁"的实测画像，全部由真实数据统计（无自报指标）:
    - 能力清单: goal_result episodes 按 agent 分组的实测成功率
      + 装配层传入的 capability registry 能力名（无实测 → attempts=0）
    - 性格参数: 对话历史聚合 — 回复均长 → 响应风格;
      待批 approved/denied 比例 → 风险偏好（诚实: 无数据="未知"）
    - 当前专注: goals 表 ACTIVE 目标 top3

生命周期: boot 加载（daemon start 时 load）→ 每 N tick 校准
（daemon tick 挂载 calibrate）→ LLM prompt 注入（render → "我是谁"块）。

content_hash = 画像内容 sha256 — 供 L4-3 跨重启一致性校验（V5 身份参数）。

层级约束: 本模块只依赖 sqlite3/hashlib 标准库 — memory 层禁入 ocos.self
（test_phase24_isolation），interaction/daemon 导入本模块合法
（禁运清单只含 ocos.self.self_model / ocos.self.monitor）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS agent_self_model (
    id            INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行最新画像
    version       INTEGER NOT NULL,                    -- 校准次数（只增）
    capabilities  TEXT NOT NULL DEFAULT '[]',          -- JSON [{name,attempts,success_rate}]
    personality   TEXT NOT NULL DEFAULT '{}',          -- JSON {reply_style,risk_preference,...}
    focus         TEXT NOT NULL DEFAULT '[]',          -- JSON [当前专注目标]
    content_hash  TEXT NOT NULL DEFAULT '',            -- 画像内容 sha256（V5 校验用）
    calibrated_at TEXT NOT NULL
)
"""

_REPLY_STYLE_SHORT = 200   # 平均回复 <200 字符 = 简洁风格
_FOCUS_LIMIT = 3
_FAILURE_MODES_LIMIT = 4
_BRIEF_MAX = 120


class AgentSelfModel:
    """agent_self_model 表的读写与校准（SQLite，同库共生存）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute(_DDL)
        # COG-V2: 旧库（无 failure_modes 列）幂等迁移 — 仅加列不改数据。
        try:
            conn.execute(
                "ALTER TABLE agent_self_model ADD COLUMN failure_modes "
                "TEXT NOT NULL DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # 列已存在
        return conn

    # ── boot 加载 ─────────────────────────────────────────────────────

    def load(self) -> dict | None:
        """加载最新画像快照（boot 时调用）。未校准过 → None（诚实）。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT version, capabilities, personality, focus, "
                "failure_modes, content_hash, calibrated_at "
                "FROM agent_self_model WHERE id = 1").fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        cols = list(row)
        return {"version": int(cols[0]),
                "capabilities": json.loads(cols[1]),
                "personality": json.loads(cols[2]),
                "focus": json.loads(cols[3]),
                "failure_modes": json.loads(cols[4]) if cols[4] else [],
                "content_hash": cols[5],
                "calibrated_at": cols[6]}

    # ── tick 校准 ─────────────────────────────────────────────────────

    def calibrate(self, capability_names: list[str] | None = None) -> dict:
        """重新统计画像并落库（daemon 每 N tick 调用）。

        capability_names: 装配层从 capability registry 传入的能力名
        （与 episode 实测统计合并；缺省只统计实测）。
        """
        capabilities = self._stat_capabilities(capability_names)
        personality = self._stat_personality()
        focus = self._stat_focus()
        failure_modes = self._stat_failure_modes()
        content_hash = self._content_hash(
            capabilities, personality, focus, failure_modes)

        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT version FROM agent_self_model WHERE id = 1").fetchone()
            version = (int(row[0]) + 1) if row else 1
            conn.execute(
                "INSERT OR REPLACE INTO agent_self_model "
                "(id, version, capabilities, personality, focus, "
                " failure_modes, content_hash, calibrated_at) "
                "VALUES (1,?,?,?,?,?,?,?)",
                (version, json.dumps(capabilities, ensure_ascii=False),
                 json.dumps(personality, ensure_ascii=False),
                 json.dumps(focus, ensure_ascii=False),
                 json.dumps(failure_modes, ensure_ascii=False),
                 content_hash,
                 datetime.now(timezone.utc).isoformat()))
            conn.commit()
        finally:
            conn.close()
        logger.info("SelfModel calibrated v%d (%d capabilities, %d failure modes)",
                    version, len(capabilities), len(failure_modes))
        snapshot = self.load() or {}
        # P1 恢复性迁移（2026-09-14）：calibrate 是 S1 实测证据的唯一生产发射
        # 点（goal_result 闭合 + daemon 每 50 tick 两处都收口于此）。校准落库
        # 后同 tick 确定性喂 S2（零 LLM；进程注册表保证喂的是 runtime boot 的
        # 同一 manager；内容无变化时管线语义 noop；失败只 debug，绝不阻断校准）。
        # lazy import：保持本模块顶层只依赖标准库，且避开同包导入环。
        try:
            from ocos.self.self_state import get_or_boot_self_manager
            from ocos.self.s2_feeder import feed_s1_snapshot
            manager = get_or_boot_self_manager(self._db_path)
            if manager is not None:
                feed_s1_snapshot(manager, snapshot)
        except Exception as e:  # noqa: BLE001
            logger.debug("S2 feed after calibrate skipped: %s", e)
        return snapshot

    def _stat_capabilities(self, capability_names: list[str] | None) -> list[dict]:
        """实测统计: goal_result episodes 按 context.agent 分组成功率。

        P2 (2026-09-08 事件复盘): 此前 goal_result 的 context 无 agent 键
        → 全部归到 "?"（354 条 0.364 的来源）；且 bridge 的 shell/filesystem
        实测从不出现在统计里（registry 能力名永远 attempts=0）。现在:
        - context.agent → agent 级实测
        - context.capabilities [{name, success}] → 能力级实测（shell/
          filesystem 由 bridge RUN/FILE_WRITE 打标）
        """
        stats: dict[str, dict] = {}
        try:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT context, outcome FROM episodes "
                    "WHERE action = 'goal_result'").fetchall()
            finally:
                conn.close()
            for ctx_raw, out_raw in rows:
                try:
                    ctx = json.loads(ctx_raw) or {}
                    agent = ctx.get("agent", "?")
                    outcome = json.loads(out_raw) or {}
                    success = bool(outcome.get("success", False))
                except Exception:  # noqa: BLE001 — 脏行跳过
                    continue
                s = stats.setdefault(agent, {"name": str(agent),
                                             "attempts": 0, "successes": 0})
                s["attempts"] += 1
                if success:
                    s["successes"] += 1
                for cap in (ctx.get("capabilities") or []):
                    if isinstance(cap, dict):
                        cname = str(cap.get("name", ""))
                        cok = bool(cap.get("success", False))
                    else:  # 兼容旧格式（裸字符串 → 按聚合 success 计）
                        cname, cok = str(cap), success
                    if not cname:
                        continue
                    c = stats.setdefault(cname, {"name": cname,
                                                 "attempts": 0, "successes": 0})
                    c["attempts"] += 1
                    if cok:
                        c["successes"] += 1
        except Exception as e:  # noqa: BLE001 — 无 episodes 表时诚实为空
            logger.debug("self-model capability stats skipped: %s", e)
        for s in stats.values():
            s["success_rate"] = (round(s["successes"] / s["attempts"], 3)
                                 if s["attempts"] else 0.0)

        out = list(stats.values())
        if capability_names:
            seen = {s["name"] for s in out}
            out.extend({"name": n, "attempts": 0, "successes": 0,
                        "success_rate": None}
                       for n in capability_names if n not in seen)
        out.sort(key=lambda s: (-s["attempts"], s["name"]))
        return out

    def _stat_personality(self) -> dict:
        """对话历史聚合: 响应风格（回复均长）+ 风险偏好（审批比例）。"""
        out: dict = {"reply_style": "未知", "risk_preference": "未知"}
        try:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*), AVG(LENGTH(reply)) FROM user_messages "
                    "WHERE reply IS NOT NULL AND reply != ''").fetchone()
            finally:
                conn.close()
            reply_count, avg_len = int(row[0] or 0), row[1]
            if reply_count and avg_len is not None:
                out["reply_count"] = reply_count
                out["avg_reply_len"] = round(float(avg_len), 1)
                out["reply_style"] = ("简洁" if avg_len < _REPLY_STYLE_SHORT
                                      else "详细")
        except Exception as e:  # noqa: BLE001
            logger.debug("self-model reply stats skipped: %s", e)
        try:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT status, COUNT(*) FROM pending_actions "
                    "WHERE status IN ('approved', 'denied') "
                    "GROUP BY status").fetchall()
            finally:
                conn.close()
            counts = {r[0]: int(r[1]) for r in rows}
            approved, denied = counts.get("approved", 0), counts.get("denied", 0)
            if approved + denied:
                out["approvals"] = {"approved": approved, "denied": denied}
                if denied == 0:
                    out["risk_preference"] = "偏信任"
                elif denied > approved:
                    out["risk_preference"] = "偏谨慎"
                else:
                    out["risk_preference"] = "均衡"
        except Exception as e:  # noqa: BLE001
            logger.debug("self-model risk stats skipped: %s", e)
        return out

    def _stat_focus(self) -> list[str]:
        """当前专注: ACTIVE 目标 top3（按优先级）。"""
        try:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT description FROM goals "
                    "WHERE status = 'ACTIVE' "
                    "ORDER BY priority DESC LIMIT ?",
                    (_FOCUS_LIMIT,)).fetchall()
            finally:
                conn.close()
            return [str(r[0])[:50] for r in rows if r[0]]
        except Exception as e:  # noqa: BLE001
            logger.debug("self-model focus stats skipped: %s", e)
            return []

    def _stat_failure_modes(self) -> list[dict]:
        """COG-V2 L2 失败模式：近 7 天 failure_lesson 按 cause 聚合。

        从 episodes 表 failure_lesson 的 tags 提取 cause，只保留
        出现 ≥2 次的反复模式（单次失败是噪声，不值得进自我画像）。
        输出 [{cause, count, last_at}]，按 count 降序。
        """
        try:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT tags, created_at FROM episodes "
                    "WHERE action='failure_lesson' "
                    "AND created_at >= datetime('now', '-7 days')"
                ).fetchall()
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            logger.debug("self-model failure stats skipped: %s", e)
            return []

        rec: dict[str, dict] = {}
        for tags_raw, last_at in rows:
            try:
                tags = json.loads(tags_raw or "[]")
            except Exception:
                tags = []
            for t in tags:
                if not isinstance(t, str):
                    continue
                # 排除工具名/噪声标签，只取已知 cause 类
                if t in {"sql_schema_mismatch", "dependency_missing",
                         "tool_unavailable", "permission_denied",
                         "execution_error", "timeout"}:
                    r = rec.setdefault(t, {"cause": t, "count": 0,
                                           "last_at": last_at})
                    r["count"] += 1
                    r["last_at"] = last_at
        out = [r for r in rec.values() if r["count"] >= 2]
        out.sort(key=lambda r: -r["count"])
        return out[:_FAILURE_MODES_LIMIT]

    # ── V5: 画像内容 hash（跨重启一致性输入） ──────────────────────────

    @staticmethod
    def _content_hash(capabilities: list, personality: dict,
                      focus: list, failure_modes: list | None = None) -> str:
        payload = json.dumps({"capabilities": capabilities,
                              "personality": personality,
                              "focus": focus,
                              "failure_modes": failure_modes or []},
                             ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ── prompt 注入 ───────────────────────────────────────────────────

    def render(self, snapshot: dict | None = None) -> str:
        """【自我模型】块 — "我是谁"注入对话/决策上下文。"""
        snap = snapshot if snapshot is not None else self.load()
        if not snap:
            return "自我模型: 尚未校准（无实测画像）"
        caps = snap.get("capabilities", [])
        pers = snap.get("personality", {})
        focus = snap.get("focus", [])
        cap_s = "; ".join(
            f"{c['name']}(实测{c['attempts']}次,成功率"
            f"{c['success_rate'] if c.get('success_rate') is not None else '无'})"
            for c in caps[:6]) or "无"
        lines = [
            f"自我模型（v{snap['version']}, 校准于 {snap['calibrated_at'][:19]}）:",
            f"  能力实测: {cap_s}",
            f"  响应风格: {pers.get('reply_style', '未知')}, "
            f"风险偏好: {pers.get('risk_preference', '未知')}",
            f"  当前专注: {'; '.join(focus) if focus else '无'}",
        ]
        fms = snap.get("failure_modes") or []
        if fms:
            fm_s = ", ".join(
                f"{m['cause']}×{m['count']}" for m in fms)
            lines.append(f"  反复失败模式: {fm_s}")
        return "\n".join(lines)

    def render_brief(self, snapshot: dict | None = None) -> str:
        """COG-V2: 全局工作空间 [self] 条目（≤120 字），决策前必读。

        只给高 n（≥3 次）能力 + 反复失败模式 + 当前专注，避免把零样本
        能力（uncertain）灌进 prompt 误导 LLM。
        """
        snap = snapshot if snapshot is not None else self.load()
        if not snap:
            return ""
        caps = snap.get("capabilities") or []
        parts: list[str] = []
        # 只取有 ≥3 次实测的能力，避免小样本自信
        known = [c for c in caps
                 if isinstance(c.get("attempts"), int) and c["attempts"] >= 3]
        if known:
            top = known[:3]
            parts.append("能力：" + "；".join(
                f"{c['name']}成功率{c.get('success_rate', 0):.0%}"
                for c in top))
        fms = snap.get("failure_modes") or []
        if fms:
            parts.append("近期反复失败：" + "/".join(
                m["cause"] for m in fms[:2]))
        focus = snap.get("focus") or []
        if focus:
            parts.append("当前专注：" + focus[0][:30])
        brief = " | ".join(parts)
        if len(brief) > _BRIEF_MAX:
            brief = brief[:_BRIEF_MAX - 1] + "…"
        return brief
