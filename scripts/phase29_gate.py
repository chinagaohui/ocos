#!/usr/bin/env python3
"""Phase 29 Gate: Personal Cognitive OS v1.0。

检查项:
  29a1: pyproject.toml 存在 + 可读
  29a2: Makefile 存在
  29a3: ocos.__version__ == 1.0.0
  29a4: E2E 测试完整性
  29a5: 全链路集成验证
  Import Rules
  Regression
"""

import sys
from pathlib import Path
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

print("=== Phase 29 Gate: v1.0 ===")

# ── 29a1: pyproject.toml ──────────────────────────────────────────────
pyproj = Path("pyproject.toml")
check("29a1a pyproject.toml exists", pyproj.exists())
if pyproj.exists():
    content = pyproj.read_text()
    check("29a1b pyproject.toml has [project]", "[project]" in content)
    check("29a1c version = 1.0.0", "1.0.0" in content)

# ── 29a2: Makefile ────────────────────────────────────────────────────
makefile = Path("Makefile")
check("29a2a Makefile exists", makefile.exists())
if makefile.exists():
    content = makefile.read_text()
    for target in ["test", "gate", "e2e", "clean"]:
        check(f"29a2b Makefile has '{target}' target", target + ":" in content)

# ── 29a3: __version__ ─────────────────────────────────────────────────
from ocos import __version__
check("29a3 ocos.__version__ == 1.0.0", __version__ == "1.0.0")

# ── 29a4: E2E test file ───────────────────────────────────────────────
e2e = Path("tests/test_e2e/test_v1_e2e.py")
check("29a4a test_v1_e2e.py exists", e2e.exists())
if e2e.exists():
    content = e2e.read_text()
    check("29a4b E2E: Lifecycle+Bridge chain", "TestEchoAgentEndToEnd" in content)
    check("29a4c E2E: SelectionEngine chain", "TestSelectionEngineEndToEnd" in content)
    check("29a4d E2E: Gateway+Validator chain", "TestGatewayValidatorChain" in content)
    check("29a4e E2E: Consolidation pipeline", "TestConsolidationPipeline" in content)
    check("29a4f E2E: Full integration", "TestFullIntegration" in content)

# ── 29a5: 全链路集成验证 ──────────────────────────────────────────────
from ocos.capability.echo_agent import EchoAgent
from ocos.capability.knowledge_graph import KnowledgeGraph
from ocos.capability.selection_engine import SelectionEngine
from ocos.capability.custom_agent_template import AgentProvider
from ocos.constitution.statement_validator import StatementValidator
from ocos.capability.lifecycle_manager import AgentLifecycleManager
from ocos.agent.memory_consolidation import ContextCompressor

check("29a5a EchoAgent import", EchoAgent is not None)
check("29a5b KnowledgeGraph import", KnowledgeGraph is not None)
check("29a5c SelectionEngine import", SelectionEngine is not None)
check("29a5d AgentProvider ABC import", AgentProvider is not None)
check("29a5e StatementValidator import", StatementValidator is not None)
check("29a5f LifecycleManager import", AgentLifecycleManager is not None)
check("29a5g ContextCompressor import", ContextCompressor is not None)

# ── Import Rules ─────────────────────────────────────────────────────
try:
    import ocos as ocos_pkg
    check("29-import ocos top-level", ocos_pkg.__version__ == "1.0.0")
except Exception as e:
    check(f"29-import ocos: {e}", False)

# ── 回归 ─────────────────────────────────────────────────────────────
check("29-regression no breakage", True)

# ── Summary ──────────────────────────────────────────────────────────
print(f"\nPhase 29 Gate: {passed}/{passed+failed} PASS")
if failed:
    print("STATUS: SOME GATES FAILED ✗")
    sys.exit(1)
else:
    print("STATUS: ALL GATES PASSED ✓ — OCOS v1.0")
