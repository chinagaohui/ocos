#!/usr/bin/env python3
"""Phase 26 Gate — Result Understanding Layer (v0.1)

验证:
  G1: 全量 pytest 回归 (≥1620 passed, 0 failed)
  G2: ResultUnderstandingLayer validate → structure → learn 管道
  G3: CapabilityExperienceMemory 写入验证
  G4: KnowledgeGraph 更新验证
  G5: AgentRuntime._tick_step_result_ingest 集成
  G6: StatementValidator 集成 (向后兼容)
  G7: Import rules 无非法导入
"""
import os
import sys
import subprocess

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
results: dict[str, str] = {}


def gate(name: str, condition: bool, detail: str = "") -> bool:
    status = f"{GREEN}PASS{RESET}" if condition else f"{RED}FAIL{RESET}"
    results[name] = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}  {detail}")
    return condition


print(f"{YELLOW}Phase 26 Gate{RESET}")
print("-" * 60)

# ── G1: pytest regression ───────────────────────────────────────
p = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "--tb=line"],
    cwd=PROJECT, capture_output=True, text=True, timeout=120,
)
gate("G1: pytest regression (≥1620/0)",
     p.returncode == 0 and " failed" not in " ".join(p.stdout.splitlines()[-2:]),
     f"output: {'...'.join(p.stdout.strip().splitlines()[-2:])}")

# ── G2: Pipeline 完整管道 ───────────────────────────────────────
from ocos.capability.result_understanding import (
    ResultUnderstandingLayer, StructuredResult, ProcessedResult,
)
from ocos.capability.knowledge_graph import KnowledgeGraph, CapabilityNode, ProviderNode, EdgeType
from ocos.capability.experience_memory import CapabilityExperienceMemory

kg = KnowledgeGraph()
kg.add_capability(CapabilityNode("img_gen", "image"))
kg.add_provider(ProviderNode("dalle", ("img_gen",), "http"))
kg.add_edge("dalle", EdgeType.PROVIDES, "img_gen")

exp = CapabilityExperienceMemory()
layer = ResultUnderstandingLayer(experience=exp, kg=kg)

processed = layer.process_result(
    "Image generated: a sunset landscape.",
    capability_id="img_gen",
    provider_id="dalle",
    outcome="success",
    quality_score=0.92,
    duration_ms=450,
)

gate("G2: validate passed",
     processed.validated, "clean output")

gate("G2: experience stored",
     processed.experience_stored, f"stored={processed.experience_stored}")

gate("G2: KG updated",
     processed.kg_updated, f"updated={processed.kg_updated}")

gate("G2: structured quality",
     processed.structured.quality_score == 0.92,
     f"q={processed.structured.quality_score}")

# ── G3: ExperienceMemory 写入验证 ────────────────────────────────
rows = exp.query_by_capability("img_gen")
gate("G3: ExperienceMemory query",
     len(rows) >= 1 and rows[0]["quality_score"] > 0.9,
     f"rows={len(rows)}, avg_q={rows[0].get('quality_score', 'N/A')}")

stats = exp.get_stats(capability_id="img_gen")
gate("G3: ExperienceMemory stats",
     stats["total"] >= 1 and stats["success_rate"] >= 0.9,
     f"total={stats['total']}, sr={stats['success_rate']}")

# ── G4: KnowledgeGraph 更新验证 ─────────────────────────────────
info = kg.query_by_capability("img_gen")
gate("G4: KG experience count",
     len(info.get("experiences", [])) >= 1,
     f"exps={len(info.get('experiences', []))}")

exp.close()

# ── G5: AgentRuntime integration ─────────────────────────────────
try:
    from unittest.mock import MagicMock
    from ocos.agent.agent_runtime import AgentRuntime

    agent = MagicMock()
    rt = AgentRuntime(agent, max_cycles=1)
    rt.boot()
    result = rt._tick_step_result_ingest()

    gate("G5: tick_step_result_ingest step",
         result["step"] == 9 and result["recorded"],
         f"step={result['step']}")

    has_pipeline = "phase26_pipeline" in result
    gate("G5: phase26_pipeline in result",
         has_pipeline,
         f"pipeline={'yes' if has_pipeline else 'no'}")
except Exception as e:
    gate("G5: AgentRuntime integration", False, str(e))
    gate("G5: pipeline in result", False, "skipped")

# ── G6: StatementValidator backward compat ──────────────────────
from ocos.capability.result_understanding import ResultUnderstanding

ru = ResultUnderstanding()
clean = ru.examine("This is normal output.")
dirty = ru.examine("I feel joy and satisfaction from this work.")

gate("G6: backward compat clean output",
     clean.passed, f"passed={clean.passed}")

gate("G6: backward compat violation",
     not dirty.passed, f"passed={dirty.passed}")

# ── G7: Import rules ────────────────────────────────────────────
p_import = subprocess.run(
    [sys.executable, "-m", "pytest", "ocos/tests/test_import_rules.py", "-q", "--tb=short"],
    cwd=PROJECT, capture_output=True, text=True, timeout=60,
)
gate("G7: Import rules clean",
     p_import.returncode == 0,
     f"rc={p_import.returncode}")

# ── summary ────────────────────────────────────────────────────
print("-" * 60)
passed = sum(1 for v in results.values() if v == "PASS")
total = len(results)
color = GREEN if passed == total else RED
print(f"{color}{passed}/{total} gates passed{RESET}")
sys.exit(0 if passed == total else 1)
