"""Phase14 测试基础配置 — 添加项目根到 sys.path 以便 import contracts/reality。"""
import sys
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _sandbox_switch_default_off(monkeypatch):
    """沙盒白名单开关测试隔离（2026-09-07）。

    生产 ~/.ocos/config.json 可能设 OCOS_SANDBOX_DISABLED=true（个人使用
    模式）。env 非 "false" 之外的假值不会覆盖 config.json — 此处统一设
    "false"（env > config.json）锁定「沙盒开启」语义，需要测开关的测试
    自行 setenv("OCOS_SANDBOX_DISABLED", "true") 覆盖。
    """
    monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
