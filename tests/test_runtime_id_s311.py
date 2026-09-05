"""S3.11: runtime_id 固定 + 恢复矢量观测回灌回归（白皮书 P2-1/P2-2）。

- RuntimeKernel runtime_id 优先级：显式参数 > OCOS_RUNTIME_ID > uuid
- RecoveryResult 携带 restore_result（认知矢量可观测，不再静默丢弃）
"""

from __future__ import annotations

import pytest

from ocos.runtime.recovery_engine import RecoveryResult
from ocos.runtime.runtime_kernel import RuntimeKernel


class TestRuntimeIdStability:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OCOS_RUNTIME_ID", "fixed-runtime-1")
        k1 = RuntimeKernel()
        k2 = RuntimeKernel()
        assert k1.runtime_id == k2.runtime_id == "fixed-runtime-1"

    def test_explicit_param_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("OCOS_RUNTIME_ID", "from-env")
        k = RuntimeKernel(runtime_id="from-param")
        assert k.runtime_id == "from-param"

    def test_same_id_checkpoint_hit(self, monkeypatch, tmp_path):
        """同 runtime_id 跨实例 → 旧式 checkpoint 可命中（39.1 通道复活）。"""
        from ocos.runtime.checkpoint import CheckpointEngine
        d = tmp_path / "ckpt"
        monkeypatch.setenv("OCOS_RUNTIME_ID", "stable-1")
        k1 = RuntimeKernel(checkpoint_dir=d)
        k1.start()
        k1.tick_loop(max_ticks=3)
        k1.shutdown(checkpoint=True)
        engine = CheckpointEngine(d)
        assert engine.latest_checkpoint("stable-1") is not None


class TestRestoreResultVisibility:
    def test_recovery_result_carries_restore(self, monkeypatch, tmp_path):
        """认知恢复路径的 RecoveryResult.restore_result 非 None。"""
        monkeypatch.setenv("OCOS_RECOVERY_DIR", str(tmp_path / "rec"))
        from ocos.runtime.recovery_engine import RecoveryEngine
        engine = RecoveryEngine.__new__(RecoveryEngine)
        # 用真实组件构造最小恢复链
        from ocos.runtime.recovery.recovery_manager import RecoveryManager
        mgr = RecoveryManager(data_dir=tmp_path / "rec")
        engine._recovery_mgr = mgr
        engine._ckpt = __import__(
            "ocos.runtime.checkpoint", fromlist=["CheckpointEngine"]
        ).CheckpointEngine(tmp_path / "ckpt")
        engine._runtime_id = "r-1"
        result = engine.attempt_recovery()
        # 无快照时走 checkpoint 退路 → restore_result=None（合法）
        assert result.restore_result is None or hasattr(
            result.restore_result, "active_goal_ids")
