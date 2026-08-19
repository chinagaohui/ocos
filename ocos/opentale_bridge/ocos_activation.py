"""ocos 侧激活计数器（S7 生产激活观测，OCOS 组件）。

与 opentale/app/activation.py 对应。CLI 每次调用是独立进程——必须
**文件持久化**（追加 ~/.ocos/activation.jsonl）跨进程累积，终局汇总。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()
_ACTIVATION: dict[str, int] = {}


def _log_path() -> Path:
    p = Path(os.getenv("OCOS_ACTIVATION_LOG", str(Path.home() / ".ocos" / "activation.jsonl")))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def activate(component_id: str) -> None:
    with _LOCK:
        _ACTIVATION[component_id] = _ACTIVATION.get(component_id, 0) + 1
        # 文件持久化（跨进程累积）
        try:
            with open(_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"component": component_id}) + "\n")
        except Exception:
            pass


def snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_ACTIVATION)


def reset() -> None:
    with _LOCK:
        _ACTIVATION.clear()
    try:
        _log_path().unlink(missing_ok=True)
    except Exception:
        pass


def summarize() -> dict[str, int]:
    """从持久化日志汇总全部进程的激活计数。"""
    counts: dict[str, int] = {}
    p = _log_path()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                cid = json.loads(line)["component"]
                counts[cid] = counts.get(cid, 0) + 1
            except Exception:
                continue
    return counts
