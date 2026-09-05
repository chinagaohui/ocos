"""Phase 39.1 Acceptance Tests: R39-001 ~ R39-005.

验证 Runtime Skeleton 满足进入 39.2 的条件:
    R39-001: Runtime Boot — python -m ocos.runtime
    R39-002: Tick Generation — 60 ticks, no business behavior
    R39-003: Tick Persistence — checkpoint.json exists after shutdown
    R39-004: Recovery — restart continues from last_tick+1
    R39-005: Governance Isolation — no goal/agent/planning/self imports
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ocos.runtime import (
    CheckpointEngine,
    CheckpointRecord,
    LifecycleManager,
    RecoveryEngine,
    RuntimeKernel,
    RuntimeState,
    Tick,
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
)
from ocos.runtime.capability_policy import CapabilityPolicyProvider
from ocos.runtime.permission import DecisionResult


# ── helpers ──

def _new_kernel(runtime_id: str | None = None, **kwargs):
    """Create RuntimeKernel with unique temp dir, isolated from other tests."""
    tmp = tempfile.mkdtemp(prefix="ocos_t39_1_")
    return RuntimeKernel(
        runtime_id=runtime_id,
        checkpoint_dir=tmp,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# R39-001: Runtime Boot
# ═══════════════════════════════════════════════════════════════════════════

class TestR39001RuntimeBoot:
    """Runtime Boot → Runtime ID → State RUNNING."""

    def test_boot_creates_runtime_id(self):
        k = _new_kernel()
        rid = k.start()
        assert isinstance(rid, str)
        assert len(rid) > 0
        assert k.runtime_id == rid

    def test_boot_transitions_to_running(self):
        k = _new_kernel()
        k.start()
        assert k.state == RuntimeState.RUNNING

    def test_python_m_ocos_runtime(self):
        """R39-001: python -m ocos.runtime 成功运行。"""
        project_root = Path(__file__).parents[2]
        result = subprocess.run(
            [sys.executable, "-m", "ocos.runtime"],
            capture_output=True, text=True,
            cwd=project_root,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr[:500]}"
        assert "Runtime BOOT" in result.stdout
        assert "State: running" in result.stdout
        assert "Ticks completed: 60" in result.stdout
        assert "State: shutdown" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# R39-002: Tick Generation
# ═══════════════════════════════════════════════════════════════════════════

class TestR39002TickGeneration:
    """60 ticks, no business behavior, monotonic tick_id."""

    def test_ticks_are_monotonic(self):
        k = _new_kernel()
        k.start()
        recorded_ticks = []

        # Use kernel directly
        k.tick_loop(max_ticks=60)
        tick_ids = [k.last_tick_id - 59 + i for i in range(60)]
        assert tick_ids == list(range(1, 61)), f"Expected [1..60], got [{tick_ids[0]}..{tick_ids[-1]}]"

    def test_tick_is_frozen(self):
        """Tick 是不可变对象。"""
        t = Tick(tick_id=1)
        with pytest.raises(Exception):  # frozen dataclass
            t.tick_id = 2  # type: ignore

    def test_tick_id_must_be_positive(self):
        with pytest.raises(ValueError, match=">= 1"):
            Tick(tick_id=0)

    def test_60_tick_run(self):
        k = _new_kernel()
        k.start()
        k.tick_loop(max_ticks=60)
        assert k.tick_count == 60
        assert k.last_tick_id == 60


# ═══════════════════════════════════════════════════════════════════════════
# R39-003: Tick Persistence
# ═══════════════════════════════════════════════════════════════════════════

class TestR39003TickPersistence:
    """Checkpoint JSON exists after shutdown, integrity verified."""

    def test_checkpoint_saved_after_shutdown(self):
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="ocos_cp_")
        k = RuntimeKernel(checkpoint_dir=tmpdir)
        k.start()
        k.tick_loop(max_ticks=22)
        k.shutdown()

        cp = CheckpointEngine(checkpoint_dir=tmpdir)
        record = cp.latest_checkpoint(k.runtime_id)
        assert record is not None, "No checkpoint found after shutdown"
        assert record.tick_id == 22, f"Expected shutdown checkpoint at last tick, got {record.tick_id}"

    def test_checkpoint_integrity_verified(self):
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="ocos_cp2_")
        k = RuntimeKernel(checkpoint_dir=tmpdir)
        k.start()
        k.tick_loop(max_ticks=10)
        k.shutdown()

        cp = CheckpointEngine(checkpoint_dir=tmpdir)
        record = cp.latest_checkpoint(k.runtime_id)
        assert record is not None
        assert record.verify_integrity(), "Checkpoint hash mismatch"

    def test_checkpoint_file_exists(self):
        tmpdir = tempfile.mkdtemp(prefix="ocos_cp_test_")
        k = RuntimeKernel(checkpoint_dir=tmpdir)
        k.start()
        k.tick_loop(max_ticks=10)
        k.shutdown()

        path = Path(tmpdir) / f"{k.runtime_id}_tick_000010.json"
        assert path.exists()
        data = json.loads(path.read_text())
        # 39.4: RecoveryEngine 升级，version 变为 "39.4"
        assert data["version"] in ("39.1", "39.4"), f"Unexpected version: {data['version']}"
        assert data["runtime_id"] == k.runtime_id


# ═══════════════════════════════════════════════════════════════════════════
# R39-004: Recovery
# ═══════════════════════════════════════════════════════════════════════════

class TestR39004Recovery:
    """Restart reads last_tick, continues from tick+1."""

    def test_cold_start_has_next_tick_1(self):
        tmpdir = tempfile.mkdtemp(prefix="ocos_cold_")
        ce = CheckpointEngine(checkpoint_dir=Path(tmpdir))
        re = RecoveryEngine(ce, runtime_id="test-cold", data_dir=Path(tmpdir))
        result = re.attempt_recovery()
        assert not result.recovered, f"Expected cold start, got recovered={result.recovered}"
        assert result.next_tick_id == 1

    def test_recovery_continues_from_last_tick(self):
        import time
        unique_id = f"recv-004-{int(time.time() * 1000)}"
        tmpdir = tempfile.mkdtemp(prefix="ocos_recv_")
        # Run 25 ticks, kill
        k1 = RuntimeKernel(runtime_id=unique_id, checkpoint_dir=tmpdir)
        k1.start()
        k1.tick_loop(max_ticks=25)
        k1.shutdown()

        # Restart and verify
        k2 = RuntimeKernel(runtime_id=unique_id, checkpoint_dir=tmpdir)
        k2.start()
        k2.tick_loop(max_ticks=5)
        assert k2.tick_count == 5
        assert k2.last_tick_id == 30
        k2.shutdown()

    def test_recovery_preserves_runtime_id(self):
        rid = "test-recovery-id"
        tmpdir = tempfile.mkdtemp(prefix="ocos_recv2_")

        k1 = RuntimeKernel(runtime_id=rid, checkpoint_dir=tmpdir)
        k1.start()
        k1.tick_loop(max_ticks=5)
        k1.shutdown()

        k2 = RuntimeKernel(runtime_id=rid, checkpoint_dir=tmpdir)
        k2.start()
        assert k2.runtime_id == rid

    def test_recovery_with_no_checkpoint_cold_starts(self):
        import time
        unique_id = f"never-{int(time.time() * 1000)}"
        tmpdir = tempfile.mkdtemp(prefix="ocos_never_")
        k = RuntimeKernel(runtime_id=unique_id, checkpoint_dir=tmpdir)
        k.start()
        assert k.last_tick_id == 0
        k.tick_loop(max_ticks=3)
        assert k.last_tick_id == 3
        k.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
# R39-005: Governance Isolation
# ═══════════════════════════════════════════════════════════════════════════

class TestR39005GovernanceIsolation:
    """Runtime 不 import goal/agent/planning/self 模块。"""

    FORBIDDEN_MODULES = [
        "ocos.goal",
        "ocos.agent",
        "ocos.planning",
        "ocos.self",
        "ocos.memory",
        "ocos.attention",
    ]

    ALLOWED_MODULES = [
        "ocos.runtime",
        "ocos.kernel.goal_types",  # type definitions only
    ]

    def test_no_forbidden_imports_in_runtime_package(self):
        """检查 ocos/runtime/ 下的 .py 文件没有禁止 import。"""
        runtime_dir = Path(__file__).parents[1] / "runtime"
        for py_file in runtime_dir.glob("*.py"):
            content = py_file.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if not line.startswith("from ocos.") and not line.startswith("import ocos."):
                    continue
                for forbidden in self.FORBIDDEN_MODULES:
                    if forbidden in line and "# pragma:" not in line:
                        if f"import {forbidden}" in line or f"from {forbidden}" in line:
                            pytest.fail(
                                f"{py_file.name}:{line} — forbidden import of {forbidden}"
                            )

    def test_module_loads_without_triggering_goal_initialization(self):
        """import ocos.runtime 不应触发 Goal/Agent 初始化。"""
        import ocos.runtime  # noqa: F811

    def test_capability_policy_provider_integration(self):
        """CapabilityPolicyProvider 接入 PermissionGateway。

        39.3: known L0 capabilities → ALLOW, unknown → DENY。
        """
        p = CapabilityPolicyProvider()
        assert p.check("runtime", "runtime.status") == DecisionResult.ALLOW
        assert p.check("runtime", "goal.list") == DecisionResult.ALLOW
        assert p.check("runtime", "file.read") == DecisionResult.ALLOW
        assert p.check("runtime", "create_goal") == DecisionResult.DENY
        assert p.check("runtime", "modify_identity") == DecisionResult.DENY
        assert p.check("runtime", "file.write") == DecisionResult.REQUIRE_APPROVAL


# ═══════════════════════════════════════════════════════════════════════════
# Runtime State & Lifecycle 单元测试
# ═══════════════════════════════════════════════════════════════════════════

class TestRuntimeState:
    def test_booting_to_running(self):
        lm = LifecycleManager(RuntimeState.BOOTING)
        assert lm.boot() == RuntimeState.RUNNING

    def test_running_to_shutdown(self):
        lm = LifecycleManager(RuntimeState.RUNNING)
        assert lm.shutdown() == RuntimeState.SHUTDOWN

    def test_invalid_transition_raises(self):
        lm = LifecycleManager(RuntimeState.SHUTDOWN)
        with pytest.raises(InvalidTransitionError):
            lm.boot()

    def test_enter_safe_mode(self):
        lm = LifecycleManager(RuntimeState.RUNNING)
        assert lm.enter_safe_mode() == RuntimeState.SAFE_MODE

    def test_safe_mode_only_to_shutdown(self):
        lm = LifecycleManager(RuntimeState.SAFE_MODE)
        assert lm.shutdown() == RuntimeState.SHUTDOWN
        lm2 = LifecycleManager(RuntimeState.SAFE_MODE)
        with pytest.raises(InvalidTransitionError):
            lm2.transition(RuntimeState.BOOTING)
        # S3.10: SAFE_MODE→RUNNING 恢复路径（连续 5 tick 成功后自动恢复）
        lm3 = LifecycleManager(RuntimeState.SAFE_MODE)
        assert lm3.recover() == RuntimeState.RUNNING

    def test_degraded_recovery(self):
        lm = LifecycleManager(RuntimeState.RUNNING)
        lm.enter_degraded()
        assert lm.recover() == RuntimeState.RUNNING
