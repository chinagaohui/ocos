"""CPU load 阈值按核数归一化测试（COG-V2 Phase4.5 附带修复）。

生产实锤（2026-09-13）：硬编码 load1>4.0 报过载是 4 核时代的满载线；
切本地 qwen 模型后 12 核机器常态 load1≈4.8（仅 40% 占用）被误报过载，
导致 SelfCheck 四层自检在开发机上恒红。
"""
from __future__ import annotations

import pytest

from ocos.diagnosis import environment_probe as ep


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OCOS_CPU_LOAD_BAD", raising=False)
    monkeypatch.delenv("OCOS_CPU_LOAD_WARN", raising=False)
    yield


def test_thresholds_scale_with_nproc(monkeypatch):
    monkeypatch.setattr(ep.os, "cpu_count", lambda: 12)
    bad, warn, nproc = ep._cpu_load_thresholds()
    assert nproc == 12
    assert bad == pytest.approx(12.0)   # 4.0 * 12/4
    assert warn == pytest.approx(7.5)   # 2.5 * 12/4


def test_thresholds_4core_unchanged(monkeypatch):
    """4 核机器保持历史绝对阈值，向后兼容。"""
    monkeypatch.setattr(ep.os, "cpu_count", lambda: 4)
    bad, warn, nproc = ep._cpu_load_thresholds()
    assert (bad, warn, nproc) == (4.0, 2.5, 4)


def test_explicit_env_is_absolute_not_scaled(monkeypatch):
    """env 显式配置保持绝对值语义（用户自定阈值不被缩放）。"""
    monkeypatch.setattr(ep.os, "cpu_count", lambda: 12)
    monkeypatch.setenv("OCOS_CPU_LOAD_BAD", "6.0")
    monkeypatch.setenv("OCOS_CPU_LOAD_WARN", "3.0")
    bad, warn, _ = ep._cpu_load_thresholds()
    assert (bad, warn) == (6.0, 3.0)


def test_half_load_on_many_core_is_healthy(monkeypatch):
    """12 核机器 load1=4.8（40% 占用）不应产生 CPU 告警。"""
    import itertools
    monkeypatch.setattr(ep.os, "cpu_count", lambda: 12)
    # /proc/loadavg 三列 + 后续字段
    fake = "4.8 4.2 4.0 2/1234 5678\n"
    monkeypatch.setattr(ep, "_read_file", lambda path: fake
                        if path == "/proc/loadavg" else "")
    # 内存/磁盘分支读不到 /proc 也不抛（_read_file 已被桩为 ""）
    h = ep.probe_host_resources(heavy=False)
    cpu_warns = [w for w in h.warnings if "CPU" in w]
    assert cpu_warns == [], cpu_warns
    assert h.metrics["cpu_count"] == 12
