"""S3.3: OCOSConfig 统一配置回归（白皮书 P3 / §6.2）。"""

from __future__ import annotations

import json


class TestOCOSConfig:
    def test_priority_env_over_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"OCOS_TICK_BUDGET": "99"}),
                            encoding="utf-8")
        monkeypatch.setenv("OCOS_CONFIG_PATH", str(cfg_file))
        monkeypatch.setenv("OCOS_TICK_BUDGET", "42")
        from ocos.config import OCOSConfig
        cfg = OCOSConfig()
        assert cfg.get_int("OCOS_TICK_BUDGET") == 42  # env 优先
        monkeypatch.delenv("OCOS_TICK_BUDGET")
        cfg2 = OCOSConfig()
        assert cfg2.get_int("OCOS_TICK_BUDGET") == 99  # 次选文件

    def test_defaults_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_CONFIG_PATH", str(tmp_path / "none.json"))
        from ocos.config import get_str, get_int
        assert get_int("OCOS_API_PORT", 8900) == 8900
        assert get_str("OCOS_API_HOST", "127.0.0.1") == "127.0.0.1"

    def test_nested_keys_flattened(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"api": {"token": "t-1"}}),
                            encoding="utf-8")
        monkeypatch.setenv("OCOS_CONFIG_PATH", str(cfg_file))
        from ocos.config import OCOSConfig
        cfg = OCOSConfig()
        assert cfg.get("api.token") == "t-1"

    def test_approval_mode_via_config(self, tmp_path, monkeypatch):
        """approval_disabled 走统一配置（迁移样板 3）。"""
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.delenv("OCOS_APPROVAL_MODE", raising=False)
        from ocos.execution.pending import approval_disabled
        assert approval_disabled() is False  # S3.13: 默认已切 ask
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
        assert approval_disabled() is False
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")
        assert approval_disabled() is True
