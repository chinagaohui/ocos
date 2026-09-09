#!/usr/bin/env python3
"""Phase B 纵向自进化验证 — 每日快照 + 多日趋势判定。

用法:
    # 单次快照（每天 cron 调一次）
    python scripts/self_evolution_daily_test.py snapshot

    # 查看历史快照趋势（≥2 天数据时输出 Pass/Fail）
    python scripts/self_evolution_daily_test.py trend

    # 合成测试（造假数据验证趋势判定逻辑）
    python scripts/self_evolution_daily_test.py synthetic

通过门槛（路线图 §B1+§B2）:
    连续 7 天中 ≥3 项指标呈改善趋势:
      失败率 ↓ / 工具利用率 ↑ / C 类产出 ↑ / 复用率 ↑ / 复发率 ↓

设计原则:
    - 纯数据驱动：只读 episodes 表，无副作用
    - 诚实降级：缺 DB/缺 episodes 时存空 snapshot，不报错
    - 可审计：每次快照含完整 vitals dict，落盘可溯源
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── 路径约定 ──────────────────────────────────────────────────────

SNAPSHOT_DIR = Path.home() / ".ocos" / "self_evolution"
SNAPSHOT_FILE = SNAPSHOT_DIR / "daily_snapshots.jsonl"
DEFAULT_DB = os.environ.get(
    "OCOS_DB_PATH", str(Path.home() / ".ocos" / "ocos.db"))


# ── 快照采集 ──────────────────────────────────────────────────────

def collect_snapshot(db_path: str = DEFAULT_DB) -> dict:
    """采集一次自进化指标快照（诚实降级）。"""
    try:
        from ocos.monitoring.vitals import compute_vitals
        vitals = compute_vitals(db_path, window_days=7)
    except Exception as e:
        vitals = {"error": str(e)}

    now = datetime.now(timezone.utc)
    return {
        "ts": now.isoformat(),
        "day_key": now.strftime("%Y-%m-%d"),
        "db_path": db_path,
        # Phase B 5 项自进化指标（从 vitals 中提取）
        "failure_rate_trend_delta": vitals.get("failure_rate_trend_delta"),
        "recent_7d_success_rate": vitals.get("recent_7d_success_rate"),
        "tool_utilization_rate": vitals.get("tool_utilization_rate"),
        "c_lesson_production_per_day": vitals.get("c_lesson_production_per_day"),
        "lesson_injection_intensity": vitals.get("lesson_injection_intensity"),
        "failure_recurrence_rate": vitals.get("failure_recurrence_rate"),
        # 基础 counts（供调试）
        "tool_action_total_30d": vitals.get("tool_action_total_30d"),
        "c_lesson_count_7d": vitals.get("c_lesson_count_7d"),
        "lesson_prior_injections_7d": vitals.get("lesson_prior_injections_7d"),
        # 状态标记
        "missing": vitals.get("missing", []),
    }


def save_snapshot(snapshot: dict) -> Path:
    """追加一条快照到 jsonl（幂等：同一天重复调用覆盖同 day_key）。"""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 先读现有快照，过滤掉同 day_key 的（覆盖）
    existing: list[dict] = []
    if SNAPSHOT_FILE.exists():
        try:
            with SNAPSHOT_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            existing.append(json.loads(line))
                        except ValueError:
                            continue
        except OSError:
            pass

    existing = [s for s in existing if s.get("day_key") != snapshot["day_key"]]
    existing.append(snapshot)

    with SNAPSHOT_FILE.open("w", encoding="utf-8") as f:
        for s in existing:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    return SNAPSHOT_FILE


# ── 趋势判定 ──────────────────────────────────────────────────────

def load_snapshots() -> list[dict]:
    if not SNAPSHOT_FILE.exists():
        return []
    out: list[dict] = []
    with SNAPSHOT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    # 按 day_key 排序
    out.sort(key=lambda s: s.get("day_key", ""))
    return out


def _metric_trend(points: list[tuple[float, str]],
                  metric_name: str,
                  higher_is_better: bool) -> dict:
    """判定单个指标的趋势方向。

    points: [(value, day_key), ...] 升序排列
    higher_is_better: True=上升变好，False=下降变好（如 failure rate）
    返回: {"trend": "improving" | "degrading" | "flat" | "insufficient",
           "delta": float, "first_val": float, "last_val": float}
    """
    valid = [(v, d) for v, d in points if v is not None]
    if len(valid) < 2:
        return {"trend": "insufficient", "delta": 0,
                "first_val": None, "last_val": None}

    first_val, _ = valid[0]
    last_val, _ = valid[-1]
    delta = last_val - first_val

    if abs(delta) < 1e-6:
        trend = "flat"
    elif higher_is_better and delta > 0 or not higher_is_better and delta < 0:
        trend = "improving"
    else:
        trend = "degrading"

    return {"trend": trend, "delta": round(delta, 4),
            "first_val": round(first_val, 4), "last_val": round(last_val, 4)}


def compute_trend(snapshots: list[dict]) -> dict:
    """对多日快照计算 5 项自进化指标的趋势。

    返回:
      {
        "days_analyzed": int,
        "metrics": {metric_name: trend_dict, ...},
        "improving_count": int,
        "verdict": "PASS" | "FAIL" | "INSUFFICIENT",
        "verdict_rule": "≥3 improving in ≥7 days"
      }
    """
    if len(snapshots) < 2:
        return {
            "days_analyzed": len(snapshots),
            "metrics": {},
            "improving_count": 0,
            "verdict": "INSUFFICIENT",
            "verdict_rule": "≥3 improving in ≥7 days (need ≥2 snapshots)",
        }

    # 每项指标提取 (value, day_key) 序列
    m = snapshots
    def pts(key: str) -> list[tuple[Any, str]]:
        return [(s.get(key), s.get("day_key", "")) for s in m]

    trends: dict[str, dict] = {}

    # 1. 近 7d success rate（↑ 变好）
    trends["recent_7d_success_rate"] = _metric_trend(
        pts("recent_7d_success_rate"), "recent_7d_success_rate", True)

    # 2. 工具利用率（↑ 变好）
    trends["tool_utilization_rate"] = _metric_trend(
        pts("tool_utilization_rate"), "tool_utilization_rate", True)

    # 3. C 类 Lesson 日均产出（↑ 变好）
    trends["c_lesson_production_per_day"] = _metric_trend(
        pts("c_lesson_production_per_day"), "c_lesson_production_per_day", True)

    # 4. Lesson 注入强度（↑ 变好，≥1× = 高频）
    trends["lesson_injection_intensity"] = _metric_trend(
        pts("lesson_injection_intensity"), "lesson_injection_intensity", True)

    # 5. 同型失败复发率（↓ 变好）
    trends["failure_recurrence_rate"] = _metric_trend(
        pts("failure_recurrence_rate"), "failure_recurrence_rate", False)

    improving = sum(1 for t in trends.values() if t.get("trend") == "improving")
    insufficient = sum(1 for t in trends.values() if t.get("trend") == "insufficient")

    days = len(snapshots)
    if days >= 7 and improving >= 3:
        verdict = "PASS"
    elif days < 7:
        verdict = "INSUFFICIENT"
    else:
        verdict = "FAIL"

    return {
        "days_analyzed": days,
        "date_range": f"{snapshots[0].get('day_key')} → {snapshots[-1].get('day_key')}",
        "metrics": trends,
        "improving_count": improving,
        "degrading_count": sum(1 for t in trends.values()
                               if t.get("trend") == "degrading"),
        "insufficient_count": insufficient,
        "verdict": verdict,
        "verdict_rule": "≥3 improving in ≥7 days",
    }


# ── 合成数据验证 ──────────────────────────────────────────────────

def run_synthetic() -> str:
    """造 7 天假数据（4 项改善 + 1 持平）→ 应判定 PASS。"""
    now = datetime.now(timezone.utc)
    existing = load_snapshots()

    # 用临时文件覆盖
    global SNAPSHOT_FILE
    import tempfile
    tmpdir = Path(tempfile.mkdtemp())
    SNAPSHOT_FILE = tmpdir / "daily_snapshots.jsonl"

    base_success = 0.60
    base_tool = 0.55
    base_c_prod = 0.14
    base_reuse = 0.05
    base_recur = 0.40

    for day_offset in range(7):
        day = now - timedelta(days=6 - day_offset)
        snapshot = {
            "ts": day.isoformat(),
            "day_key": day.strftime("%Y-%m-%d"),
            "db_path": "/tmp/synthetic.db",
            # 4 项逐步改善，1 项持平
            "failure_rate_trend_delta": None,  # 需要 14d 数据
            "recent_7d_success_rate": round(
                base_success + 0.03 * day_offset, 4),  # ↑ 60→78%
            "tool_utilization_rate": round(
                base_tool + 0.02 * day_offset, 4),     # ↑ 55→69%
            "c_lesson_production_per_day": round(
                base_c_prod + 0.02 * day_offset, 2),    # ↑ 0.14→0.26
            "lesson_reuse_rate": round(
                base_reuse + 0.015 * day_offset, 4),    # ↑ 5→14%
            "failure_recurrence_rate": round(
                base_recur - 0.03 * day_offset, 4),     # ↓ 40→22%
            "tool_action_total_30d": 20 + day_offset * 2,
            "c_lesson_count_7d": 1 + day_offset,
            "lesson_prior_injections_7d": 2 + day_offset * 2,
            "missing": [],
        }
        save_snapshot(snapshot)

    snapshots = load_snapshots()
    result = compute_trend(snapshots)
    assert result["verdict"] == "PASS", f"Expected PASS, got {result}"

    # 清理
    import shutil
    shutil.rmtree(tmpdir)

    # 恢复原路径
    SNAPSHOT_FILE = Path.home() / ".ocos" / "self_evolution" / "daily_snapshots.jsonl"

    return f"✅ Synthetic test PASS: {result['improving_count']} improving " \
           f"in {result['days_analyzed']} days → {result['verdict']}"


# ── 标准化任务执行 ───────────────────────────────────────────────

# 预定义的标准化任务（路线图 §B2 要求）
_STANDARD_TASKS: dict[str, str] = {
    "analyze_project_structure": "分析项目结构：扫描根目录列出所有顶层文件和子目录，"
                                 "识别主要代码语言和框架，给出项目规模估算。",
    "batch_file_read": "批量读取文件：列出 tests 目录下所有测试文件，"
                       "分批读取前 5 个文件的内容摘要。",
}


def run_standard_task(task_name: str) -> dict:
    """执行一个标准化任务并记录行为数据。

    实现策略（诚实降级）:
      - 如果 OCOS daemon 正在运行（检查 heartbeat），尝试通过 converse API 调用
      - 如果 daemon 未运行，进入 stub 模式：仅记录任务定义 + 从现有 episodes
        推断 step_count / failure_count / used_c_procedure / summary_word_count
      - 无论哪种模式都返回统一 schema，供趋势判定使用

    返回 schema:
      {step_count, failure_count, used_c_procedure, summary_word_count,
       mode: "real" | "stub", task_name, task_description}
    """
    description = _STANDARD_TASKS.get(task_name, task_name)
    db_path = os.environ.get("OCOS_DB_PATH", DEFAULT_DB)

    # 检查 daemon heartbeat
    hb_path = Path(os.environ.get(
        "OCOS_HEARTBEAT_PATH", str(Path.home() / ".ocos" / "heartbeat.json")))
    daemon_alive = hb_path.exists()

    if daemon_alive:
        # Real mode: 尝试通过 converse API 执行任务
        try:
            import urllib.request
            api_url = os.environ.get("OCOS_API_URL",
                                     "http://localhost:8080/api/chat")
            import json as _json
            req = urllib.request.Request(
                api_url, data=_json.dumps(
                    {"message": description}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                response = _json.loads(resp.read())
            # 从 response 提取指标
            return {
                "mode": "real",
                "task_name": task_name,
                "task_description": description,
                "step_count": response.get("steps", 0),
                "failure_count": response.get("failures", 0),
                "used_c_procedure": response.get("used_c_procedure", False),
                "summary_word_count": len(
                    response.get("summary", "").split()),
            }
        except Exception as e:
            # API 调用失败 → 降级到 stub
            logger = __import__("logging").getLogger(__name__)
            logger.warning("run-task real mode failed (%s), falling back to stub", e)

    # Stub mode: 从现有 DB 推断 + 合理默认值
    try:
        import sqlite3 as _sqlite3
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=2)).isoformat()
        result: dict[str, Any] = {
            "mode": "stub",
            "task_name": task_name,
            "task_description": description,
            "step_count": 0,
            "failure_count": 0,
            "used_c_procedure": False,
            "summary_word_count": 0,
        }
        if Path(db_path).exists():
            conn = _sqlite3.connect(db_path)
            # 最近 2h 的 episode action 数 = step_count
            try:
                rows = conn.execute(
                    "SELECT action, outcome FROM episodes "
                    "WHERE created_at >= ? AND source != 'lesson'",
                    (cutoff,)).fetchall()
                result["step_count"] = len(rows)
                # outcome.success = False 的 = failure_count
                fails = sum(1 for _, oc in rows
                            if not __import__("json").loads(oc or "{}")
                            .get("success", True))
                result["failure_count"] = fails
            except _sqlite3.Error:
                pass
            # 检查最近 7d 是否有 C 类 Lesson 被注入
            try:
                cutoff_7d = (now - timedelta(days=7)).isoformat()
                lesson_rows = conn.execute(
                    "SELECT decision FROM episodes "
                    "WHERE source = 'lesson' AND created_at >= ?",
                    (cutoff_7d,)).fetchall()
                result["used_c_procedure"] = any(
                    desc and "【" in (desc or "")
                    for (desc,) in lesson_rows)
            except _sqlite3.Error:
                pass
            conn.close()
        return result
    except Exception:
        return {
            "mode": "stub",
            "task_name": task_name,
            "task_description": description,
            "step_count": 0,
            "failure_count": 0,
            "used_c_procedure": False,
            "summary_word_count": 0,
        }


# ── CLI ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase B 纵向自进化验证: 每日快照 + 多日趋势判定")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("snapshot", help="采集一次快照（cron 每日调）")
    sub.add_parser("trend", help="查看历史快照趋势")
    sub.add_parser("synthetic", help="合成数据验证趋势判定逻辑")
    rt = sub.add_parser("run-task",
                        help="执行标准化任务并记录行为数据（Phase B2 主动跑）")
    rt.add_argument("--task", default="analyze_project_structure",
                    choices=list(_STANDARD_TASKS.keys()),
                    help="预定义标准化任务（默认 analyze_project_structure）")

    args = parser.parse_args()

    if args.command == "synthetic":
        print(run_synthetic())
        return 0

    if args.command == "snapshot":
        snap = collect_snapshot()
        path = save_snapshot(snap)
        print(f"📸 Snapshot saved → {path}")
        print(f"   day_key: {snap['day_key']}")
        print(f"   failure_rate_trend_delta: {snap['failure_rate_trend_delta']}")
        print(f"   tool_utilization_rate:    {snap['tool_utilization_rate']}")
        print(f"   c_lesson_production/day:  {snap['c_lesson_production_per_day']}")
        print(f"   lesson_injection_intensity: {snap['lesson_injection_intensity']}")
        print(f"   failure_recurrence_rate:  {snap['failure_recurrence_rate']}")
        if snap.get("missing"):
            print(f"   ⚠ missing: {snap['missing']}")
        return 0

    if args.command == "run-task":
        task_name = getattr(args, "task", "analyze_project_structure")
        result = run_standard_task(task_name)
        print(f"🎯 Task '{task_name}' recorded")
        print(f"   steps: {result['step_count']}  "
              f"failures: {result['failure_count']}")
        print(f"   used_c_procedure: {result['used_c_procedure']}  "
              f"summary_words: {result['summary_word_count']}")
        # 任务执行后立刻采 snapshot（包含任务产出的新 episodes）
        snap = collect_snapshot()
        snap["task"] = result
        path = save_snapshot(snap)
        print(f"   Snapshot → {path}")
        return 0

    if args.command == "trend":
        snaps = load_snapshots()
        if not snaps:
            print("⚠ No snapshots yet. Run 'snapshot' first.")
            return 1
        result = compute_trend(snaps)
        print(f"\n📊 Self-Evolution Trend ({result['days_analyzed']} days, "
              f"{result.get('date_range', '?')})")
        print("─" * 50)
        for metric_name, trend in result.get("metrics", {}).items():
            arrow = {"improving": "↑", "degrading": "↓",
                     "flat": "→", "insufficient": "?"}.get(trend["trend"], "?")
            print(f"  {arrow} {metric_name:35s} "
                  f"first={trend['first_val']} last={trend['last_val']} "
                  f"Δ={trend['delta']}")
        print("─" * 50)
        print(f"  Improving: {result.get('improving_count', 0)}  "
              f"Degrading: {result.get('degrading_count', 0)}  "
              f"Insufficient: {result.get('insufficient_count', 0)}")
        print(f"  Verdict: ** {result['verdict']} ** "
              f"(rule: {result.get('verdict_rule', '?')})")
        return 0 if result["verdict"] in ("PASS", "INSUFFICIENT") else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
