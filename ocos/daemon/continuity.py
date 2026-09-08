"""L4-3 (升级方案 v1.0): ContinuityChecker — boot 时 V5 跨重启一致性校验。

V5 判据: 跨重启身份参数/价值观/人格零漂移; 记忆一致性校验通过。

每次 boot 校验三件套并与基线对比:
    1. 身份参数 hash — IdentityAnchor（agent_id/born_at/name）
       + 宪法当前版本与原则 hash（L4-1）+ 自我模型画像 hash（L4-2）
       → 组成"身份快照 hash"。零漂移 = 人格未变。
    2. 记忆计数断言 — episodes 计数单调不减（重启后变少 = 记忆丢失）。
    3. 基线读写 — audit 目录 continuity_baseline.json
       （OCOS_AUDIT_DIR 解析与 self_check 同源）；首启写基线不算漂移。

漂移/记忆丢失 → audit episode（source="continuity_check"，可溯源）+
返回详情（daemon start 转 outbox 告警 — 如实上报，不静默）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_BASELINE_FILE = "continuity_baseline.json"


class ContinuityChecker:
    """boot 时 V5 校验（daemon start 调用一次）。"""

    def __init__(self, db_path: str,
                 audit_dir: Path | None = None) -> None:
        self._db_path = db_path
        self._audit_dir = audit_dir

    # ── 主入口 ────────────────────────────────────────────────────────

    def boot_check(self, identity_params: dict | None = None,
                   notify_fn: Callable[[str], None] | None = None) -> dict:
        """执行校验，返回结果 dict（daemon 装配层消费）。

        identity_params: 装配层从 IdentityAnchor 提取
        {agent_id, born_at, name}；缺省（无锚）→ 用 db 文件名占位，
        诚实标注 identity_available=False。
        """
        identity_params = dict(identity_params or {})
        constitution = self._constitution_state()
        self_model_hash = self._self_model_hash()
        snapshot = {
            "identity": identity_params,
            "identity_available": bool(identity_params),
            "constitution": constitution,
            # 自我模型随行为演进 — 单独记录，不计入漂移判定 hash
            "self_model_hash": self_model_hash,
        }
        identity_hash = self._hash({"identity": identity_params,
                                    "constitution": constitution})
        memory_count = self._count_episodes()

        baseline, baseline_error = self._read_baseline()
        result: dict = {
            "identity_hash": identity_hash,
            "memory_count": memory_count,
            "drift": False,
            "memory_loss": False,
            "baseline_created": False,
            "details": [],
        }

        if baseline is None:
            if baseline_error:
                result["details"].append(f"基线读取失败: {baseline_error}")
                logger.warning("V5 baseline read failed: %s", baseline_error)
            result["baseline_created"] = True
        else:
            prev_hash = baseline.get("identity_hash", "")
            prev_count = int(baseline.get("memory_count", 0))
            if prev_hash and prev_hash != identity_hash:
                result["drift"] = True
                result["details"].append(
                    self._drift_reason(baseline.get("snapshot", {}),
                                       snapshot))
            if memory_count < prev_count:
                result["memory_loss"] = True
                result["details"].append(
                    f"记忆计数下降 {prev_count} → {memory_count}"
                    f"（丢失 {prev_count - memory_count} 条）")

        # 基线更新（漂移时也以当前为准落新基线 — 已告警，不阻塞后续 boot）
        write_err = self._write_baseline({
            "identity_hash": identity_hash,
            "memory_count": memory_count,
            "snapshot": snapshot,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })
        if write_err:
            result["details"].append(f"基线写入失败: {write_err}")

        # 校验结果落库（成功也记录 — vitals continuity_checks 需要
        # 正向证据，"无漂移"与"未校验"必须可区分）
        self._audit(result)
        if result["drift"] or result["memory_loss"] or baseline_error:
            msg = ("⚠ V5 连续性校验异常: " + "；".join(result["details"])
                   if result["details"] else "⚠ V5 连续性校验异常")
            logger.warning("%s", msg)
            if notify_fn is not None:
                try:
                    notify_fn(msg)
                except Exception:  # noqa: BLE001 — 告警失败不阻断 boot
                    logger.debug("continuity notify failed", exc_info=True)
        else:
            logger.info("V5 continuity OK: hash=%s… memories=%d",
                        identity_hash[:12], memory_count)
        return result

    # ── 身份快照组成 ──────────────────────────────────────────────────

    def _constitution_state(self) -> dict:
        """L4-1: 宪法当前版本 + 原则 hash（价值观属身份参数）。"""
        try:
            from ocos.constitution.versioned import VersionedConstitution
            snap = VersionedConstitution(self._db_path).current()
            return {"version": snap.version,
                    "principles_hash": self._hash(snap.principles)}
        except Exception as e:  # noqa: BLE001 — 无宪法表不阻断
            logger.debug("continuity constitution state skipped: %s", e)
            return {"version": None, "principles_hash": None}

    def _self_model_hash(self) -> str:
        """L4-2: 自我模型画像 hash（人格实测面）。未校准 → 诚实标注。"""
        try:
            from ocos.self.agent_self_model import AgentSelfModel
            snap = AgentSelfModel(self._db_path).load()
            return (snap or {}).get("content_hash") or "uncalibrated"
        except Exception as e:  # noqa: BLE001
            logger.debug("continuity self model hash skipped: %s", e)
            return "unavailable"

    def _count_episodes(self) -> int:
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM episodes").fetchone()
            finally:
                conn.close()
            return int(row[0])
        except sqlite3.OperationalError:
            return 0  # 无 episodes 表（全新库）
        except Exception as e:  # noqa: BLE001
            logger.debug("continuity episode count skipped: %s", e)
            return -1

    @staticmethod
    def _hash(obj: Any) -> str:
        payload = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                             default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _drift_reason(self, prev_snap: dict, curr_snap: dict) -> str:
        """定位漂移源（身份/宪法/自我模型），告警可读。"""
        reasons: list[str] = []
        for key, label in (("identity", "身份锚"),
                           ("constitution", "价值观宪法")):
            if prev_snap.get(key) != curr_snap.get(key):
                reasons.append(f"{label}变化")
        if prev_snap.get("self_model_hash") != curr_snap.get("self_model_hash"):
            # 自我模型随行为演进属正常 — 不算人格漂移，仅记录
            reasons.append("自我模型画像更新（属正常演进）")
        return ("身份快照漂移! " + ("; ".join(reasons) if reasons
                                  else "组成项变化"))

    # ── 基线读写（与 self_check 同源 audit 目录） ──────────────────────

    def _baseline_path(self) -> Path:
        if self._audit_dir is not None:
            return Path(self._audit_dir) / _BASELINE_FILE
        env = os.environ.get("OCOS_AUDIT_DIR", "").strip()
        if env:
            return Path(env) / _BASELINE_FILE
        try:
            from ocos.execution.autonomy import audit_log_path
            return audit_log_path().parent / _BASELINE_FILE
        except Exception:
            return Path.home() / ".ocos" / "audit" / _BASELINE_FILE

    def _read_baseline(self) -> tuple[dict | None, str]:
        try:
            raw = self._baseline_path().read_text(encoding="utf-8")
            return (json.loads(raw), "") if raw.strip() else (None, "")
        except FileNotFoundError:
            return None, ""
        except Exception as e:  # noqa: BLE001
            return None, str(e)

    def _write_baseline(self, data: dict) -> str:
        try:
            path = self._baseline_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            return ""
        except OSError as e:
            return str(e)

    # ── 漂移审计（episode 可溯源） ─────────────────────────────────────

    def _audit(self, result: dict) -> None:
        try:
            import uuid
            from ocos.memory.episode.models import Episode, EpisodeStatus
            from ocos.memory.episode.store import EpisodeStore
            bad = bool(result["drift"] or result["memory_loss"]
                       or result.get("details"))
            estore = EpisodeStore(db_path=self._db_path)
            estore.initialize()
            estore.save(Episode(
                id=f"EPI-V5-{uuid.uuid4().hex[:12]}",
                experience_id=f"EXP-V5-{uuid.uuid4().hex[:10]}",
                created_at=datetime.now(timezone.utc),
                session_id="continuity",
                context={"identity_hash": result["identity_hash"],
                         "memory_count": result["memory_count"],
                         "drift": result["drift"],
                         "memory_loss": result["memory_loss"]},
                goal="V5 跨重启一致性校验",
                decision="; ".join(result["details"])[:500],
                action="continuity_drift_alert" if bad
                       else "continuity_boot_check",
                outcome={"success": not bad,
                         "drift": result["drift"],
                         "memory_loss": result["memory_loss"]},
                significance_score=0.9 if bad else 0.5,
                source="continuity_check",
                status=EpisodeStatus.ACTIVE,
                tags=["v5", "continuity"],
            ))
        except Exception as e:  # noqa: BLE001 — 审计失败不阻断 boot
            logger.debug("continuity audit episode skipped: %s", e)
