#!/usr/bin/env python3
"""Phase 24 Gate: Cognitive Sovereignty & Infrastructure 达标检查。

Gate 清单:
  24-a1  Gateway 集成: AgentRuntime.tick() Step 8 包含 gateway_stats
  24-a2  Gateway 集成: import 了 PermissionDeniedError
  24-a3  Gateway: 审计日志计数方法存在
  24-b1  StatementValidator: 6 条检测规则存在
  24-b2  StatementValidator: ViolationCategory 枚举存在（向后兼容）
  24-b3  StatementValidator: 中英文检测正常
  24-b4  StatementValidator: ValidationResult 有 violations/has_violations
  24-b5  Belief: __post_init__ 使用 StatementValidator
  24-c1  LifecycleManager: 四阶段方法存在
  24-c2  LifecycleManager: 休眠/唤醒/回收方法存在
  24-d1  MemoryConsolidation: ContextCompressor 存在
  24-d2  MemoryConsolidation: AttentionDrivenRetrieval 存在
  24-d3  MemoryConsolidation: ConsolidationScheduler 存在
  24-e1  GoalLifecycle: maintenance() 方法存在
  24-e2  GoalLifecycle: count_by_status() 方法存在

测试基线: 1724 passed, 8 skipped, 0 failed
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

GATES_PASSED = 0
GATES_FAILED = 0


def check(label: str, condition: bool, detail: str = ""):
    global GATES_PASSED, GATES_FAILED
    if condition:
        GATES_PASSED += 1
        print(f"  [PASS] {label}")
    else:
        GATES_FAILED += 1
        print(f"  [FAIL] {label} — {detail}")


# ── 24-A: Gateway Integration ────────────────────────────────────────

# 24-a1: AgentRuntime dispatch 包含 gateway stats
import inspect
from ocos.agent.agent_runtime import AgentRuntime
src = inspect.getsource(AgentRuntime._tick_step_dispatch)
check("24-a1 AgentRuntime dispatch has gateway_stats",
      "gateway_stats" in src and "gateway" in src.lower())

# 24-a2: import PermissionDeniedError in agent_runtime.py
with open("ocos/agent/agent_runtime.py") as f:
    agent_runtime_src = f.read()
check("24-a2 AgentRuntime imports PermissionDeniedError",
      "PermissionDeniedError" in agent_runtime_src)

# 24-a3: Gateway audit methods exist
from ocos.capability.permission_gateway import PermissionGateway
gw = PermissionGateway()
check("24-a3 Gateway has export_audit method", hasattr(gw, "export_audit"))
check("24-a3 Gateway has audit_count", hasattr(gw, "audit_count"))

# ── 24-B: StatementValidator ─────────────────────────────────────────

from ocos.constitution.statement_validator import (
    StatementValidator, ViolationCategory, ValidationResult, _DETECTION_RULES,
)

check("24-b1 StatementValidator has 6 detection rules", len(_DETECTION_RULES) == 6)

check("24-b2 ViolationCategory enum exists", hasattr(ViolationCategory, "PERSONHOOD"))
check("24-b2 ViolationCategory CONSCIOUSNESS", hasattr(ViolationCategory, "CONSCIOUSNESS"))

sv = StatementValidator()
r_en = sv.validate("I feel happy")
check("24-b3 English emotion detected", r_en.has_violations)

r_zh = sv.validate("我很高兴")
check("24-b3 Chinese emotion detected", r_zh.has_violations)

r_cn = sv.validate("我有自己的意识")
check("24-b3 Chinese consciousness detected", r_cn.has_violations)

check("24-b4 ValidationResult.violations", hasattr(r_en, "violations"))
check("24-b4 ValidationResult.has_violations", hasattr(r_en, "has_violations"))
check("24-b4 ValidationResult.summary()", callable(getattr(r_en, "summary", None)))
check("24-b4 ValidationResult.categories()", callable(getattr(r_en, "categories", None)))

# 24-b5: Belief uses StatementValidator
from ocos.memory.belief import Belief, BeliefValidationError
try:
    b = Belief(statement="Normal observation about weather")
    check("24-b5 Belief clean statement accepted", True)
except BeliefValidationError:
    check("24-b5 Belief clean statement accepted", False)

try:
    Belief(statement="I am conscious and self-aware")
    check("24-b5 Belief blocks consciousness claim", False)
except BeliefValidationError:
    check("24-b5 Belief blocks consciousness claim", True)

# ── 24-C: AgentLifecycleManager ─────────────────────────────────────

from ocos.capability.lifecycle_manager import AgentLifecycleManager

mgr = AgentLifecycleManager()
check("24-c1 connect method exists", hasattr(mgr, "connect"))
check("24-c1 authenticate method exists", hasattr(mgr, "authenticate"))
check("24-c1 execute method exists", hasattr(mgr, "execute"))
check("24-c1 release method exists", hasattr(mgr, "release"))

check("24-c2 sleep method exists", hasattr(mgr, "sleep"))
check("24-c2 wake method exists", hasattr(mgr, "wake"))
check("24-c2 reclaim_idle method exists", hasattr(mgr, "reclaim_idle"))
check("24-c2 health_check_all method exists", hasattr(mgr, "health_check_all"))

# ── 24-D: MemoryConsolidation ────────────────────────────────────────

from ocos.agent.memory_consolidation import (
    ContextCompressor, AttentionDrivenRetrieval, MemoryConsolidationScheduler,
)

cc = ContextCompressor(token_budget=100)
check("24-d1 ContextCompressor exists", cc is not None)
items, stats = cc.compress([{"content": "hello world", "importance": 0.5}])
check("24-d1 ContextCompressor.compress works", len(items) == 1 and stats.compression_ratio <= 1.0)

adr = AttentionDrivenRetrieval()
check("24-d2 AttentionDrivenRetrieval exists", adr is not None)
result = adr.retrieve("test query", [{"content": "relevant", "tags": [], "importance": 0.8}])
check("24-d2 AttentionDrivenRetrieval.retrieve works", hasattr(result, "items"))

sched = MemoryConsolidationScheduler()
check("24-d3 ConsolidationScheduler exists", sched is not None)
check("24-d3 should_consolidate returns bool", isinstance(sched.should_consolidate(0), bool))

# ── 24-E: Goal Lifecycle ─────────────────────────────────────────────

from ocos.goal.tree import GoalTree
check("24-e1 GoalTree.maintenance exists", hasattr(GoalTree, "maintenance"))
check("24-e2 GoalTree.count_by_status exists", hasattr(GoalTree, "count_by_status"))

# ── 24c4: Bridge 集成 ────────────────────────────────────────────────

from ocos.capability.async_bridge import AsyncBridge, DispatchResult
bridge = AsyncBridge(engine_bridge=object())
check("24-c4 AsyncBridge has lifecycle field", hasattr(bridge, "lifecycle"))
check("24-c4 LifecycleManager.transition exists", hasattr(mgr, "transition"))
check("24-c4 LifecycleManager.ensure_registered exists", hasattr(mgr, "ensure_registered"))
ok_r = mgr.ensure_registered("gateway_test", "test")
check("24-c4 ensure_registered returns AgentHandle", ok_r is not None)
ok_t = mgr.transition("gateway_test", "idle")
check("24-c4 transition string state works", ok_t)

# ── 24d4: 四层管道集成 ───────────────────────────────────────────────
import importlib.util
pipe_spec = importlib.util.find_spec("tests.test_memory.test_consolidation_pipeline")
check("24-d4 pipeline test file exists", pipe_spec is not None)

# fatigue 感知检索
result_fatigue = adr.retrieve("test", [{"content": "relevant", "tags": [], "importance": 0.8}], fatigue_level=0.9)
check("24-d4 fatigue-aware retrieve accepts fatigue_level", hasattr(result_fatigue, "items"))

# force consolidate
check("24-d4 should_consolidate force=True", sched.should_consolidate(0, force=True))


# ── Summary ──────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Phase 24 Gate: {GATES_PASSED}/{GATES_PASSED + GATES_FAILED} PASS")
if GATES_FAILED == 0:
    print("STATUS: ALL GATES PASSED ✓")
    sys.exit(0)
else:
    print(f"STATUS: {GATES_FAILED} GATE(S) FAILED ✗")
    sys.exit(1)
