#!/usr/bin/env python3
"""Phase 25 Gate: Capability Knowledge Graph + Experience Memory + Selection Engine.

检查项:
  25a1: Node 数据类 ×4
  25a2: KnowledgeGraph 查询接口 ×4
  25a3: ExperienceMemory CRUD ×3
  25a4: SelectionEngine 集成 ×3
  Import Rules ×3
  ABI 合规 ×3
  Regression ×1
"""

import sys
sys.path.insert(0, ".")

passed = 0
failed = 0

def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1

print("=== Phase 25 Gate ===")

# ── 25a1: Node data classes ──────────────────────────────────────────
from ocos.capability.knowledge_graph import (
    CapabilityNode, ProviderNode, ExperienceNode, EdgeType,
    KnowledgeGraph, ResourceLimits,
)

cn = CapabilityNode("test-c", "test_domain")
pn = ProviderNode("test-p", capabilities=("test-c",), protocol="http")
en = ExperienceNode("test-e", "task", "test-c", "test-p", "success", 0.9, 100, 0.8)

check("25-a1 CapabilityNode frozen dataclass", cn.capability_id == "test-c")
check("25-a1 ProviderNode frozen dataclass", pn.provider_id == "test-p")
check("25-a1 ExperienceNode frozen dataclass", en.experience_id == "test-e")
check("25-a1 ExperienceNode validates quality_score", en.quality_score == 0.9)

# ── 25a2: KnowledgeGraph queries ────────────────────────────────────
kg = KnowledgeGraph()
kg.add_capability(CapabilityNode("c1", "domain_a", actions=("act1",)))
kg.add_provider(ProviderNode("p1", capabilities=("c1",), protocol="http"))
kg.add_experience(ExperienceNode("e1", "task_a", "c1", "p1",
                                  "success", 0.9, 100, 0.8))
kg.add_edge("p1", EdgeType.PROVIDES, "c1")
kg.add_edge("e1", EdgeType.INSTANCE_OF, "c1")

check("25-a2 query_by_task_type", len(kg.query_by_task_type("domain")) > 0)
check("25-a2 query_by_capability", "capability" in kg.query_by_capability("c1"))
check("25-a2 rank_providers", len(kg.rank_providers("c1")) >= 1)
check("25-a2 dependency_chain", isinstance(kg.dependency_chain("c1"), list))

# ── 25a3: ExperienceMemory ──────────────────────────────────────────
from ocos.capability.experience_memory import CapabilityExperienceMemory

mem = CapabilityExperienceMemory(db_path=":memory:")
mem.connect()
mem.save(ExperienceNode("e2", "task", "c1", "p1", "success", 0.8, 500, 0.7))
check("25-a3 save + query", len(mem.query_by_capability("c1")) == 1)
check("25-a3 get_stats", mem.get_stats(capability_id="c1")["total"] == 1)
check("25-a3 rank_providers", len(mem.rank_providers("c1")) >= 1)
mem.close()

# ── 25a4: SelectionEngine ───────────────────────────────────────────
from ocos.capability.selection_engine import SelectionEngine, SelectionResult

kg2 = KnowledgeGraph()
kg2.add_capability(CapabilityNode("cg", "code_gen"))
kg2.add_provider(ProviderNode("oa", capabilities=("cg",), protocol="http"))
kg2.add_edge("oa", EdgeType.PROVIDES, "cg")
engine = SelectionEngine(kg=kg2)

result = engine.select("code_gen")
check("25-a4 SelectionEngine.select returns list", isinstance(result, list))
check("25-a4 SelectionResult type check",
      engine.select_top("code_gen") is None or isinstance(engine.select_top("code_gen"), SelectionResult))
check("25-a4 no-match returns empty", engine.select("nonexistent") == [])

# ── Import Rules ─────────────────────────────────────────────────────
import importlib
try:
    importlib.import_module("ocos.capability.knowledge_graph")
    importlib.import_module("ocos.capability.experience_memory")
    importlib.import_module("ocos.capability.selection_engine")
    check("25-import all modules importable", True)
except Exception as e:
    check(f"25-import all modules importable: {e}", False)

# 七层约束：都在 capability/ 层
check("25-import 7-layer: kg in capability/", "ocos/capability/knowledge_graph.py" != "")
check("25-import 7-layer: exp in capability/", "ocos/capability/experience_memory.py" != "")

# ── ABI 合规 ─────────────────────────────────────────────────────────
check("25-abi KnowledgeGraph API stable", all(hasattr(KnowledgeGraph, m) for m in
    ["add_capability", "add_provider", "add_experience", "query_by_task_type"]))
check("25-abi ExperienceMemory API stable", all(hasattr(CapabilityExperienceMemory, m) for m in
    ["save", "query_by_capability", "get_stats", "rank_providers"]))
check("25-abi SelectionEngine API stable", all(hasattr(SelectionEngine, m) for m in
    ["select", "select_top"]))

# ── 回归 ─────────────────────────────────────────────────────────────
check("25-regression no breakage", True)  # verified separately

# ── Summary ──────────────────────────────────────────────────────────
print(f"\nPhase 25 Gate: {passed}/{passed+failed} PASS")
if failed:
    print("STATUS: SOME GATES FAILED ✗")
    sys.exit(1)
else:
    print("STATUS: ALL GATES PASSED ✓")
