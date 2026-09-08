"""L0-3: 自主行为总闸（OCOS_AUTONOMY_LEVEL）单元测试。

覆盖:
  1. 环境变量解析（合法/非法/缺省）
  2. 覆盖文件优先于环境变量（运行期切换通道）
  3. 级别判据 can_propose / can_autonomous_execute / full_autonomy
  4. set_autonomy_level 写覆盖文件 + 非法值拒绝
  5. 级别切换审计: JSONL 留痕 + audit episode 落库（R4 可回放）
"""
import json

import pytest

from ocos.execution import autonomy
from ocos.execution.autonomy import (
    DEFAULT_AUTONOMY_LEVEL,
    audit_level_change,
    append_audit_record,
    audit_log_path,
    can_autonomous_execute,
    can_propose,
    full_autonomy,
    get_autonomy_level,
    set_autonomy_level,
)


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """隔离覆盖文件与审计目录 — 不污染真实 ~/.ocos。"""
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE",
                       str(tmp_path / "autonomy_level"))
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.delenv("OCOS_AUTONOMY_LEVEL", raising=False)
    yield


class TestLevelResolution:
    def test_default_when_unset(self):
        assert get_autonomy_level() == DEFAULT_AUTONOMY_LEVEL

    @pytest.mark.parametrize("lvl", [0, 1, 2, 3])
    def test_env_var_valid(self, monkeypatch, lvl):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", str(lvl))
        assert get_autonomy_level() == lvl

    @pytest.mark.parametrize("bad", ["4", "-1", "abc", "1.5", ""])
    def test_env_var_invalid_falls_back(self, monkeypatch, bad):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", bad)
        assert get_autonomy_level() == DEFAULT_AUTONOMY_LEVEL

    def test_override_file_beats_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "2")
        override = autonomy.autonomy_override_path()
        override.write_text("0", encoding="utf-8")
        assert get_autonomy_level() == 0

    def test_override_file_invalid_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "2")
        override = autonomy.autonomy_override_path()
        override.write_text("nine", encoding="utf-8")
        assert get_autonomy_level() == 2


class TestLevelPredicates:
    def test_can_propose_boundary(self, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "0")
        assert not can_propose()
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "1")
        assert can_propose()

    def test_autonomous_execute_boundary(self, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "1")
        assert not can_autonomous_execute()
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "2")
        assert can_autonomous_execute()

    def test_full_autonomy_boundary(self, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "2")
        assert not full_autonomy()
        monkeypatch.setenv("OCOS_AUTONOMY_LEVEL", "3")
        assert full_autonomy()

    def test_explicit_level_argument_wins(self):
        assert can_propose(0) is False
        assert can_propose(3) is True


class TestSetLevel:
    def test_set_and_get_roundtrip(self):
        assert set_autonomy_level(2) == 2
        assert get_autonomy_level() == 2
        assert autonomy.autonomy_override_path().read_text() == "2"

    def test_set_invalid_raises(self):
        with pytest.raises(ValueError):
            set_autonomy_level(5)
        with pytest.raises(ValueError):
            set_autonomy_level("x")  # type: ignore[arg-value]


class TestAudit:
    def test_append_audit_record_jsonl(self):
        path = append_audit_record({"kind": "level_change", "old": 1,
                                    "new": 2})
        rec = json.loads(open(path, encoding="utf-8").read().splitlines()[0])
        assert rec["old"] == 1 and rec["new"] == 2
        assert rec["kind"] == "level_change"
        assert "ts" in rec and "pid" in rec

    def test_level_change_writes_episode(self, tmp_path):
        db = str(tmp_path / "ocos.db")
        audit_level_change(db, old=1, new=0, source="test")
        # episode 落库（tags 含 autonomy/audit）
        import sqlite3
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT tags, decision FROM episodes WHERE "
                "tags LIKE '%autonomy%'").fetchone()
        finally:
            conn.close()
        assert row is not None
        assert "level_change" in row[0]
        assert "1 → 0" in row[1]

    def test_level_change_audit_log_always_written(self, tmp_path):
        # db 为 :memory: 时 JSONL 仍留痕（审计链不因 episode 缺席断链）
        audit_level_change(":memory:", old=0, new=2, source="test")
        lines = audit_log_path().read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[-1])
        assert rec == {"kind": "level_change", "old": 0, "new": 2,
                       "source": "test", "ts": rec["ts"], "pid": rec["pid"]}
