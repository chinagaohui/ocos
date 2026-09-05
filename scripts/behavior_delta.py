#!/usr/bin/env python3
"""P0.2: Behavioral Delta 量化工具（AGI 落地计划 P0 / ER-2 基座）。

对同一任务两次执行的轨迹 JSONL 做对比，输出：
  - similarity     动作序列相似度（0.0-1.0）
  - success_delta  成功度变化（completed=1 / pending=0.5 / failed|blocked=0）
  - path_changed   动作增删明细（含 denied 收敛）

用法:
  python3 scripts/behavior_delta.py --task host-analysis            # 用 ~/.ocos/behavior
  python3 scripts/behavior_delta.py --task host-analysis --dir PATH # 指定轨迹目录
  python3 scripts/behavior_delta.py --task host-analysis --json     # 输出 JSON 行

退出码: 0=可归因变化或一致；2=记录不足一次（需 ≥2 条才能对比）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="任务标识（轨迹文件 base name）")
    parser.add_argument("--dir", default="",
                        help="轨迹目录（默认 ~/.ocos/behavior）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ocos.behavior.trajectory import (
        compare_trajectories, load_trajectories,
    )

    rows = load_trajectories(args.task, base_dir=args.dir or None)
    if len(rows) < 2:
        print(f"[{args.task}] 轨迹记录 {len(rows)} 条（需 ≥2 条才能对比）")
        return 2

    delta = compare_trajectories(rows[-2], rows[-1])
    if args.json:
        print(json.dumps({"task": args.task, **delta}, ensure_ascii=False))
        return 0

    print(f"== Behavioral Delta: {args.task} ==")
    print(f"  相似度       : {delta['similarity']:.2f}")
    print(f"  成功度变化   : {delta['success_delta']:+.2f}"
          f"  ({rows[-2].get('outcome')} → {rows[-1].get('outcome')})")
    pc = delta["path_changed"]
    print(f"  动作新增     : {pc['added'] or '-'}")
    print(f"  动作移除     : {pc['removed'] or '-'}")
    print(f"  拦截收敛     : {pc['denied_removed'] or '-'}")
    if delta["attributable_to"]:
        print(f"  可归因产物   : {delta['attributable_to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
