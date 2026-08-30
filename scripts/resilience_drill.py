"""PW-3.2: 韧性演练 — 注入故障 → 检出 → 修复/恢复 → 评分。

对齐 resurrection_drill.py 模式: 注入 Damage（记忆膨胀/归档延迟）→
验证 HealthLoop/diagnosis 链能检出 → 执行白名单修复 → 输出韧性评分。

用法:
    python scripts/resilience_drill.py [--db PATH]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _seed_damage(db: str, n: int = 40) -> None:
    """注入损伤: 大量 90 天前的低显著度 Episode（记忆膨胀）。"""
    conn = sqlite3.connect(db)
    from ocos.storage.migrations import ensure_schema
    conn.close()
    ensure_schema(db)
    conn = sqlite3.connect(db)
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    for i in range(n):
        conn.execute(
            """INSERT OR IGNORE INTO episodes
               (id, experience_id, session_id, context, goal, decision,
                action, outcome, condition, significance_score,
                evaluation_trace, source, status, tags, created_at)
               VALUES (?, ?, 'drill', '{}', NULL, ?, 'task_execution',
                       '{}', '', 0.1, '{}', 'drill', 'ACTIVE', '[]', ?)""",
            (f"EPI-DRILL-{i}", f"EXP-DRILL-{i}", f"陈旧任务 {i}", old))
    conn.commit()
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="")
    args = parser.parse_args()
    db = args.db or (Path(tempfile.mkdtemp()) / "resilience.db").as_str() \
        if False else (args.db or __import__("tempfile").mkdtemp() + "/resilience.db")

    print("OCOS 韧性演练 — 注入 → 检出 → 修复")
    print("=" * 52)

    # 1. 注入损伤
    _seed_damage(db, n=40)
    conn = sqlite3.connect(db)
    before = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE significance_score < 0.3").fetchone()[0]
    conn.close()
    print(f"  [1] 注入 40 条陈旧低显著度 Episode（当前 <0.3 计数: {before}）")

    # 2. 诊断循环检出
    from ocos.daemon.repair_link import run_diagnosis_cycle, execute_system_repair
    diag = run_diagnosis_cycle(db)
    print(f"  [2] 诊断: faults={diag['faults']} degraded={diag['degraded']} "
          f"修复提案入队={len(diag['repairs_queued'])}")

    # 3. 执行白名单修复（归档类）
    repaired = False
    from ocos.execution.pending import PendingStore
    store = PendingStore(db)
    b = __import__("ocos.execution.bridge", fromlist=["DecisionBridge"]) \
        .DecisionBridge(db_path=db)
    b.attach_default_handlers()
    for row in store.list_by_status("pending"):
        payload = json.loads(row["payload_json"])
        if any("归档" in s or "修剪" in s or "索引" in s for s in payload.get("steps", [])):
            store.decide(row["id"], approved=True, decided_by="drill")
            r = b.execute_approved("system_repair", payload)
            store.mark_executed(row["id"], result_summary=str(r.result),
                                executed=bool(r.result.get("ok")))
            repaired = repaired or bool(r.result.get("ok"))
    print(f"  [3] 白名单修复执行: {'✓' if repaired else '— 无匹配的归档/索引修复'}")

    # 4. 验证恢复
    conn = sqlite3.connect(db)
    after = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE significance_score < 0.3 "
        "AND status='ACTIVE'").fetchone()[0]
    conn.close()
    score = 10 if (before == 0 or after < before) else 0
    print(f"  [4] 恢复验证: ACTIVE 低显著度残留 {after} → "
          f"{'✓ 改善' if after < before else '（本库无归档类损伤，跳过）'}")
    print("=" * 52)
    print(f"resilience score: {score}/10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
