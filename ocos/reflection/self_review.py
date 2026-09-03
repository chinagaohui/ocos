"""ocos self review — 自省分析器 (Phase 52).

从自身记忆/执行历史采集证据 → LLM 综合分析不足与升级方向 → 报告落盘。

流程 (只读 + LLM, 无任何变异):
    1. collect(): 多维只读证据 (episodes 失败模式/goal/belief/事件流/growth)
    2. analyze(): LLM 综合证据 → 不足清单 + 升级优先级
    3. report: Markdown 报告落盘 docs/self_review/  + 控制台摘要

治理: 纯只读采集 (mode=ro sqlite), LLM 仅文本分析, 不触任何写入路径。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReviewEvidence:
    """自省证据快照。"""

    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    episodes_total: int = 0
    episodes_success: int = 0
    episodes_failed: int = 0
    failure_patterns: list[dict] = field(default_factory=list)   # {pattern, count, sample}
    goals_by_status: dict[str, int] = field(default_factory=dict)
    recent_goal_ok: int = 0
    recent_goal_failed: int = 0
    beliefs_total: int = 0
    beliefs_domains: list[dict] = field(default_factory=list)    # {domain, count}
    events_last_day: int = 0
    events_result_fail: int = 0
    dlq_count: int = 0
    growth_signals: int = 0
    growth_applied: int = 0
    llm_blocked_patterns: list[dict] = field(default_factory=list)
    recent_episodes: list[dict] = field(default_factory=list)    # {goal, decision, outcome}
    working_memory_items: int = 0

    def to_dict(self) -> dict:
        return {
            "collected_at": self.collected_at,
            "episodes_total": self.episodes_total,
            "episodes_success": self.episodes_success,
            "episodes_failed": self.episodes_failed,
            "failure_patterns": self.failure_patterns[:8],
            "goals_by_status": self.goals_by_status,
            "recent_goal_ok": self.recent_goal_ok,
            "recent_goal_failed": self.recent_goal_failed,
            "beliefs_total": self.beliefs_total,
            "beliefs_domains": self.beliefs_domains[:8],
            "events_last_day": self.events_last_day,
            "events_result_fail": self.events_result_fail,
            "dlq_count": self.dlq_count,
            "growth_signals": self.growth_signals,
            "growth_applied": self.growth_applied,
            "llm_blocked_patterns": self.llm_blocked_patterns[:6],
            "recent_episodes": self.recent_episodes[:10],
            "working_memory_items": self.working_memory_items,
        }


class SelfReviewCollector:
    """只读采集 — 全部 mode=ro, 零写入。"""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path or os.environ.get(
            "OCOS_DB_PATH", os.path.expanduser("~/.ocos/ocos.db"))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def collect(self) -> ReviewEvidence:
        ev = ReviewEvidence()
        if not os.path.exists(self._db_path):
            logger.warning("SelfReview: db not found %s", self._db_path)
            return ev
        try:
            con = self._connect()
            con.row_factory = sqlite3.Row

            # episodes 总量与成败 — outcome JSON 精确判定 ("success": bool)
            # decision 是聚合文本 (一行含 ✗收集/✓分析), 关键词判定不可靠;
            # outcome LIKE '%false%' 会误匹配成功里的 "blocked": False
            ev.episodes_total = con.execute(
                "SELECT COUNT(*) FROM episodes").fetchone()[0]
            ev.episodes_success = con.execute(
                "SELECT COUNT(*) FROM episodes WHERE outcome LIKE '%\"success\": true%'"
            ).fetchone()[0]
            ev.episodes_failed = con.execute(
                "SELECT COUNT(*) FROM episodes WHERE outcome LIKE '%\"success\": false%'"
            ).fetchone()[0]

            # 失败模式: 从失败 episode 的 decision 聚合文本中提取特征
            # (decision 聚合含多条子任务, 特征词仍可归因主导失败原因)
            rows = con.execute(
                "SELECT decision FROM episodes "
                "WHERE outcome LIKE '%\"success\": false%' "
                "ORDER BY rowid DESC LIMIT 300").fetchall()
            pattern_count: dict[str, int] = {}
            samples: dict[str, str] = {}
            for r in rows:
                txt = str(r["decision"])[:160]
                # 提取特征: 过于模糊/白名单/规划失败/LLM/超时
                for key in ("模糊", "白名单", "规划失败", "proxy", "openai",
                            "LLM", "超时", "not found", "拦截", "抽象",
                            "过于模糊", "pending_approval"):
                    if key in txt:
                        pattern_count[key] = pattern_count.get(key, 0) + 1
                        samples.setdefault(key, txt[:120])
                        break
                else:
                    # decision 无失败特征词: 聚合汇总 episode
                    # (子任务部分成功但整体周期失败) — 单独归因避免误导
                    if "✓" in txt or "completed" in txt.lower():
                        pattern_count["聚合部分失败"] = \
                            pattern_count.get("聚合部分失败", 0) + 1
                        samples.setdefault("聚合部分失败",
                                           "子任务部分成功但整体周期失败 (decision 聚合)")
                    else:
                        pattern_count["other"] = pattern_count.get("other", 0) + 1
                        samples.setdefault("other", txt[:120])
            ev.failure_patterns = [
                {"pattern": k, "count": v, "sample": samples[k]}
                for k, v in sorted(pattern_count.items(), key=lambda x: -x[1])]

            # goal 状态分布
            for r in con.execute("SELECT status, COUNT(*) n FROM goal GROUP BY status"):
                ev.goals_by_status[str(r["status"])] = r["n"]

            # 最近 15 goals 成败
            recent = con.execute(
                "SELECT status FROM goal ORDER BY created_at DESC LIMIT 15").fetchall()
            ev.recent_goal_ok = sum(1 for r in recent if r["status"] == "COMPLETED")
            ev.recent_goal_failed = sum(
                1 for r in recent if r["status"] not in ("COMPLETED", "ARCHIVED"))

            # beliefs — belief 表无 domain 列, 用 scope 分组
            try:
                ev.beliefs_total = con.execute(
                    "SELECT COUNT(*) FROM belief").fetchone()[0]
                rows = con.execute(
                    "SELECT COALESCE(scope, 'unscoped') s, COUNT(*) n "
                    "FROM belief GROUP BY s ORDER BY n DESC LIMIT 8").fetchall()
                ev.beliefs_domains = [{"domain": str(r["s"]), "count": r["n"]}
                                      for r in rows]
            except Exception:
                pass

            # event_store 近 24h
            try:
                ev.events_last_day = con.execute(
                    "SELECT COUNT(*) FROM event_store "
                    "WHERE created_at >= datetime('now', '-1 day')").fetchone()[0]
                ev.events_result_fail = con.execute(
                    "SELECT COUNT(*) FROM event_store "
                    "WHERE event_type='result' AND payload LIKE '%failed%' "
                    "AND created_at >= datetime('now', '-1 day')").fetchone()[0]
            except Exception:
                pass

            # DLQ
            try:
                ev.dlq_count = con.execute(
                    "SELECT COUNT(*) FROM dead_letter_queue").fetchone()[0]
            except Exception:
                pass

            # working memory 条目数
            try:
                wm = con.execute(
                    "SELECT value FROM working_memory WHERE key='wm:working'").fetchone()
                if wm:
                    data = json.loads(wm["value"])
                    ev.working_memory_items = len(data.get("items", []))
            except Exception:
                pass

            # 最近 episodes 样本 (成败各取)
            rows = con.execute(
                "SELECT goal, decision, outcome FROM episodes "
                "ORDER BY rowid DESC LIMIT 20").fetchall()
            for r in rows:
                goal_txt = str(r["goal"])[:70]
                dec_txt = str(r["decision"])[:120]
                ok = "true" in str(r["outcome"]) or "✓" in dec_txt
                ev.recent_episodes.append({
                    "goal": goal_txt, "ok": ok,
                    "decision": dec_txt[:100] if not ok else "✓ " + goal_txt[:60]})
            con.close()
        except Exception as e:
            logger.warning("SelfReview collect error: %s", e)
        return ev


class SelfReviewAnalyzer:
    """LLM 综合证据 → 不足 + 升级方向。"""

    def __init__(self, llm_fn: Any = None) -> None:
        self._llm = llm_fn or self._default_llm

    def _default_llm(self, prompt: str) -> str:
        from ocos.engines.text_generator import get_text_generator
        tg = get_text_generator()
        provider = getattr(tg, "_provider", tg)
        gen = getattr(provider, "generate", None)
        if gen is None:
            return '{"error": "no LLM provider"}'
        return asyncio.run(gen(
            prompt, system_prompt="你是 OCOS 内核架构师，输出结构化 JSON。",
            temperature=0.2, max_tokens=4000))

    def analyze(self, ev: ReviewEvidence) -> dict[str, Any]:
        """证据 → JSON 分析 (weaknesses/upgrades/priorities)。"""
        data = json.dumps(ev.to_dict(), ensure_ascii=False)
        prompt = f"""以下是 OCOS 认知系统的自省证据 (真实运行数据):

{data[:12000]}

请以系统架构师身份分析 OCOS 自身的不足与升级方向。只输出 JSON (不要代码块):

{{
  "overall_health": "良好/一般/欠佳 + 一句话依据",
  "weaknesses": [
    {{"issue": "具体不足", "evidence": "引用证据中的数字/模式", "impact": "影响什么"}}
  ],
  "upgrades": [
    {{"upgrade": "升级项", "rationale": "为什么", "priority": "P0/P1/P2"}}
  ],
  "biggest_bottleneck": "一句话: 当前最大结构瓶颈"
}}

要求: 严格基于证据, 不要泛泛而谈; 每个 weakness 必须有证据引用; 最多 5 弱点 + 5 升级。"""
        try:
            raw = self._llm(prompt)
            text = raw.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            return {"raw": raw[:2000]}
        except Exception as e:
            logger.warning("SelfReview analyze error: %s", e)
            return {"error": str(e)}


def render_markdown(ev: ReviewEvidence, analysis: dict[str, Any]) -> str:
    """证据 + 分析 → Markdown 报告。"""
    lines: list[str] = []
    lines.append("# OCOS 自省分析报告 (Self Review)")
    lines.append("")
    lines.append(f"- 生成时间: {ev.collected_at}")
    lines.append(f"- 证据库: {ev.episodes_total} episodes / "
                 f"{ev.goals_by_status.get('COMPLETED', 0)} completed goals / "
                 f"{ev.beliefs_total} beliefs")
    lines.append("")
    lines.append("## 运行概览")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| Episodes | {ev.episodes_total} (✓{ev.episodes_success} / ✗{ev.episodes_failed}) |")
    lines.append(f"| Goals | {json.dumps(ev.goals_by_status, ensure_ascii=False)} |")
    lines.append(f"| 近 15 goal 成败 | ✓{ev.recent_goal_ok} / ✗{ev.recent_goal_failed} |")
    lines.append(f"| 近 24h 事件 | {ev.events_last_day} (失败 {ev.events_result_fail}) |")
    lines.append(f"| DLQ | {ev.dlq_count} |")
    lines.append(f"| Working Memory | {ev.working_memory_items} 项 |")
    lines.append("")
    lines.append("## 失败模式 (证据)")
    lines.append("")
    for p in ev.failure_patterns:
        lines.append(f"- **{p['pattern']}** ×{p['count']}: `{p['sample'][:90]}`")
    lines.append("")
    lines.append("## 分析结论")
    lines.append("")
    lines.append(f"**总体健康**: {analysis.get('overall_health', '(无)')}")
    lines.append("")
    lines.append("### 不足")
    lines.append("")
    for w in analysis.get("weaknesses", []):
        lines.append(f"- **{w.get('issue', '')}** — 证据: {w.get('evidence', '')}")
        lines.append(f"  影响: {w.get('impact', '')}")
    lines.append("")
    lines.append("### 升级方向")
    lines.append("")
    for u in analysis.get("upgrades", []):
        lines.append(f"- [{u.get('priority', 'P2')}] **{u.get('upgrade', '')}** — {u.get('rationale', '')}")
    lines.append("")
    lines.append(f"**最大瓶颈**: {analysis.get('biggest_bottleneck', '(无)')}")
    lines.append("")
    return "\n".join(lines)


def write_report(md: str, out_dir: str = "") -> str:
    """报告落盘 docs/self_review/。返回路径。"""
    base = Path(out_dir) if out_dir else Path(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "docs" / "self_review"
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"self_review_{ts}.md"
    path.write_text(md, encoding="utf-8")
    return str(path)
