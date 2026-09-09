"""一次性诊断脚本：手动触发 dream cycle，观察 builder._candidates 状态。"""
from __future__ import annotations

import os
import sys
import json
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("diagnose_dream")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    db = os.path.expanduser("~/.ocos/ocos.db")
    conn = sqlite3.connect(db)
    before_lessons = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source='lesson'"
    ).fetchone()[0]
    before_c_lessons = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source='lesson' AND decision LIKE '%【%'"
    ).fetchone()[0]
    print(f"[基线] lesson episodes: {before_lessons}, C-class: {before_c_lessons}")

    # 1. 用工厂构建 MasterAgent（和 daemon 一样）
    print("\n[构建 MasterAgent via factory]...")
    from ocos.daemon.factory import build_master_agent
    agent = build_master_agent("diag-agent", db_path=db)
    builder = getattr(agent, "_experience_builder", None)
    print(f"builder 存在: {builder is not None}")
    if builder:
        print(f"  初始 _candidates: {len(builder._candidates)}")

    # 2. 手动触发 dream cycle
    print("\n[跑 dream cycle]...")
    from ocos.daemon.consolidation_service import LearningConsolidationService
    svc = LearningConsolidationService(db_path=db)
    try:
        out = svc.run_dream_cycle(agent)
        print(f"dream 输出: {json.dumps(out, indent=2, default=str)[:600]}")
    except Exception as e:
        print(f"❌ dream 抛异常: {e}")
        import traceback; traceback.print_exc()

    # 3. 再查 builder 状态
    if builder:
        print(f"\n[dream 后] builder._candidates: {len(builder._candidates)}")
        complete = builder.get_complete()
        incomplete = builder.get_incomplete()
        print(f"  COMPLETE: {len(complete)}, INCOMPLETE: {len(incomplete)}")
        for c in incomplete[:5]:
            print(f"    INCOMPLETE id={getattr(c,'id','?')} reason={getattr(c,'rejection_reason','?')}")

    # 4. 对比 DB
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT action, decision, created_at FROM episodes "
        "WHERE source='lesson' ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    print(f"\n[新 lessons 最近 5 条]:")
    for r in rows:
        print(f"  {r['created_at'][11:19]} action={r['action']:25s} decision={str(r['decision'])[:100]}")

    conn.close()
    print("\n✅ 诊断完成")

if __name__ == "__main__":
    main()
