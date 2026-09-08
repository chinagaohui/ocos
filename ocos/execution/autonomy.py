"""L0-3: 自主行为总闸（OCOS_AUTONOMY_LEVEL）。

四级自主性（升级方案 v1.0 §二 L0-3）:
    0 = 只执行用户目标（零自主提案/主动行为）
    1 = 可自主提案需批（默认 — 提案进 outbox/待批队列，不自动执行）
    2 = 低风险自主执行（只读探测/学习类可自主，写类仍需审批）
    3 = 全自主（受审批红线与审计约束）

来源优先级: 覆盖文件 ~/.ocos/autonomy_level（运行期即时生效，由
`ocos autonomy <n>` 写入）> 环境变量 OCOS_AUTONOMY_LEVEL（daemon 启动读取）
> 默认 1。

切换审计: 级别变化 → ~/.ocos/audit/autonomy.jsonl 留痕 + 可选写入
audit episode（tags 含 "autonomy"），保证任一自主行为可回放到当时的级别。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_AUTONOMY_LEVEL = 1
VALID_LEVELS = (0, 1, 2, 3)

LEVEL_DESCRIPTIONS = {
    0: "只执行用户目标（零自主行为）",
    1: "可自主提案需批",
    2: "低风险自主执行（只读探测/学习类）",
    3: "全自主（红线与审计约束下）",
}


def autonomy_override_path() -> Path:
    return Path(os.environ.get(
        "OCOS_AUTONOMY_OVERRIDE",
        str(Path.home() / ".ocos" / "autonomy_level"))).expanduser()


def _parse_level(raw: str | int | None) -> int | None:
    """解析级别字符串；非法值返回 None（调用方回退默认）。"""
    if raw is None:
        return None
    try:
        lvl = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return lvl if lvl in VALID_LEVELS else None


def get_autonomy_level() -> int:
    """读取当前自主级别（每次调用重读 — 运行期切换即时生效）。"""
    path = autonomy_override_path()
    if path.exists():
        lvl = _parse_level(path.read_text(encoding="utf-8"))
        if lvl is not None:
            return lvl
        logger.warning("autonomy override file invalid: %s — 忽略", path)
    lvl = _parse_level(os.environ.get("OCOS_AUTONOMY_LEVEL"))
    if lvl is not None:
        return lvl
    return DEFAULT_AUTONOMY_LEVEL


def set_autonomy_level(level: int) -> int:
    """写入覆盖文件（运行期切换通道）；返回实际生效级别。

    非法级别抛 ValueError — 调用方（CLI）负责向用户诚实报错。
    """
    lvl = _parse_level(level)
    if lvl is None:
        raise ValueError(
            f"invalid autonomy level: {level!r} — 合法值 0/1/2/3")
    path = autonomy_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(lvl), encoding="utf-8")
    return lvl


# ── 级别判据（全链路闸门统一从这里取，不各自散写硬编码） ────────────────

def can_propose(level: int | None = None) -> bool:
    """LEVEL>=1: 允许自主提案（提案仍需审批/进 outbox）。"""
    return (level if level is not None else get_autonomy_level()) >= 1


def can_autonomous_execute(level: int | None = None) -> bool:
    """LEVEL>=2: 低风险（只读/学习类）自主执行。"""
    return (level if level is not None else get_autonomy_level()) >= 2


def full_autonomy(level: int | None = None) -> bool:
    return (level if level is not None else get_autonomy_level()) >= 3


# ── 审计 ─────────────────────────────────────────────────────────────────

def audit_log_path() -> Path:
    """审计 JSONL 路径（OCOS_AUDIT_DIR 可覆写 — 测试/多实例隔离）。"""
    base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
    if base:
        return Path(base).expanduser() / "autonomy.jsonl"
    return Path.home() / ".ocos" / "audit" / "autonomy.jsonl"


def append_audit_record(record: dict) -> str:
    """追加一条自主行为审计（JSONL）。返回写入路径。"""
    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {**record,
         "ts": datetime.now(timezone.utc).isoformat(),
         "pid": os.getpid()},
        ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return str(path)


def audit_level_change(db_path: str | None, old: int, new: int,
                       source: str = "runtime") -> None:
    """级别切换审计: JSONL 留痕 + audit episode（db_path 提供时）。

    episode 落库失败不阻断切换（审计文件已是权威留痕），只告警。
    """
    append_audit_record({"kind": "level_change", "old": old, "new": new,
                         "source": source})
    if db_path and db_path != ":memory:":
        try:
            from ocos.memory.episode.models import Episode
            from ocos.memory.episode.store import EpisodeStore
            store = EpisodeStore(db_path=db_path)
            store.initialize()   # 自愈建表（独立 CLI 环境可能未跑 migrations）
            store.save(Episode(
                id=f"EPI-AUTONOMY-{int(datetime.now().timestamp()*1000)}",
                experience_id="autonomy_gate",
                created_at=datetime.now(timezone.utc),
                context={"old_level": old, "new_level": new,
                         "source": source},
                decision=(f"自主级别切换 {old} → {new} "
                          f"({LEVEL_DESCRIPTIONS.get(new, '?')})"),
                source="anomaly",
                tags=["autonomy", "audit", "level_change"],
            ))
        except Exception:
            logger.warning("autonomy level-change episode 落库失败",
                           exc_info=True)


def audit_brake(db_path: str | None, braked: bool) -> None:
    """制动/解除制动审计（STOP 神经 — L0-5 同源审计链）。"""
    append_audit_record({"kind": "brake", "braked": bool(braked)})
    if db_path and db_path != ":memory:":
        try:
            from ocos.memory.episode.models import Episode
            from ocos.memory.episode.store import EpisodeStore
            store = EpisodeStore(db_path=db_path)
            store.initialize()   # 自愈建表（独立 CLI 环境可能未跑 migrations）
            store.save(Episode(
                id=f"EPI-BRAKE-{int(datetime.now().timestamp()*1000)}",
                experience_id="stop_nerve",
                created_at=datetime.now(timezone.utc),
                context={"braked": bool(braked)},
                decision=("自主活动已制动（对话仍响应）" if braked
                          else "制动已解除，自主活动恢复"),
                source="anomaly",
                tags=["autonomy", "audit", "brake"],
            ))
        except Exception:
            logger.warning("brake audit episode 落库失败", exc_info=True)
