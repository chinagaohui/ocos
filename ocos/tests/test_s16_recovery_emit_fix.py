"""S1.6: RecoveryManager.shutdown 单一定义（含账本落盘）+ EventBus
publish API 对齐回归（白皮书 P1-7 / P1-6）。
"""

from __future__ import annotations

from ocos.runtime.recovery.recovery_manager import RecoveryManager
from ocos.runtime.recovery.runtime_snapshot import SnapshotReason


class TestShutdownSingleDefinition:
    def test_shutdown_persists_ledger(self, tmp_path):
        """shutdown() 必须把执行账本落盘（原第二定义缺失 _save_ledger）。"""
        import json
        mgr = RecoveryManager(data_dir=tmp_path)
        mgr.track_execution_start("exec-1", "fs_read", "read file")
        mgr.track_execution_success("exec-1", tick_id=5)
        mgr.shutdown(tick_id=10)
        ledger_files = list((tmp_path / "executions").glob("*.json"))
        assert ledger_files, "账本未落盘"
        data = json.loads(ledger_files[0].read_text())
        assert any(r.get("execution_id") == "exec-1" for r in data)

    def test_publish_guard_tolerates_none_and_legacy_bus(self, tmp_path):
        """_publish_safe 对 None 与无 publish 的旧式总线均不抛错。"""
        from ocos.runtime.resource_manager import ResourceManager

        class LegacyBus:  # 只有 emit 的旧式桩（审计记录的历史误用形态）
            def emit(self, event):
                raise AssertionError("不应再调用 emit")

        mgr = ResourceManager(event_bus=None)
        mgr._event_bus = None
        mgr.release("nonexistent")  # 不应抛错
        mgr2 = ResourceManager(event_bus=LegacyBus())
        mgr2.release("nonexistent")  # publish 缺失 → 静默跳过
