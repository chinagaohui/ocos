"""Phase 23 — Gate 23-05: Phase Isolation 静态扫描。

验证 Phase 23 边界合规:
  23-016: 无 EpisodicMemory 导入
  23-017: 无 SelfModel 导入
  23-018: 无 Value 层导入
  23-019: 无传统 Workflow 引擎导入
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))


# ── Phase 23 模块路径列表 ───────────────────────────────────────────────────

PHASE23_OCOS_PATHS = [
    "ocos/capability/__init__.py",
    "ocos/capability/models.py",
    "ocos/capability/skill_registry.py",
    "ocos/capability/selector.py",
    "ocos/capability/skill_graph_executor.py",
    "ocos/capability/meta_controller.py",
]

# Phase 25+ 概念（Phase 23 不应包含）
FORBIDDEN_IMPORTS = [
    "episodic_memory",
    "EpisodicMemory",
    "self_model",
    "SelfModel",
    "value_layer",
    "ValueLayer",
    "narrative_engine",
    "NarrativeEngine",
    "temporal_reasoning",
    "TemporalReasoning",
    "personality_trait",
    "PersonalityTrait",
]

# 传统 Workflow 引擎
FORBIDDEN_WORKFLOW_IMPORTS = [
    "airflow",
    "prefect",
    "temporal_client",
    "celery",
    "dagster",
]


# ── 扫描函数 ────────────────────────────────────────────────────────────────


def _read_file_lines(path: str) -> list[str]:
    full_path = PROJECT / path
    if not full_path.is_file():
        return []
    return [line.strip() for line in full_path.read_text().splitlines()]


def _scan_files(
    paths: list[str], keywords: list[str]
) -> list[tuple[str, int, str]]:
    """扫描文件中的禁止关键词。返回 [(文件, 行号, 匹配行), ...]"""
    violations: list[tuple[str, int, str]] = []
    for path in paths:
        lines = _read_file_lines(path)
        for i, line in enumerate(lines, 1):
            # 跳过注释行和文档字符串
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            for kw in keywords:
                if kw in line:
                    violations.append((path, i, line.strip()))
                    break  # 每行只报告一次
    return violations


# ── 23-016: 无 EpisodicMemory ──────────────────────────────────────────────


def test_no_episodic_memory():
    """Phase 23 模块不应导入/引用 EpisodicMemory。"""
    violations = _scan_files(
        PHASE23_OCOS_PATHS,
        ["episodic_memory", "EpisodicMemory", "episode", "Episode"],
    )

    # 过滤元数据中的 "description" 字符串（非语义性引用）
    real_violations = [
        v for v in violations
        if "description" not in v[2] and "'" not in v[2]
    ]

    assert real_violations == [], (
        f"Phase 23 不应引用 EpisodicMemory: {real_violations}"
    )


# ── 23-017: 无 SelfModel ──────────────────────────────────────────────────


def test_no_self_model():
    """Phase 23 模块不应导入/引用 SelfModel。"""
    violations = _scan_files(
        PHASE23_OCOS_PATHS,
        ["self_model", "SelfModel", "self_concept", "SelfConcept"],
    )

    real_violations = [
        v for v in violations
        if "description" not in v[2]
    ]

    assert real_violations == [], (
        f"Phase 23 不应引用 SelfModel: {real_violations}"
    )


# ── 23-018: 无 Value 层 ───────────────────────────────────────────────────


def test_no_value_layer():
    """Phase 23 模块不应导入/引用 ValueLayer。"""
    violations = _scan_files(
        PHASE23_OCOS_PATHS,
        ["value_layer", "ValueLayer", "ValueSystem"],
    )

    assert violations == [], (
        f"Phase 23 不应引用 Value Layer: {violations}"
    )


# ── 23-019: 无传统 Workflow 引擎导入 ───────────────────────────────────────


def test_no_workflow_imports():
    """Phase 23 模块不应导入传统 Workflow 引擎。"""
    violations = _scan_files(
        PHASE23_OCOS_PATHS,
        FORBIDDEN_WORKFLOW_IMPORTS,
    )

    assert violations == [], (
        f"Phase 23 不应导入传统 Workflow 引擎: {violations}"
    )


# ── 额外: Phase 22 已有概念仍允许 ──────────────────────────────────────────


def test_phase22_imports_allowed():
    """Phase 23 可以引用 Phase 22 的 CognitiveBridge。"""
    violations = _scan_files(
        PHASE23_OCOS_PATHS,
        ["CognitiveBridge", "cognitive_bridge"],
    )
    # 允许 — 这是 Phase 22 的接口通过
    assert len(violations) > 0, (
        "Phase 23 应通过 CognitiveBridge 调用引擎"
    )
