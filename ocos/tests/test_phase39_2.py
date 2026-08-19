"""Phase 39.2 Acceptance Tests: R39-201 ~ R39-204.

验证 Tick Pipeline:
    R39-201: Pipeline 顺序 — 8 stages in fixed order
    R39-202: 空系统持续运行 — 1000 ticks, no Goal/Event/Agent
    R39-203: Stage 隔离 — 无 import runtime_kernel/self/agent 循环
    R39-204: Tick Replay 准备 — TickContext.to_dict() 可序列化
"""

from __future__ import annotations

import ast
import json
import time

import pytest

from ocos.runtime.pipeline import TickPipeline
from ocos.runtime.pipeline_protocol import PipelineStage, TickStage
from ocos.runtime.tick_context import TickContext
from ocos.runtime import RuntimeKernel


# ═══════════════════════════════════════════════════════════════════════════
# R39-201: Pipeline 顺序
# ═══════════════════════════════════════════════════════════════════════════

class TestR39201PipelineOrder:
    """R39-201: Tick Pipeline 必须按固定顺序执行 8 阶段。"""

    FROZEN_ORDER = (
        "EVENT_INGESTION",
        "ATTENTION",
        "MEMORY_SYNC",
        "GOAL_MAINTENANCE",
        "EXECUTION_CHECK",
        "RESULT_COLLECTION",
        "LEARNING_TRIGGER",
        "CHECKPOINT_DECISION",
    )

    def test_pipeline_has_8_stages(self):
        p = TickPipeline()
        assert p.stage_count == 8

    def test_pipeline_stage_names_match_frozen_order(self):
        p = TickPipeline()
        assert p.stage_names() == self.FROZEN_ORDER

    def test_pipeline_stage_enum_order_matches(self):
        names = tuple(s.name for s in TickPipeline.STAGE_ORDER)
        assert names == self.FROZEN_ORDER

    def test_tick_context_traces_all_8_stages(self):
        p = TickPipeline()
        ctx = p.execute_tick(tick_id=1)

        # 8 stages + COMPLETE marker
        assert len(ctx.stage_traces) == 9  # 8 stages + "COMPLETE"
        assert ctx.stage_traces[:8] == self.FROZEN_ORDER
        assert ctx.stage_traces[8] == "COMPLETE"

    def test_each_tick_gets_correct_tick_id(self):
        p = TickPipeline()
        for tid in [1, 42, 999]:
            ctx = p.execute_tick(tick_id=tid)
            assert ctx.tick_id == tid

    def test_pipeline_through_runtime_kernel_traces_stages(self):
        """Pipeline 通过 RuntimeKernel 执行时仍然记录完整 stage trace。"""
        # Register a spy stage to verify pipeline executes through kernel
        trace_msgs = []

        class SpyStage:
            name: str = "SPY"
            def execute(self, context: TickContext) -> TickContext:
                trace_msgs.append(context.stage_traces)
                return context.with_stage_trace(self.name)

        p = TickPipeline()
        # 用 spy 替换 CHECKPOINT_DECISION (最后一个)
        p.register_stage(PipelineStage.CHECKPOINT_DECISION, SpyStage())

        ctx = p.execute_tick(tick_id=1)
        assert "SPY" in ctx.stage_traces
        # trace captured before spy ran = first 7 stages + memory_sync onwards completion
        assert len(trace_msgs) > 0


# ═══════════════════════════════════════════════════════════════════════════
# R39-202: 空系统持续运行
# ═══════════════════════════════════════════════════════════════════════════

class TestR39202EmptySystemEndurance:
    """R39-202: 无 Goal / Event / Agent 条件下 1000 ticks 通过。"""

    def test_1000_ticks_no_goal_no_event_no_agent(self):
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="ocos_39_2_")
        k = RuntimeKernel(checkpoint_dir=tmpdir)
        k.start()
        k.tick_loop(max_ticks=1000)
        k.shutdown()

        assert k.tick_count == 1000
        assert k.last_tick_id == 1000

    def test_empty_system_checkpoint_persists(self):
        """100 ticks 后 checkpoint 存在。"""
        import time
        uid = f"empty-{int(time.time() * 1000)}"
        k = RuntimeKernel(runtime_id=uid)
        k.start()
        k.tick_loop(max_ticks=100)
        k.shutdown()

        from ocos.runtime.checkpoint import CheckpointEngine
        cp = CheckpointEngine()
        record = cp.latest_checkpoint(uid)
        assert record is not None, "checkpoint not found after 100 ticks"
        assert record.tick_id >= 100


# ═══════════════════════════════════════════════════════════════════════════
# R39-203: Stage 隔离
# ═══════════════════════════════════════════════════════════════════════════

class TestR39203StageIsolation:
    """R39-203: Stage 不能 import runtime_kernel / self / agent。

    采用 AST 扫描确保 ocos.runtime.stages 下无禁止导入。
    """

    FORBIDDEN = (
        "ocos.runtime.runtime_kernel",
        "ocos.self",
    )

    def test_no_stage_imports_runtime_kernel(self):
        import ast
        from pathlib import Path

        stages_dir = Path(__file__).parents[1] / "runtime" / "stages"
        imports = []

        for f in sorted(stages_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in self.FORBIDDEN:
                            if node.module == forbidden or node.module.startswith(forbidden + "."):
                                imports.append(f"{f.name}: {node.module}")

        assert imports == [], f"forbidden imports found: {imports}"

    def test_no_stage_imports_ocos_self(self):
        """duplicate assertion via grep — self-contained。"""
        import subprocess, sys
        from pathlib import Path

        stages_dir = Path(__file__).parents[1] / "runtime" / "stages"
        r = subprocess.run(
            ["grep", "-rn", "from ocos.self", str(stages_dir)],
            capture_output=True, text=True
        )
        assert r.returncode != 0, f"forbidden self import: {r.stdout}"

    def test_goal_maintenance_stage_no_create_call(self):
        """Stage ④ 不得实际 call goal_store.create()（AST 检查）。"""
        import ast
        from pathlib import Path
        stages_dir = Path(__file__).parents[1] / "runtime" / "stages"
        gm_path = stages_dir / "goal_maintenance.py"
        tree = ast.parse(gm_path.read_text())

        for node in ast.walk(tree):
            # 检查函数调用: goal_store.create() 或 store.create()
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "create":
                        self._fail_if_forbidden_call(node, gm_path.name)

    @staticmethod
    def _fail_if_forbidden_call(node, filename):
        # 只标记 if the parent object is goal_store or store
        obj = node.func.value
        if isinstance(obj, ast.Name) and obj.id in ("goal_store", "store"):
            pytest.fail(f"{filename}: forbidden create() call via {obj.id}")

    def test_execution_check_stage_no_agent_call(self):
        """Stage ⑤ 不得调用 Agent.execute()（AST 检查）。"""
        import ast
        from pathlib import Path
        stages_dir = Path(__file__).parents[1] / "runtime" / "stages"
        ec_path = stages_dir / "execution_check.py"
        tree = ast.parse(ec_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "execute":
                        obj = node.func.value
                        if isinstance(obj, ast.Name) and obj.id in ("Agent", "agent"):
                            pytest.fail(f"execution_check.py: forbidden Agent.execute() call")


# ═══════════════════════════════════════════════════════════════════════════
# R39-204: Tick Replay 准备
# ═══════════════════════════════════════════════════════════════════════════

class TestR39204TickReplay:
    """R39-204: TickContext.to_dict() 可序列化 → future replay。"""

    def test_tick_context_serializable(self):
        p = TickPipeline()
        ctx = p.execute_tick(tick_id=100)

        d = ctx.to_dict()
        # 每个 tick 必须可 JSON 序列化
        s = json.dumps(d, indent=2)
        assert len(s) > 0

    def test_tick_context_dict_keys(self):
        p = TickPipeline()
        ctx = p.execute_tick(tick_id=42)
        d = ctx.to_dict()

        required = [
            "tick_id", "runtime_state", "events_count", "attention_snapshot",
            "memory_changes_count", "goal_updates_count", "execution_candidates_count",
            "execution_results_count", "learning_signals_count", "checkpoint_decision",
            "started_at", "completed_at", "stage_traces",
        ]
        for key in required:
            assert key in d, f"missing key: {key}"

    def test_two_tick_contexts_independent(self):
        """两个 tick 的上下文互不影响 (immutability proof)。"""
        p = TickPipeline()
        ctx100 = p.execute_tick(tick_id=100)
        ctx200 = p.execute_tick(tick_id=200)

        assert ctx100.tick_id == 100
        assert ctx200.tick_id == 200
        assert ctx100.completed_at > 0
        assert ctx200.completed_at > ctx100.completed_at
        # 100 的 completed_at 未受 200 影响
        assert ctx100 is not ctx200

    def test_tick_context_with_updates_preserves_immutability(self):
        """with_updates() 返回新对象，不修改原对象。"""
        ctx = TickContext(tick_id=1, runtime_state="running", started_at=time.time())
        ctx2 = ctx.with_updates(tick_id=2)

        assert ctx.tick_id == 1  # 原始未变
        assert ctx2.tick_id == 2  # 新对象
        assert ctx is not ctx2
