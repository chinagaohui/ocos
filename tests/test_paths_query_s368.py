"""S3.6/S3.8: REPL 路径统一 + query_db 去硬编码回归（白皮书 P3）。"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace


class TestReplPath:
    def test_repl_uses_resolved_db_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
        from ocos.interaction.repl.shell import OcosShell
        shell = OcosShell()
        assert str(shell.ctx.db_path) == str(tmp_path / "t.db"), \
            f"REPL 库路径应来自 resolve_db_path, 实际 {shell.ctx.db_path}"


class TestQueryDbPath:
    def test_query_db_uses_instance_path(self, tmp_path):
        """bridge._db_path 优先于 ~/.ocos 默认（修复后查对库）。"""
        from ocos.execution.bridge import DecisionBridge
        db = str(tmp_path / "custom.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE probe (k TEXT)")
        conn.execute("INSERT INTO probe VALUES ('hit')")
        conn.commit()
        conn.close()
        bridge = DecisionBridge(db_path=db)
        bridge.attach_default_handlers()
        result = bridge._handler_query_db(SimpleNamespace(
            payload={"query": "SELECT k FROM probe"}))
        assert result.get("ok") is True, result
        assert "hit" in str(result.get("rows", result))
