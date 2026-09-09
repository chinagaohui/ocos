"""L0-6: 生命体征仪表盘（vitals）— 从生产行为聚合，不接受自报告。

升级方案 v1.0 §3.1: 指标全部从 episodes/goals/pending_actions 现有表
聚合，不打断主流程。L0 先上 autonomy / redline 两组指标，其余体征
（skill_replay/failure_recurrence/... ）随 L1–L4 逐步填充（值置 None
并诚实标注 not_implemented，不装样子）。

用法:
    ocos vitals            # 一屏总览
    python - <<'EOF'
    from ocos.monitoring.vitals import compute_vitals
    print(compute_vitals("~/.ocos/ocos.db"))
    EOF
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _window_start(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone()
    return row is not None


def _autonomy_metrics(conn: sqlite3.Connection, window_start: str) -> dict:
    """V1 自主性（骨架）: 周窗内自主目标占比。

    自主目标判据（L3 MotivationHub 落地时统一打标）:
      metadata 含 "autonomous" 或 source='motivation'。
    """
    metrics = {"goals_total": 0, "goals_autonomous": 0,
               "autonomy_goal_ratio": 0.0}
    if not _table_exists(conn, "goals"):
        return metrics
    row = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE created_at >= ?",
        (window_start,)).fetchone()
    metrics["goals_total"] = int(row[0] or 0)
    row = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE created_at >= ? AND "
        "(metadata LIKE '%autonomous%' OR source = 'motivation')",
        (window_start,)).fetchone()
    metrics["goals_autonomous"] = int(row[0] or 0)
    if metrics["goals_total"] > 0:
        metrics["autonomy_goal_ratio"] = round(
            metrics["goals_autonomous"] / metrics["goals_total"], 4)
    return metrics


def _redline_metrics(conn: sqlite3.Connection, window_start: str) -> dict:
    """V8 安全缰绳（骨架）: 红线绕过次数（硬性 =0）+ 闸门拦截证据。

    redline_violation_count 只统计确证的绕过（episode tags 含
    redline_violation — 由审计链在确证绕过时打标）；
    blocked_attempts 为闸门成功拦截的伪造审批/越权尝试数（≥0，
    属于缰绳生效的正向证据）。
    """
    metrics = {"redline_violation_count": 0, "redline_blocked_attempts": 0}
    if not _table_exists(conn, "episodes"):
        return metrics
    row = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE created_at >= ? AND "
        "tags LIKE '%redline_violation%'",
        (window_start,)).fetchone()
    metrics["redline_violation_count"] = int(row[0] or 0)
    row = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE created_at >= ? AND "
        "(tags LIKE '%forged%' OR decision LIKE '%forged/unapproved approval_id%')",
        (window_start,)).fetchone()
    metrics["redline_blocked_attempts"] = int(row[0] or 0)
    return metrics


def _pending_metrics(conn: sqlite3.Connection) -> dict:
    metrics: dict[str, int] = {}
    if not _table_exists(conn, "pending_actions"):
        return metrics
    for status, n in conn.execute(
            "SELECT status, COUNT(*) FROM pending_actions "
            "GROUP BY status").fetchall():
        metrics[f"pending_{status}"] = int(n or 0)
    return metrics


def _proactive_metrics(conn: sqlite3.Connection, window_days: int) -> dict:
    """V1 主动汇报: 无指令主动推送次数/天（user_messages outbound）。

    口径: sender='ocos' AND status='outbound' — 仅 agent 主动发起
    （UX-J 目标结果回推 / L3 提案通知），用户消息回复不计入。
    """
    metrics = {"proactive_report_count": None}
    if not _table_exists(conn, "user_messages"):
        return metrics
    window_start = _window_start(window_days)
    row = conn.execute(
        "SELECT COUNT(*) FROM user_messages "
        "WHERE sender = 'ocos' AND status = 'outbound' AND created_at >= ?",
        (window_start,)).fetchone()
    if window_days > 0:
        metrics["proactive_report_count"] = round(
            int(row[0] or 0) / window_days, 2)
    return metrics


def _failure_recurrence(conn: sqlite3.Connection) -> dict:
    """V2/V4 同型失败复发率: 30 天窗内同 cause lesson 复现占比。

    口径: source='lesson' 的 episode 以首个非 failure_lesson tag 为
    cause（与 MotivationHub._from_lessons 同构）；同一 cause 在 30 天内
    产生 ≥2 条 lesson = 复发。复发 cause 数 / 总 cause 数即复发率。
    （lesson 只在失败后合成——同 cause 反复出现即"同型失败复发"。）
    """
    metrics = {"failure_recurrence_rate": None, "failure_cause_total": 0,
               "failure_cause_recurring": 0}
    if not _table_exists(conn, "episodes"):
        return metrics
    since = _window_start(30)
    rows = conn.execute(
        "SELECT tags FROM episodes WHERE source = 'lesson' "
        "AND created_at >= ?", (since,)).fetchall()
    by_cause: dict[str, int] = {}
    for (tags_raw,) in rows:
        try:
            tag_list = json.loads(tags_raw or "[]")
        except ValueError:
            tag_list = []
        for t in (tag_list if isinstance(tag_list, list) else []):
            if t and t != "failure_lesson":
                by_cause[str(t)] = by_cause.get(str(t), 0) + 1
                break
    metrics["failure_cause_total"] = len(by_cause)
    metrics["failure_cause_recurring"] = sum(
        1 for n in by_cause.values() if n >= 2)
    if by_cause:
        metrics["failure_recurrence_rate"] = round(
            metrics["failure_cause_recurring"] / len(by_cause), 4)
    return metrics


_INTERNAL_AGENT_NAMES = frozenset({
    "?", "executor", "llm", "agent", "master", "decision", "runtime",
})


def _learning_marks_path() -> Path:
    import os as _os
    base = _os.environ.get("OCOS_AUDIT_DIR", "").strip()
    return ((Path(base).expanduser() if base
             else Path.home() / ".ocos" / "audit") / "learning.jsonl")


def _read_learning_marks() -> list[dict]:
    """learning.jsonl 全量解析（L8/V6 观测数据源，坏行跳过）。"""
    path = _learning_marks_path()
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
        return []
    return out


def _learning_metrics(conn: sqlite3.Connection) -> dict:
    """V2 学习闭环观测（L7/L8）: lesson 先验消费 + 技能重放命中。

    数据源:
      - episodes: 30 天 lesson cause 注册表（先验可用性）
      - learning.jsonl（OCOS_AUDIT_DIR 可覆写，bridge/daemon 留痕）:
        lesson_prior_injected / skill_replay / skill_synthesized 计数
    skill_replay_hit_rate = 命中/触发（7 天窗）；无触发 = None（诚实——
    技能库为空时重放通道未激活）。
    """
    metrics: dict = {"lesson_priors_available": 0,
                     "lesson_prior_injections_7d": 0,
                     "skill_replay_triggers_7d": 0,
                     "skill_replay_matched_7d": 0,
                     "skill_replay_hit_rate": None,
                     "skills_synthesized_7d": 0}
    if _table_exists(conn, "episodes"):
        since = _window_start(30)
        rows = conn.execute(
            "SELECT tags FROM episodes WHERE source = 'lesson' "
            "AND created_at >= ?", (since,)).fetchall()
        causes: set = set()
        for (tags_raw,) in rows:
            try:
                tag_list = json.loads(tags_raw or "[]")
            except ValueError:
                tag_list = []
            for t in (tag_list if isinstance(tag_list, list) else []):
                if t and t != "failure_lesson":
                    causes.add(str(t))
                    break
        metrics["lesson_priors_available"] = len(causes)
    # learning.jsonl — 7 天窗计数
    cutoff = _window_start(7)
    inj = triggers = matched = synth = 0
    for e in _read_learning_marks():
        ts = str(e.get("ts", ""))
        if ts < cutoff:
            continue
        t = e.get("type")
        if t == "lesson_prior_injected":
            inj += 1
        elif t == "skill_replay":
            triggers += 1
            if e.get("matched"):
                matched += 1
        elif t == "skill_synthesized":
            synth += int(e.get("count", 1) or 1)
    metrics["lesson_prior_injections_7d"] = inj
    metrics["skill_replay_triggers_7d"] = triggers
    metrics["skill_replay_matched_7d"] = matched
    metrics["skills_synthesized_7d"] = synth
    if triggers:
        metrics["skill_replay_hit_rate"] = round(matched / triggers, 4)
    return metrics


def _self_evolution_metrics(conn: sqlite3.Connection) -> dict:
    """Phase B 纵向自进化量化 — 5 项指标（路线图 §B1）。

    指标定义:
      1. failure_rate_trend_delta — 近 7d vs 前 7d outcome.success 比例变化
         （正值 = 变好（success rate 上升）；负值 = 退化；None = 数据不足）
      2. tool_utilization_rate   — fs_read/shell/read_file/run_command
         类 action 中 outcome.success 占比（ER-2 C=6/10 指标借鉴）
      3. c_lesson_production_per_day — 7d 内 C 类 Lesson 日均产出
         （C 类判定 = source='lesson' 且 decision 含 '【'）
      4. lesson_injection_intensity — 近 30d lesson_prior_injected 次数 /
         近 30d source='lesson' episodes 数（可 > 1.0，高频注入）
      5. cross_task_lesson_delta — failure_rate_trend_delta > 0 且
         failure_recurrence_rate 下降 = 自进化生效信号

    所有指标独立容错：缺表/缺列只影响自身（诚实标注 None/0），
    其余继续聚合。不中断 compute_vitals 主流程。
    """
    metrics: dict = {
        "failure_rate_trend_delta": None,
        "recent_7d_success_rate": None,
        "prev_7d_success_rate": None,
        "tool_utilization_rate": None,
        "tool_action_total_30d": 0,
        "tool_action_success_30d": 0,
        "c_lesson_production_per_day": None,
        "c_lesson_count_7d": 0,
        "lesson_injection_intensity": None,
    }
    if not _table_exists(conn, "episodes"):
        return metrics

    _NOW = datetime.now(timezone.utc).isoformat()

    # ── 指标 1: 失败率趋势 ─────────────────────────────────────
    # 两个窗口:
    #   近 7d = [now-7d, now)
    #   前 7d = [now-14d, now-7d)
    prev_7d = _window_start(7)    # now - 7 days
    prev_14d = _window_start(14)  # now - 14 days
    try:
        rows = conn.execute(
            "SELECT outcome, created_at FROM episodes "
            "WHERE created_at >= ? AND source != 'lesson' ORDER BY created_at",
            (prev_14d,)).fetchall()
    except sqlite3.Error:
        rows = []
    def _count(rows_list, start, end):
        total = ok = 0
        for outcome_raw, created_at in rows_list:
            if not (start <= created_at < end):
                continue
            total += 1
            try:
                oc = json.loads(outcome_raw or "{}")
                if oc.get("success"):
                    ok += 1
            except (ValueError, TypeError):
                pass
        return ok, total
    now_ok, now_total = _count(rows, prev_7d, _NOW)
    prev_ok, prev_total = _count(rows, prev_14d, prev_7d)
    if now_total >= 5 and prev_total >= 5:
        metrics["recent_7d_success_rate"] = round(now_ok / now_total, 4)
        metrics["prev_7d_success_rate"] = round(prev_ok / prev_total, 4)
        metrics["failure_rate_trend_delta"] = round(
            metrics["recent_7d_success_rate"] - metrics["prev_7d_success_rate"], 4)

    # ── 指标 3: 工具利用率 ─────────────────────────────────────
    _TOOL_ACTIONS = frozenset({
        "fs_read", "shell", "read_file", "run_command",
        "write_file", "edit_file", "search_files", "bash",
    })
    cutoff_30d = _window_start(30)
    try:
        trows = conn.execute(
            "SELECT action, outcome FROM episodes WHERE created_at >= ?",
            (cutoff_30d,)).fetchall()
    except sqlite3.Error:
        trows = []
    t_total = t_success = 0
    for action_raw, outcome_raw in trows:
        act = action_raw or ""
        # action 可能存 JSON 或纯字符串
        try:
            ad = json.loads(act) if act.startswith("{") else act
            act_val = ad if isinstance(ad, str) else str(ad.get("action", ""))
        except (ValueError, AttributeError):
            act_val = act
        if act_val not in _TOOL_ACTIONS:
            continue
        t_total += 1
        try:
            oc = json.loads(outcome_raw or "{}")
            if oc.get("success"):
                t_success += 1
        except (ValueError, TypeError):
            pass
    metrics["tool_action_total_30d"] = t_total
    metrics["tool_action_success_30d"] = t_success
    if t_total >= 5:
        metrics["tool_utilization_rate"] = round(t_success / t_total, 4)

    # ── 指标 4: C 类 Lesson 产出率 ─────────────────────────────
    try:
        lesson_rows = conn.execute(
            "SELECT decision FROM episodes "
            "WHERE source = 'lesson' AND created_at >= ?",
            (prev_7d,)).fetchall()
    except sqlite3.Error:
        lesson_rows = []
    c_count = sum(1 for (desc,) in lesson_rows if desc and "【" in desc)
    metrics["c_lesson_count_7d"] = c_count
    if lesson_rows:
        metrics["c_lesson_production_per_day"] = round(c_count / 7.0, 2)

    # ── 指标 5: Lesson 注入强度 ──────────────────────────────────
    # injection_intensity = 30d lesson_prior_injected 次数 / 30d lesson 总数
    # 注意: 一条 Lesson 可被注入多次，此值可 > 1.0
    # 语义: ≥1.0 = Lesson 被频繁消费；越高 = C 类 procedure 被活跃复用
    try:
        total_lessons_30d = conn.execute(
            "SELECT COUNT(*) FROM episodes "
            "WHERE source = 'lesson' AND created_at >= ?",
            (cutoff_30d,)).fetchone()[0]
    except sqlite3.Error:
        total_lessons_30d = 0
    intensity: float | None = None
    if total_lessons_30d > 0:
        marks = _read_learning_marks()
        cutoff_reuse = _window_start(30)
        inj_30 = sum(1 for e in marks
                     if str(e.get("ts", "")) >= cutoff_reuse
                     and e.get("type") == "lesson_prior_injected")
        if inj_30 > 0:
            intensity = round(inj_30 / total_lessons_30d, 4)
    metrics["lesson_injection_intensity"] = intensity

    return metrics


def _attribution_metrics(conn: sqlite3.Connection) -> dict:
    """V4 失败归因质量: 归因覆盖率代理（方案定义为人工抽样评分）。

    代理口径（诚实标注）: 30 天 lesson 中 cause 非 unknown 的占比 ×
    平均 artifact 置信度。FailureDiagnoser 归因失败时以 UNKNOWN 兜底
    入库——覆盖率即"归因器有效分类的比例"。人工抽样评分流程建立后
    应替换本代理。
    """
    metrics = {"attribution_accuracy": None,
               "attribution_sample_total": 0}
    if not _table_exists(conn, "episodes"):
        return metrics
    since = _window_start(30)
    rows = conn.execute(
        "SELECT tags, outcome FROM episodes WHERE source = 'lesson' "
        "AND created_at >= ?", (since,)).fetchall()
    total = known = 0
    conf_sum = 0.0
    conf_n = 0
    for tags_raw, out_raw in rows:
        total += 1
        try:
            tag_list = json.loads(tags_raw or "[]")
        except ValueError:
            tag_list = []
        cause = next((t for t in (tag_list if isinstance(tag_list, list)
                                  else []) if t and t != "failure_lesson"),
                     None)
        if cause and cause != "unknown":
            known += 1
        try:
            outcome = json.loads(out_raw or "{}")
            c = outcome.get("confidence")
            if isinstance(c, (int, float)):
                conf_sum += float(c)
                conf_n += 1
        except ValueError:
            pass
    metrics["attribution_sample_total"] = total
    if total:
        coverage = known / total
        avg_conf = (conf_sum / conf_n) if conf_n else 0.6
        metrics["attribution_accuracy"] = round(coverage * avg_conf, 4)
    return metrics


def _reactivity_metrics(conn: sqlite3.Connection, window_days: int) -> dict:
    """V3 感知-反应: 无指令主动行为频度（探测/适应/汇报）。

    口径（7 天窗）: autonomous_goal_proposal episode（探测/适应类自
    主提案）+ proactive outbound user_messages（主动汇报）之和 / 天。
    感知事件入队率需感知观测持久化后接入（当前 sensor 观测不落库，
    诚实标注）。
    """
    metrics = {"reactivity_actions_per_day": None,
               "autonomous_proposals_7d": 0}
    days = window_days if window_days > 0 else 7
    if not _table_exists(conn, "episodes"):
        return metrics
    since = _window_start(days)
    try:
        prop = conn.execute(
            "SELECT COUNT(*) FROM episodes "
            "WHERE source = 'autonomous_goal_proposal' "
            "AND created_at >= ?", (since,)).fetchone()[0]
    except sqlite3.Error:
        prop = 0
    metrics["autonomous_proposals_7d"] = int(prop or 0)
    proactive = 0
    if _table_exists(conn, "user_messages"):
        try:
            proactive = conn.execute(
                "SELECT COUNT(*) FROM user_messages "
                "WHERE sender = 'ocos' AND status = 'outbound' "
                "AND created_at >= ?", (since,)).fetchone()[0]
        except sqlite3.Error:
            proactive = 0
    metrics["reactivity_actions_per_day"] = (
        int(prop or 0) + int(proactive or 0)) / days
    return metrics


def _social_metrics(conn: sqlite3.Connection) -> dict:
    """V6 社交性: 外部智能体调用成功率。

    口径（两层，执行时打点优先）:
      1) learning.jsonl type=external_agent_call — bridge 沙盒执行外部
         CLI（动态白名单命中）时的真实调用留痕，ok=执行真值；
      2) 回退: goal_result episodes context.agent 排除法（发现层名单，
         诚实近似 — goal_result 不携带执行者时此通道为 0）。
    """
    metrics = {"social_call_success_rate": None, "social_calls": 0}
    calls = [m for m in _read_learning_marks()
             if m.get("type") == "external_agent_call"]
    if calls:
        metrics["social_calls"] = len(calls)
        ok = sum(1 for m in calls if m.get("ok"))
        metrics["social_call_success_rate"] = round(ok / len(calls), 4)
        return metrics
    if not _table_exists(conn, "episodes"):
        return metrics
    rows = conn.execute(
        "SELECT context, outcome FROM episodes WHERE action = 'goal_result' "
        "ORDER BY created_at DESC LIMIT 500").fetchall()
    total = success = 0
    for ctx_raw, out_raw in rows:
        try:
            agent = (json.loads(ctx_raw) or {}).get("agent", "?")
            outcome = json.loads(out_raw) or {}
        except ValueError:
            continue
        if str(agent) in _INTERNAL_AGENT_NAMES:
            continue
        total += 1
        if bool(outcome.get("success", False)):
            success += 1
    metrics["social_calls"] = total
    if total:
        metrics["social_call_success_rate"] = round(success / total, 4)
    return metrics


def _perception_metrics(conn: sqlite3.Connection, window_start: str) -> dict:
    """V3 感知-反应（2026-09-07 感知层上电）: 刺激 → 行为响应链。

    口径（两层实测）:
      perception_events_24h        — perception.jsonl 触发事件数
                                     （StimulusScanner 冷却后真实触发）
      perception_goal_responses_7d — goals 表 metadata 含 perception
                                     标记的响应目标数（刺激→行为落地）
      perception_response_ratio    — 响应目标/触发事件（≤1 上限；
                                     >1 说明事件被多次响应，仍诚实记录）
    """
    metrics = {"perception_events_7d": 0, "perception_goal_responses_7d": 0,
               "perception_response_ratio": None}
    import os as _os
    base = _os.environ.get("OCOS_AUDIT_DIR", "").strip()
    path = ((Path(base).expanduser() if base
             else Path.home() / ".ocos" / "audit") / "perception.jsonl")
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                marks = []
                for line in f:
                    try:
                        d = json.loads(line)
                        if str(d.get("ts", "")) >= window_start:
                            marks.append(d)
                    except ValueError:
                        continue
            metrics["perception_events_7d"] = len(marks)
        except OSError:
            pass
    if _table_exists(conn, "goals"):
        row = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE created_at >= ? AND "
            "metadata LIKE '%perception%'",
            (window_start,)).fetchone()
        metrics["perception_goal_responses_7d"] = int(row[0] or 0)
        if metrics["perception_events_7d"]:
            metrics["perception_response_ratio"] = round(
                min(1.0, metrics["perception_goal_responses_7d"]
                    / metrics["perception_events_7d"]), 4)
    return metrics


def _reflection_metrics(conn: sqlite3.Connection, window_start: str) -> dict:
    """V2 行为级验收（2026-09-07）: REPAIR 复盘 → 可观测变更采纳率。

    数据源: learning.jsonl repair_verified 打点（MotivationHub.
    verify_repairs 在 REPAIR 完成 6h 后写，核对:
      adopted_behavior      — 同 cause 先验被真实注入执行
      adopted_no_recurrence — 验收窗内同 cause 无复发
      not_adopted           — 同 cause 复发（复盘未被消费，如实记）
    reflection_adoption_rate = adopted/(adopted+not_adopted)，行为级
    真值——非文本自评。
    """
    metrics = {"repair_verifications_7d": 0, "reflection_adoption_rate": None}
    base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
    path = ((Path(base).expanduser() if base
             else Path.home() / ".ocos" / "audit") / "learning.jsonl")
    if not path.exists():
        return metrics
    adopted = not_adopted = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if (m.get("type") == "repair_verified"
                        and str(m.get("ts", "")) >= window_start):
                    metrics["repair_verifications_7d"] += 1
                    if str(m.get("status", "")).startswith("adopted"):
                        adopted += 1
                    elif m.get("status") == "not_adopted":
                        not_adopted += 1
    except OSError:
        pass
    if adopted + not_adopted:
        metrics["reflection_adoption_rate"] = round(
            adopted / (adopted + not_adopted), 4)
    return metrics


def _identity_drift_metrics(conn: sqlite3.Connection,
                            window_start: str) -> dict:
    """V5 连续性: L4-3 continuity 校验的漂移计数（周窗，达标 =0）。"""
    metrics = {"identity_drift": None, "continuity_checks": 0}
    if not _table_exists(conn, "episodes"):
        return metrics
    row = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source = 'continuity_check' "
        "AND created_at >= ?", (window_start,)).fetchone()
    metrics["continuity_checks"] = int(row[0] or 0)
    row = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source = 'continuity_check' "
        "AND created_at >= ? AND outcome LIKE '%\"drift\": true%'",
        (window_start,)).fetchone()
    metrics["identity_drift"] = int(row[0] or 0)
    return metrics


def _homeostasis_metrics(conn: sqlite3.Connection, window_start: str) -> dict:
    """V7 自维护（L2-1 点亮）: 四层断言式自检结果聚合。

    数据源 = daemon 自检 episode（source='health_check', tags 含
    l2_self_check），不接受自报告。缺自检记录时诚实返回 None。
    """
    metrics: dict = {"homeostasis_check_passed": None,
                     "homeostasis_last_check_age_sec": None,
                     "homeostasis_check_failures_7d": None,
                     "causal_chain_completeness": None}
    if not _table_exists(conn, "episodes"):
        return metrics
    row = conn.execute(
        "SELECT created_at, outcome FROM episodes "
        "WHERE tags LIKE '%l2_self_check%' "
        "ORDER BY created_at DESC LIMIT 1").fetchone()
    if row is not None:
        created_at, outcome_json = row
        try:
            outcome = json.loads(outcome_json or "{}")
            metrics["homeostasis_check_passed"] = bool(outcome.get("success"))
            chain = outcome.get("causal_chain_completeness")
            if isinstance(chain, (int, float)):
                metrics["causal_chain_completeness"] = round(chain, 4)
        except ValueError:
            metrics["homeostasis_check_passed"] = False
        try:
            ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            metrics["homeostasis_last_check_age_sec"] = int(
                (datetime.now(timezone.utc) - ts).total_seconds())
        except ValueError:
            pass
    row = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE created_at >= ? AND "
        "tags LIKE '%l2_self_check%' AND outcome LIKE '%\"success\": false%'",
        (window_start,)).fetchone()
    metrics["homeostasis_check_failures_7d"] = int(row[0] or 0)
    return metrics


def _daemon_metrics() -> dict:
    """心跳判活 + 制动/级别快照（L0-3/L0-5 心跳字段）。"""
    hb_path = Path(os.environ.get(
        "OCOS_HEARTBEAT_PATH",
        str(Path.home() / ".ocos" / "daemon_heartbeat.json")))
    out = {"daemon_alive": False, "daemon_braked": None,
           "autonomy_level": None, "heartbeat_age_sec": None,
           "autonomy_level_changes_7d": None}
    try:
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data["ts"])
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        out["heartbeat_age_sec"] = int(age)
        # 60s 无心跳视为不存活（心跳每 5 tick ≈ 25s 刷新）
        out["daemon_alive"] = age < 60
        out["daemon_braked"] = bool(data.get("braked", False))
        out["autonomy_level"] = data.get("autonomy_level")
    except Exception:
        return out
    try:
        from ocos.execution.autonomy import audit_log_path
        audit = audit_log_path()
    except Exception:
        audit = Path.home() / ".ocos" / "audit" / "autonomy.jsonl"
    changes = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        for line in audit.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(rec.get("ts", ""))
                if (rec.get("kind") == "level_change"
                        and ts >= cutoff):
                    changes += 1
            except Exception:
                continue
    except OSError:
        return out
    out["autonomy_level_changes_7d"] = changes
    return out


def compute_vitals(db_path: str, window_days: int = 7) -> dict:
    """聚合生命体征快照。缺表/缺文件返回零值并带 source 说明 — 诚实降级。"""
    path = Path(db_path).expanduser()
    window_start = _window_start(window_days)
    vitals: dict = {
        "db_path": str(path),
        "window_days": window_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "missing": [],
        # 零值默认 — 缺库/缺表时诚实降级（键始终存在，值归零）
        "goals_total": 0, "goals_autonomous": 0, "autonomy_goal_ratio": 0.0,
        "redline_violation_count": 0, "redline_blocked_attempts": 0,
    }
    if not path.exists():
        vitals["missing"].append(f"db:{path}")
        conn = None
    else:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    if conn is not None:
        # 每个聚合器独立容错：单个指标缺列/缺表只影响自身（诚实标注
        # missing），不再中断其余指标聚合（§3.1 各体征独立点亮）
        for name, fn, arg in (
                ("autonomy", _autonomy_metrics, window_start),
                ("proactive", _proactive_metrics, window_days),
                ("failure_recurrence", _failure_recurrence, None),
                ("learning", _learning_metrics, None),
                ("self_evolution", _self_evolution_metrics, None),
                ("attribution", _attribution_metrics, None),
                ("reactivity", _reactivity_metrics, window_days),
                ("social", _social_metrics, None),
                ("perception", _perception_metrics, window_start),
                ("identity_drift", _identity_drift_metrics, window_start),
                ("redline", _redline_metrics, window_start),
                ("pending", _pending_metrics, None),
                ("homeostasis", _homeostasis_metrics, window_start),
                ("reflection", _reflection_metrics, window_start)):
            try:
                vitals.update(fn(conn, arg) if arg is not None
                              else fn(conn))
            except sqlite3.Error as e:
                vitals["missing"].append(f"{name}:{e}")
        conn.close()
    vitals.update(_daemon_metrics())
    # 不可自动聚合指标 — 诚实标注（不装样子）:
    #   unattended_survival     — 第三层长程协议（24h 实测）产出
    # 已点亮（2026-09-07 L7/L8）:
    #   skill_replay_hit_rate   — learning.jsonl 命中/触发（技能库空时 None）
    #   attribution_accuracy    — 覆盖率×置信度代理（人工抽样待建立，见
    #                             _attribution_metrics docstring）
    # 已点亮（2026-09-07 V2 行为级验收）:
    #   reflection_adoption_rate — repair_verified 打点聚合（REPAIR 目标
    #                             完成 6h 后核对复发/先验注入，非文本自评）
    not_implemented = ("unattended_survival",)
    for k in not_implemented:
        vitals[k] = None
    vitals["not_implemented"] = list(not_implemented)
    return vitals


# ── §3.4 验收 Gate: 阶段阈值判定（ocos vitals --check / make vitals-check） ──

_HARD_METRICS = ("redline_violation_count", "identity_drift")


def check_thresholds(v: dict, phase: str = "L4") -> list[str]:
    """按方案 §3.1 达标线判定，返回违规描述列表（空 = 通过）。

    阶段语义（里程碑表）:
      L0 — 红线硬性项；L1 — 无自动聚合新阈值；L2 — V7 自检闭环；
      L3 — V1 比例 + 主动汇报；L4 — V5 漂移 =0（含于硬性项）。
    硬性项（红线 =0 / 漂移 =0）任何阶段都检查。None = 数据未点亮，
    不算失败也不算通过（诚实——不算违规，但列入提示）。
    """
    failures: list[str] = []
    pending: list[str] = []
    if v.get("redline_violation_count", 0):
        failures.append(f"redline_violation_count={v['redline_violation_count']} (硬性 =0)")
    drift = v.get("identity_drift")
    if drift is None:
        pending.append("identity_drift 未点亮（无 continuity 校验记录）")
    elif drift:
        failures.append(f"identity_drift={drift} (硬性 =0)")

    checks: list[tuple[str, object, str]] = []
    if phase in ("L2", "L3", "L4"):
        passed = v.get("homeostasis_check_passed")
        if passed is None:
            pending.append("V7 自检未点亮（daemon 上电后生成）")
        elif not passed:
            failures.append("V7 自检存在失败项")
    if phase in ("L3", "L4"):
        lvl = v.get("autonomy_level")
        if lvl is not None and lvl >= 2:
            ratio = v.get("autonomy_goal_ratio")
            if ratio is not None and ratio < 0.3:
                failures.append(
                    f"autonomy_goal_ratio={ratio:.2%} < 30% (LEVEL>=2)")
        proactive = v.get("proactive_report_count")
        if proactive is not None and proactive < 1:
            failures.append(f"proactive_report_count={proactive}/天 < 1")
    if phase in ("终验", "long_run"):
        # 终验门禁（方案 §3.1 里程碑表 V2/V4 行）— 仅长程协议阶段判定
        srr = v.get("skill_replay_hit_rate")
        if srr is not None and srr < 0.5:
            failures.append(f"skill_replay_hit_rate={srr:.1%} < 50% (终验)")
        att = v.get("attribution_accuracy")
        if att is not None and att < 0.7:
            failures.append(f"attribution_accuracy={att:.1%} < 70% (终验)")
        recur = v.get("failure_recurrence_rate")
        if recur is not None and recur > 0.2:
            failures.append(f"failure_recurrence_rate={recur:.1%} > 20% (终验)")
    for name, val, line in checks:
        if val is not None and val < line:
            failures.append(f"{name}={val} < {line}")
    if pending:
        failures.extend(f"[未点亮] {p}" for p in pending)
    return failures


def render_vitals(v: dict) -> str:
    """一屏渲染（CLI 输出）。"""
    lines = ["OCOS 生命体征仪表盘 "
             f"(窗口 {v.get('window_days', 7)} 天, @ {v.get('generated_at', '?')[:19]}Z)"]
    if v.get("missing"):
        lines.append(f"  ⚠ 缺失数据源: {', '.join(v['missing'])}")
    lines.append("─" * 56)
    lines.append("[V1 自主性]")
    lines.append(f"  autonomy_goal_ratio : {v.get('autonomy_goal_ratio', 0):.1%} "
                 f"({v.get('goals_autonomous', 0)}/{v.get('goals_total', 0)} 自主/总目标, 达标线 30%)")
    pro = v.get("proactive_report_count")
    lines.append(f"  proactive_report    : {pro if pro is not None else '未点亮'} /天 (达标线 ≥1)")
    lvl = v.get("autonomy_level")
    braked = v.get("daemon_braked")
    lines.append(f"  autonomy_level      : {lvl if lvl is not None else '?'}"
                 + ("  [BRAKED 制动中]" if braked else ""))
    lines.append("[V2/V4 成长·元认知]")
    fr = v.get("failure_recurrence_rate")
    if fr is None:
        lines.append("  failure_recurrence  : 未点亮（30 天内无 lesson 数据）")
    else:
        lines.append(f"  failure_recurrence  : {fr:.1%} "
                     f"({v.get('failure_cause_recurring', 0)}/{v.get('failure_cause_total', 0)} 复发/总 cause, 达标线 ≤20%)")
    lines.append(f"  lesson_priors       : {v.get('lesson_priors_available', 0)} cause 可用, "
                 f"7d 注入 {v.get('lesson_prior_injections_7d', 0)} 次 (L7 先验消费)")
    srr = v.get("skill_replay_hit_rate")
    if srr is None:
        lines.append(f"  skill_replay        : 未触发 (7d 触发 {v.get('skill_replay_triggers_7d', 0)}, "
                     f"合成技能 {v.get('skills_synthesized_7d', 0)})")
    else:
        lines.append(f"  skill_replay        : {srr:.1%} "
                     f"({v.get('skill_replay_matched_7d', 0)}/{v.get('skill_replay_triggers_7d', 0)} 命中/触发, 达标线 ≥50%)")
    att = v.get("attribution_accuracy")
    if att is None:
        lines.append("  attribution         : 未点亮（30 天内无 lesson 数据）")
    else:
        lines.append(f"  attribution         : {att:.1%} (归因覆盖率×置信度代理, 达标线 ≥70%)")
    # ── Phase B 自进化纵向量化 ─────────────────────────────────
    frd = v.get("failure_rate_trend_delta")
    r7 = v.get("recent_7d_success_rate")
    p7 = v.get("prev_7d_success_rate")
    if frd is None:
        lines.append("  self_evolve_failure : 未点亮（近 14d episodes < 5 条）")
    else:
        trend_sym = "↓ 变好" if frd < 0 else ("↑ 退化" if frd > 0 else "→ 持平")
        lines.append(f"  self_evolve_failure : {(1 - r7):.1%} ← 近 7d 失败率 "
                     f"({frd:+.1%} {trend_sym})")
    tu = v.get("tool_utilization_rate")
    if tu is None:
        lines.append(f"  self_evolve_tool    : 未点亮（30d 工具类 action < 5 条, "
                     f"当前 {v.get('tool_action_total_30d', 0)} 条）")
    else:
        lines.append(f"  self_evolve_tool    : {tu:.1%} "
                     f"({v.get('tool_action_success_30d', 0)}/"
                     f"{v.get('tool_action_total_30d', 0)} success/tool, "
                     f"达标线 ≥70%)")
    clp = v.get("c_lesson_production_per_day")
    clc = v.get("c_lesson_count_7d", 0)
    if clp is None:
        lines.append(f"  self_evolve_c_lesson: 未点亮（7d lesson < 1 条, "
                     f"C 类产出 {clc} 条）")
    else:
        lines.append(f"  self_evolve_c_lesson: {clp:.2f}/天 C 类产出 "
                     f"({clc}/7d, 达标线 ≥0.5/天)")
    li = v.get("lesson_injection_intensity")
    if li is None:
        lines.append("  self_evolve_inject  : 未点亮（30d lesson 总数 = 0）")
    else:
        # 可 > 1.0（一条 Lesson 被注入多次），用整数×格式
        lines.append(f"  self_evolve_inject  : {li:.2f}× "
                     f"(30d 注入 / 30d lessons, ≥1× = 高频复用)")
    lines.append("[V3 感知-反应]")
    rea = v.get("reactivity_actions_per_day")
    if rea is None:
        lines.append("  reactivity          : 未点亮（无 episodes 数据）")
    else:
        lines.append(f"  reactivity          : {rea:.1f}/天 无指令主动行为 "
                     f"(自主提案 {v.get('autonomous_proposals_7d', 0)}/7d)")
    lines.append("[V5 连续性]")
    drift = v.get("identity_drift")
    if drift is None:
        lines.append("  identity_drift      : 未点亮（无 continuity 校验记录）")
    else:
        marks = "✗ 漂移!" if drift else "✓ 达标(=0)"
        lines.append(f"  identity_drift      : {drift} {marks} "
                     f"(近窗 continuity 校验 {v.get('continuity_checks', 0)} 次)")
    lines.append("[V6 社交性]")
    sc = v.get("social_call_success_rate")
    if sc is None:
        lines.append(f"  social_call_success : 无外部智能体调用记录 (calls={v.get('social_calls', 0)})")
    else:
        lines.append(f"  social_call_success : {sc:.1%} ({v.get('social_calls', 0)} 次调用, 达标线 80%)")
    lines.append("[V8 安全缰绳]")
    viol = v.get("redline_violation_count", 0)
    lines.append(f"  redline_violation   : {viol} "
                 f"{'✗ 违规!' if viol else '✓ 硬性达标(=0)'}")
    lines.append(f"  redline_blocked     : {v.get('redline_blocked_attempts', 0)} 次拦截（缰绳生效证据）")
    lines.append("[V7 自维护]")
    passed = v.get("homeostasis_check_passed")
    if passed is None:
        lines.append("  self_check          : 尚无自检记录（daemon 上电后生成）")
    else:
        age = v.get("homeostasis_last_check_age_sec")
        lines.append(f"  self_check          : {'✓ 通过' if passed else '✗ 存在失败项'}"
                     f" (最近 {age}s 前)" if age is not None else
                     f"  self_check          : {'✓ 通过' if passed else '✗ 存在失败项'}")
        fails = v.get("homeostasis_check_failures_7d")
        lines.append(f"  check_failures_7d   : {fails}")
        chain = v.get("causal_chain_completeness")
        if chain is not None:
            lines.append(f"  causal_chain        : {chain:.2f} (达标线 0.90)")
    lines.append("[daemon]")
    alive = v.get("daemon_alive")
    age = v.get("heartbeat_age_sec")
    lines.append(f"  daemon_alive        : {alive} (heartbeat {age}s ago)"
                 if age is not None else "  daemon_alive        : False (无心跳)")
    pend = {k: v[k] for k in v if k.startswith("pending_")}
    if pend:
        lines.append(f"  pending_actions     : {pend}")
    ni = v.get("not_implemented") or []
    if ni:
        lines.append("[后续阶段点亮]")
        lines.append(f"  待实现指标: {', '.join(ni)}")
    return "\n".join(lines)
