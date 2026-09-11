"""Single-Path Production Verification — 认知运行时单主链收敛验证（收敛裁决 P4）。

依据 docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md（FROZEN DECISION）：
  - 冻结令 1: AgentRuntime 是唯一 Cognitive Runtime Host
  - 冻结令 2: DecisionBridge 是生产 Decision/Mutation Authority
  - 冻结令 3: OCOS_ENABLE_COGNITIVE_LOOP 在 Migration 完成前禁止
  - R2: Learning/Consolidation 编排宿主 = daemon 侧 ConsolidationService
  - R3: LifeCycleOrchestrator 已 MERGE 后 ARCHIVE

运行: pytest ocos/tests/test_single_path_convergence_20260908.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

OCOS_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = OCOS_DIR / "_archive"


# ── 冻结令 3: 旧认知循环默认关闭 ─────────────────────────────────────


def test_cognitive_loop_switch_defaults_to_off():
    """P0-C (2026-09-11): OCOS_ENABLE_COGNITIVE_LOOP 开关必须被删除.

    冻结令 3 升级: 从"默认关闭"升级为"开关不存在".
    任何 os.environ.get("OCOS_ENABLE_COGNITIVE_LOOP") 出现都违反 P1 —
    不允许通过环境变量恢复旧 CognitiveLoop Runtime.
    legacy fallback 已永久 _enable_cognitive_loop = False,
    任何 Observe/Recall/Think/Reflect 必须 re-host 到 AgentRuntime 主链.
    """
    src = (OCOS_DIR / "agent" / "agent_runtime.py").read_text(encoding="utf-8")
    # P0-C: 开关已删除 — 代码里不应出现任何 OCOS_ENABLE_COGNITIVE_LOOP 字符串
    assert "OCOS_ENABLE_COGNITIVE_LOOP" not in src, (
        "OCOS_ENABLE_COGNITIVE_LOOP 开关仍存在 — P1 单一 Runtime 原则违规 "
        "(删除环境变量开关, legacy fallback 永久 disable)")
    # legacy fallback 必须硬编码 disable
    assert "_enable_cognitive_loop = False" in src, (
        "legacy cognitive loop fallback 必须永久 disable")


def test_archive_modules_not_importable_from_production():
    """归档命名空间不得被任何生产文件 import（违冻条款）。"""
    prod_files = [
        p for p in OCOS_DIR.rglob("*.py")
        if not str(p).startswith(str(ARCHIVE_DIR))
        and "tests" not in str(p)
        and p.name != "__init__.py"
    ]
    offenders = []
    for p in prod_files:
        src = p.read_text(encoding="utf-8", errors="ignore")
        if "_archive" in src:
            tree = ast.parse(src, filename=str(p))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = getattr(node, "module", "") or ""
                    names = [a.name for a in node.names]
                    hits = [mod] + names if mod else names
                    # 精确匹配 ocos._archive 命名空间（event_archive 等同名
                    # 子串不算）
                    if any(h == "ocos._archive"
                           or h.startswith("ocos._archive.") for h in hits):
                        offenders.append(f"{p.relative_to(OCOS_DIR)}")
    assert offenders == [], f"生产文件 import 归档模块: {offenders}"


# ── 冻结令 1 / R3: 唯一宿主与编排层收敛 ─────────────────────────────


def test_lifecycle_orchestrator_archived():
    """R3 裁决: LifeCycleOrchestrator 已 MERGE 后 ARCHIVE。"""
    assert not (OCOS_DIR / "agent" / "life_cycle_orchestrator.py").exists()
    assert (ARCHIVE_DIR / "agent" / "life_cycle_orchestrator.py").exists()
    daemon_src = (OCOS_DIR / "daemon" / "__init__.py").read_text(encoding="utf-8")
    # 只查真实依赖（import / 实例化），历史注释提及不算
    assert "from ocos.agent.life_cycle_orchestrator import" not in daemon_src, (
        "daemon 仍 import 已归档的 LifeCycleOrchestrator")
    assert "LifeCycleOrchestrator(" not in daemon_src, (
        "daemon 仍实例化已归档的 LifeCycleOrchestrator")


def test_dream_orchestration_hosted_by_consolidation_service():
    """R2 裁决: dream 巩固触发编排宿主 = ConsolidationService（daemon 层）。

    daemon 不再内联 sleep/dream 调用序列（原 _run_dream_cycle 已迁出），
    统一经 _consolidate() 委托 service。
    """
    daemon_src = (OCOS_DIR / "daemon" / "__init__.py").read_text(encoding="utf-8")
    assert "agent_obj.dream()" not in daemon_src, (
        "daemon 内联 dream 调用应迁入 ConsolidationService")
    service = (OCOS_DIR / "daemon" / "consolidation_service.py").read_text(
        encoding="utf-8")
    assert "def run_dream_cycle" in service
    assert "persist_latest_rules" in service  # 学习规则持久化语义在 service
    assert "def _synthesize_skills" in service  # 技能合成语义在 service


def test_runtime_package_governance_intact():
    """Phase 39 Governance Freeze: ocos/runtime 不 import ocos.agent。

    ConsolidationService 曾误宿主 runtime 层触发本守卫 — 已迁 daemon 层。
    本测试固化该治理边界，防 RE-HOST 第二段迁移时越界。
    """
    runtime_dir = OCOS_DIR / "runtime"
    for p in runtime_dir.rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module != "ocos.agent" \
                    and not node.module.startswith("ocos.agent."), (
                    f"runtime 包出现 agent 依赖: {p}")
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name != "ocos.agent" \
                        and not a.name.startswith("ocos.agent."), (
                        f"runtime 包出现 agent 依赖: {p}")


# ── 冻结令 2: Decision/Mutation Authority 在位 ───────────────────────


def test_decision_bridge_authority_wiring_present():
    """冻结令 2: DecisionBridge 治理装配点存在（PermissionGuard/审批/宪法）。"""
    bridge_src = (OCOS_DIR / "execution" / "bridge.py").read_text(
        encoding="utf-8")
    assert "PermissionGuard" in bridge_src or "permission_guard" in bridge_src
    factory_src = (OCOS_DIR / "daemon" / "factory.py").read_text(
        encoding="utf-8")
    assert "PendingStore" in factory_src  # ASK 待批队列持久化
    assert "BehavioralConstitution" in factory_src  # 行为宪法装配
