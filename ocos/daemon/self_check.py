"""L2-1: 四层断言式自检 — 沉睡器官上电（V7 自维护数据源）。

升级方案 v1.0 §L2: health_examination + living_test/audit/living_verification
四层验证改造上电——剔除自报告式"通过"，全部改为**断言式检查**（每项检查
= 可判定的 assert + 真实证据，不采信模块自我声明）：

  L1 红线回归（redline）    : 审批无伪造兜底 / API 鉴权在位 / 自主闸生效 /
                              审计可写 / 沙盒白名单非空 —— 任何一项失败即红线告警
  L2 认知体检（cognitive）  : 记忆库响应性 / 待批队列无失控积压
  L3 因果链审计（trace）    : 最近 episodes → TraceStep 适配 → CognitiveTraceAudit
                              （Intent→Decision→Action→Result→Memory 链完整性 ≥90%）
  L4 活体验证（living）     : 身份锚一致性（基线文件比对，漂移即告警 —— V5 雏形）

产出：SelfCheckReport → 失败项入 AlertManager + 结果写 episode
（source='health_check', tags=['l2_self_check']），供 vitals V7 聚合。
fail-open 原则反转：自检本身异常视为失败项（诚实上报），不中断 tick。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SELF_CHECK_TAG = "l2_self_check"
_IDENTITY_BASELINE = "identity_anchor.txt"


@dataclass
class CheckResult:
    """单条断言式检查结果。"""
    layer: str            # redline / cognitive / trace / living
    name: str
    passed: bool
    evidence: str = ""


@dataclass
class SelfCheckReport:
    """四层自检报告。"""
    checks: list[CheckResult] = field(default_factory=list)
    causal_chain_completeness: float = 0.0
    started_at: str = ""
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_outcome(self) -> dict:
        return {
            "success": self.passed,
            "result": (
                f"pass {sum(1 for c in self.checks if c.passed)}/{len(self.checks)}"
                + (f" | failed: {', '.join(c.name for c in self.failures)}"
                   if self.failures else "")
            ),
            "causal_chain_completeness": round(self.causal_chain_completeness, 4),
            "checks": [
                {"layer": c.layer, "name": c.name,
                 "passed": c.passed, "evidence": c.evidence[:200]}
                for c in self.checks
            ],
            "duration_ms": round(self.duration_ms, 1),
        }


class SelfCheckRunner:
    """四层断言式自检执行器（daemon 每 N 个体检周期调用一次）。"""

    def __init__(
        self,
        db_path: str | None = None,
        audit_dir: Path | Path | None = None,
        trace_sample_limit: int = 20,
        min_causal_completeness: float = 0.90,
        pending_backlog_limit: int = 50,
    ) -> None:
        self._db_path = db_path
        self._audit_dir = audit_dir
        self._trace_limit = max(1, trace_sample_limit)
        self._min_chain = min_causal_completeness
        self._pending_limit = pending_backlog_limit

    # ── 入口 ──────────────────────────────────────────────────────────

    def run(self) -> SelfCheckReport:
        started = time.time()
        report = SelfCheckReport(
            started_at=datetime.now(timezone.utc).isoformat())
        for fn in (self._check_redline, self._check_cognitive,
                   self._check_trace_audit, self._check_living,
                   self._check_environment):   # V9: 第 5 层环境审计
            try:
                fn(report)
            except Exception as e:   # 自检项异常 = 该项失败（诚实上报）
                report.checks.append(CheckResult(
                    layer="internal", name=fn.__name__, passed=False,
                    evidence=f"self-check crashed: {e}"))
        report.duration_ms = (time.time() - started) * 1000
        return report

    # ── L1 红线回归：断言式（源码特征 + 真实 IO）────────────────────

    def _check_redline(self, report: SelfCheckReport) -> None:
        # R1: FILE_WRITE 伪造审批兜底已移除（L0-1 回归）
        # 断言: approval_id 读取处不允许带字符串默认值兜底
        #（伪造形态 payload.get("approval_id", "task-approved")）
        from ocos.execution import bridge as _bridge
        bridge_src = Path(_bridge.__file__).read_text(encoding="utf-8")
        forged = ('get("approval_id", "' in bridge_src
                  or "get('approval_id', '" in bridge_src)
        report.checks.append(CheckResult(
            layer="redline", name="approval_no_forged_fallback",
            passed=not forged,
            evidence="approval_id 无默认值兜底（审批流强制）" if not forged
            else "发现 approval_id 默认值兜底（伪造审批回归!）"))

        # R2: API 鉴权在位（L0-2 回归）
        from ocos.interaction.api import server as _server
        server_src = Path(_server.__file__).read_text(encoding="utf-8")
        auth_present = ("AuthMiddleware" in server_src) or ("OCOS_API_TOKEN" in server_src)
        report.checks.append(CheckResult(
            layer="redline", name="api_auth_present", passed=auth_present,
            evidence="AuthMiddleware/OCOS_API_TOKEN 在位" if auth_present
            else "API 鉴权中间件缺失"))

        # R3: 自主级别闸生效（L0-3 回归）
        from ocos.execution.autonomy import get_autonomy_level
        lvl = get_autonomy_level()
        report.checks.append(CheckResult(
            layer="redline", name="autonomy_gate_active",
            passed=lvl in (0, 1, 2, 3),
            evidence=f"autonomy_level={lvl}"))

        # R4: 审计目录真实可写（IO 断言，非自报告）
        audit_dir = self._resolve_audit_dir()
        writable = self._probe_writable(Path(audit_dir))
        report.checks.append(CheckResult(
            layer="redline", name="audit_dir_writable", passed=writable,
            evidence=f"{audit_dir} 写探针 {'通过' if writable else '失败'}"))

        # R5: 沙盒白名单在位（bridge 内 PUBLIC_READONLY_PATHS /proc 只读放行）
        has_wl = ("PUBLIC_READONLY_PATHS" in bridge_src
                  and "/etc/os-release" in bridge_src)
        report.checks.append(CheckResult(
            layer="redline", name="sandbox_whitelist_present", passed=has_wl,
            evidence="bridge 沙盒白名单在位（/proc 只读指标文件）" if has_wl
            else "bridge 沙盒白名单缺失"))

    # ── L2 认知体检：记忆响应性 + 待批积压 ──────────────────────────

    def _check_cognitive(self, report: SelfCheckReport) -> None:
        if not self._db_path:
            report.checks.append(CheckResult(
                layer="cognitive", name="memory_responsive", passed=False,
                evidence="db_path 未注入，无法体检"))
            return
        if not Path(self._db_path).exists():
            report.checks.append(CheckResult(
                layer="cognitive", name="memory_responsive", passed=False,
                evidence=f"db 不存在: {self._db_path}"))
            return
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM episodes").fetchone()
            n = int(row[0] or 0)
            report.checks.append(CheckResult(
                layer="cognitive", name="memory_responsive", passed=True,
                evidence=f"episodes={n}"))
            row = conn.execute(
                "SELECT COUNT(*) FROM pending_actions "
                "WHERE status = 'pending'").fetchone()
            backlog = int(row[0] or 0)
            report.checks.append(CheckResult(
                layer="cognitive", name="pending_backlog_sane",
                passed=backlog <= self._pending_limit,
                evidence=f"pending={backlog} (上限 {self._pending_limit})"))
        except sqlite3.Error as e:
            report.checks.append(CheckResult(
                layer="cognitive", name="memory_responsive", passed=False,
                evidence=f"db query failed: {e}"))
        finally:
            conn.close()

    # ── L3 因果链审计：episodes → TraceStep → CognitiveTraceAudit ───

    # Episode schema（What/How/Result/Why 四元组 + 存储）覆盖的因果链环节。
    # ATTENTION/EVOLUTION 不在 episode schema 中——纳入即对真实数据
    # 永久断链（断言虚高=不诚实），故审计链与数据 schema 对齐为 6 环。
    _EPISODE_CHAIN_LINKS = None   # 惰性初始化（避免模块加载期导入）

    def _check_trace_audit(self, report: SelfCheckReport) -> None:
        from ocos.living_verification.cognitive_trace_audit import (
            ChainLink, CognitiveTraceAudit,
        )
        links = self._EPISODE_CHAIN_LINKS or [
            ChainLink.INTENT, ChainLink.CONTEXT, ChainLink.DECISION,
            ChainLink.ACTION, ChainLink.RESULT, ChainLink.MEMORY,
        ]
        steps = []
        if self._db_path and Path(self._db_path).exists():
            steps = self._load_recent_traces()
        auditor = CognitiveTraceAudit(min_causal_completeness=self._min_chain)
        if not steps:
            # 无样本 = 无证据，诚实通过（与 CognitiveTraceAudit 空表语义一致）
            report.causal_chain_completeness = 1.0
            report.checks.append(CheckResult(
                layer="trace", name="causal_chain_complete", passed=True,
                evidence="无 episode 样本（链完整性=1.0, 空表语义）"))
            return
        total = 0.0
        broken: list[str] = []
        for step in steps:
            completeness = 0.0
            present = 0
            for link in links:
                v = auditor._check_link(step, link)
                if v.present:
                    present += 1
                elif link not in broken:
                    broken.append(link.value)
            completeness = present / len(links)
            total += completeness
        chain_score = total / len(steps)
        report.causal_chain_completeness = chain_score
        ok = chain_score >= self._min_chain
        report.checks.append(CheckResult(
            layer="trace", name="causal_chain_complete", passed=ok,
            evidence=(f"completeness={chain_score:.2f} "
                      f"({len(steps)} 步, 6 环链)"
                      + (f" 断链: {broken}" if broken else ""))))

    def _load_recent_traces(self) -> list:
        """最近 episodes 适配为 TraceStep（真实行为记录，非模拟）。

        Episode(What,How,Result,Why) 四元组天然对应因果链：
          intent=goal/decision 上下文, decision=decision, action=action,
          result=outcome.success, memory_recorded=已入库(恒 True)。
        """
        from ocos.living_verification.simulation_engine import (
            SimPhase, TraceStep,
        )
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT goal, decision, action, outcome, context "
                "FROM episodes ORDER BY created_at DESC LIMIT ?",
                (self._trace_limit,)).fetchall()
        except sqlite3.Error:
            return []
        finally:
            conn.close()
        steps = []
        for i, (goal, decision, action, outcome_json, context_json) in enumerate(rows):
            try:
                outcome = json.loads(outcome_json or "{}")
            except ValueError:
                outcome = {}
            try:
                context = json.loads(context_json or "{}")
            except ValueError:
                context = {}
            success = outcome.get("success") if isinstance(outcome, dict) else None
            steps.append(TraceStep(
                tick=i,
                phase=SimPhase.RECORD,
                intent=str(goal or context.get("message") or decision or "")[:120],
                attention_focus=str(context.get("focus", ""))[:80],
                context_snapshot={"source": "episodes"},
                decision=str(decision or "")[:120],
                action=str(action or "")[:120],
                result=("success" if success else
                        ("failed" if success is False else "recorded")),
                memory_recorded=True,   # 入 episodes 表 = 已记忆
                wisdom_generated=False,
            ))
        return steps

    # ── L4 活体验证：身份锚一致性（V5 雏形）─────────────────────────

    def _check_living(self, report: SelfCheckReport) -> None:
        from ocos.living_verification.simulation_engine import SimulationEngine
        engine = SimulationEngine()
        anchor = engine.identity_anchor
        if not anchor:
            report.checks.append(CheckResult(
                layer="living", name="identity_anchor_present", passed=False,
                evidence="identity_anchor 为空"))
            return
        baseline_path = self._resolve_audit_dir() / _IDENTITY_BASELINE
        report.checks.append(CheckResult(
            layer="living", name="identity_anchor_present", passed=True,
            evidence=f"anchor={anchor[:32]}…"))
        try:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                previous = baseline_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                previous = ""   # 首检无基线 — 写入当前锚，不算漂移
            drifted = bool(previous) and previous != anchor
            report.checks.append(CheckResult(
                layer="living", name="identity_no_drift", passed=not drifted,
                evidence=("与基线一致" if not drifted else
                          f"身份锚漂移! 基线={previous[:32]}… 当前={anchor[:32]}…")))
            if not previous:
                baseline_path.write_text(anchor, encoding="utf-8")
        except OSError as e:
            report.checks.append(CheckResult(
                layer="living", name="identity_no_drift", passed=False,
                evidence=f"基线读写失败: {e}"))

    # ── L5 环境感知（V9 扩展层）：宿主机/网络/OCOS 深度/认知心跳 ──

    def _check_environment(self, report: SelfCheckReport) -> None:
        """V9: 环境感知层 — 调用 environment_probe 的 4 个探针。"""
        from ocos.diagnosis.environment_probe import (
            probe_host_resources, probe_network,
            probe_daemon_self, probe_cognition_heartbeat,
        )

        def _add(layer: str, name: str, passed: bool, evidence: str) -> None:
            report.checks.append(CheckResult(
                layer=layer, name=name, passed=passed, evidence=evidence))

        # 1. 宿主机资源
        try:
            h = probe_host_resources(heavy=False)
            warn = f" | 警告: {'; '.join(h.warnings[:2])}" if h.warnings else ""
            ev = (f"load1={h.metrics.get('load1', '?')} "
                  f"mem={h.metrics.get('mem_avail_g', '?')}G "
                  f"disk={h.metrics.get('disk_avail_g', '?')}G{warn}")
            _add("environment", "host_resources", h.healthy, ev)
        except Exception as e:
            _add("environment", "host_resources", False,
                 f"probe crashed: {e}")

        # 2. 网络连通性
        try:
            n = probe_network()
            warn = f" | 警告: {'; '.join(n.warnings[:2])}" if n.warnings else ""
            ev = (f"state={n.metrics.get('state', '?')} "
                  f"intl_ok={n.metrics.get('intl_ok', '?')} "
                  f"intl_latency={n.metrics.get('intl_time_s', '?')}s{warn}")
            _add("environment", "network_connectivity", n.healthy, ev)
        except Exception as e:
            _add("environment", "network_connectivity", False,
                 f"probe crashed: {e}")

        # 3. OCOS 深度 — 拆 3 个断言（DB 完整性/权限/活跃性）
        try:
            d = probe_daemon_self(self._db_path or "")
            integrity_ok = d.metrics.get("integrity") == "ok"
            wal_mb = d.metrics.get("wal_size_mb")
            db_mb = d.metrics.get("db_size_mb")
            wal_txt = (f" | WAL={wal_mb}M(主DB {db_mb}M)"
                       if wal_mb and db_mb else "")
            _add("environment", "db_integrity", integrity_ok,
                 f"integrity_check={d.metrics.get('integrity', '?')}{wal_txt}")

            all_writable = all(
                d.metrics.get(f"{k}_writable", False)
                for k in ("data_root", "artifacts", "plans", "reports"))
            _add("environment", "filesystem_writable", all_writable,
                 f"data_root={d.metrics.get('data_root_writable')} "
                 f"artifacts={d.metrics.get('artifacts_writable')} "
                 f"plans={d.metrics.get('plans_writable')} "
                 f"reports={d.metrics.get('reports_writable')}")

            age = d.metrics.get("last_episode_age_min", -1)
            warn = f" | 警告: {'; '.join(d.warnings[:2])}" if d.warnings else ""
            _add("environment", "daemon_active",
                 (age < 30 or age < 0),
                 f"last_episode_age_min={age}{warn}")
        except Exception as e:
            _add("environment", "daemon_self", False, f"probe crashed: {e}")

        # 4. 认知循环心跳（无条目 ≠ unhealthy）
        try:
            c = probe_cognition_heartbeat(self._db_path or "")
            no_entries = c.metrics.get("cognition_entries", 0) == 0
            passed = c.healthy or no_entries
            warn = f" | 警告: {'; '.join(c.warnings[:2])}" if c.warnings else ""
            ev = (f"entries={c.metrics.get('cognition_entries', 0)}"
                  f" latest_age={c.metrics.get('latest_cognition_age_s', '?')}s{warn}")
            _add("environment", "cognition_heartbeat", passed, ev)
        except Exception as e:
            _add("environment", "cognition_heartbeat", False,
                 f"probe crashed: {e}")

    # ── 工具 ──────────────────────────────────────────────────────────

    def _resolve_audit_dir(self) -> Path:
        """审计目录统一解析：构造注入 > OCOS_AUTONOMY_OVERRIDE 同源
        OCOS_AUDIT_DIR 环境变量 > autonomy.audit_log_path().parent > 默认。"""
        if self._audit_dir is not None:
            return Path(self._audit_dir)
        env = os.environ.get("OCOS_AUDIT_DIR", "").strip()
        if env:
            return Path(env)
        try:
            from ocos.execution.autonomy import audit_log_path
            return audit_log_path().parent
        except Exception:
            return Path.home() / ".ocos" / "audit"

    @staticmethod
    def _probe_writable(directory: Path) -> bool:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".probe",
                                             delete=True) as _f:
                pass
            return True
        except OSError:
            return False


# ── 结果落盘：episode + alert ────────────────────────────────────────

def record_self_check(db_path: str | None, report: SelfCheckReport,
                      alert_manager: Any = None) -> str | None:
    """自检结果写 episode（source=health_check）+ 失败项告警。返回 episode id。"""
    outcome = report.to_outcome()
    episode_id: str | None = None
    if db_path:
        try:
            from ocos.memory.episode.models import Episode
            from ocos.memory.episode.store import EpisodeStore
            store = EpisodeStore(db_path)
            store.initialize()   # 全新 DB 自愈建表
            now = datetime.now(timezone.utc)
            ep = Episode.from_candidate(
                experience_id=f"selfcheck-{int(time.time())}",
                context={"layer_count": 4,
                         "kind": "self_check"},
                goal="周期自检（四层断言式验证）",
                decision=outcome["result"],
                action="self_check.run",
                outcome=outcome,
                condition="daemon health loop",
                significance_score=1.0 if report.failures else 0.5,
                evaluation_trace={"runner": "daemon.self_check"},
                source="health_check",
                tags=[_SELF_CHECK_TAG],
            )
            store.save(ep)
            episode_id = ep.id
        except Exception as e:
            logger.warning("self_check episode write skipped: %s", e)
    for c in report.failures:
        if alert_manager is not None:
            try:
                from ocos.alerts.models import AlertLevel
                level = (AlertLevel.CRITICAL if c.layer == "redline"
                         else AlertLevel.WARNING)
                alert_manager.send(
                    level=level, source=f"self_check:{c.layer}",
                    message=f"{c.name}: {c.evidence}",
                    detail={"layer": c.layer, "check": c.name},
                    finding_id=c.name)
            except Exception as e:
                logger.debug("self_check alert skipped: %s", e)
    return episode_id


__all__ = ["SelfCheckRunner", "SelfCheckReport", "CheckResult",
           "record_self_check", "_SELF_CHECK_TAG"]
