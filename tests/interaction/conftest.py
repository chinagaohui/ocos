"""tests/interaction 公共夹具。

AUD-F8: goal/plan 命令落库后，CLI 测试必须与真实 ~/.ocos/ocos.db 隔离 —
统一重定向 OCOS_DB_PATH 到临时目录。
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """所有 interaction CLI 测试使用临时 db，不触碰真实 ~/.ocos/ocos.db。"""
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "test.db"))
    yield
