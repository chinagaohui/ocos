"""ocos/behavior — 行为轨迹捕获与对比（AGI 落地计划 P0）。

目标：让"学习前后行为差异"可测量（ER-2 Behavioral Delta 前置基座）。

轨迹 = 一次任务执行的"输入描述 → 动作序列 → 结果"快照，追加写入
JSONL（默认 ~/.ocos/behavior/，OCOS_BEHAVIOR_DIR 可覆盖）。
动作序列直接取 DecisionBridge 的 BridgeReport.summary()（executed/
pending/denied 三分类动作列表），不重复造数据源。

用法:
    from ocos.behavior.trajectory import record_trajectory
    record_trajectory(task_id="host-analysis", input_text="...",
                      actions=report.summary(), outcome="completed")
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

__all__ = [
    "default_behavior_dir",
    "record_trajectory",
    "load_trajectories",
    "compare_trajectories",
]


def default_behavior_dir() -> Path:
    """行为轨迹目录（~/.ocos/behavior，OCOS_BEHAVIOR_DIR 可覆盖）。"""
    override = os.environ.get("OCOS_BEHAVIOR_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".ocos" / "behavior"


def record_trajectory(
    task_id: str,
    input_text: str,
    actions: dict[str, Any],
    outcome: str,
    base_dir: str | Path | None = None,
) -> Path:
    """追加一条行为轨迹到 JSONL。

    Args:
        task_id: 任务标识（同任务前后对比用同一 id，如 "host-analysis"）。
        input_text: 任务输入描述（决策 prompt 侧）。
        actions: BridgeReport.summary() 的 dict（executed/pending/denied）。
        outcome: completed / pending_approval / failed / blocked。
        base_dir: 覆盖默认行为目录（测试用）。
    """
    base = Path(base_dir) if base_dir else default_behavior_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{task_id}.jsonl"
    row = {
        "task_id": task_id,
        "input": input_text[:500],
        "actions": actions,
        "outcome": outcome,
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def load_trajectories(
    task_id: str,
    base_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """读取某任务的全部轨迹记录（时间升序）。"""
    base = Path(base_dir) if base_dir else default_behavior_dir()
    path = base / f"{task_id}.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def compare_trajectories(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """对比两次轨迹，产出 Behavioral Delta 原始数据（P0.2 工具的输入）。

    输出:
      - similarity: 动作序列相似度（0.0-1.0，按动作类型序列的简单重叠率）
      - success_delta: outcome 成功度变化（completed=1, pending=0.5, failed/blocked=0）
      - path_changed: 动作序列差异明细
    """
    b_acts = before.get("actions", {}).get("executed", [])
    a_acts = after.get("actions", {}).get("executed", [])
    common = len(set(b_acts) & set(a_acts))
    union = len(set(b_acts) | set(a_acts)) or 1
    similarity = round(common / union, 4)

    def _score(outcome: str) -> float:
        return {"completed": 1.0, "pending_approval": 0.5,
                "failed": 0.0, "blocked": 0.0}.get(outcome, 0.0)

    b_denied = set(before.get("actions", {}).get("denied", []))
    a_denied = set(after.get("actions", {}).get("denied", []))
    return {
        "similarity": similarity,
        "success_delta": round(_score(after.get("outcome", ""))
                               - _score(before.get("outcome", "")), 4),
        "path_changed": {
            "added": sorted(set(a_acts) - set(b_acts)),
            "removed": sorted(set(b_acts) - set(a_acts)),
            "denied_removed": sorted(b_denied - a_denied),
        },
        "attributable_to": None,  # P1.2 注入 artifact id 时回填
    }
