"""S2.7: 恢复数据持久化目录回归（白皮书 P2）。

- RuntimeKernel 默认恢复目录 ~/.ocos/recovery（不再 /tmp）
- OCOS_RECOVERY_DIR 可覆盖
- 显式传入 checkpoint_dir 仍生效（向后兼容）
"""

from __future__ import annotations

import os
from pathlib import Path

from ocos.runtime.runtime_kernel import RuntimeKernel


class TestRecoveryDir:
    def test_default_persistent_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("OCOS_RECOVERY_DIR", raising=False)
        kernel = RuntimeKernel(runtime_id="k-test")
        expected = tmp_path / ".ocos" / "recovery"
        assert expected.exists()
        # 恢复数据四子目录随 data_dir 落在持久目录
        assert (expected / "snapshots").exists()
        assert (expected / "events").exists()

    def test_env_override(self, monkeypatch, tmp_path):
        custom = tmp_path / "custom_recovery"
        monkeypatch.setenv("OCOS_RECOVERY_DIR", str(custom))
        RuntimeKernel(runtime_id="k-test")
        assert custom.exists()

    def test_explicit_arg_still_works(self, tmp_path):
        d = tmp_path / "explicit"
        RuntimeKernel(runtime_id="k-test", checkpoint_dir=d)
        assert d.exists()
