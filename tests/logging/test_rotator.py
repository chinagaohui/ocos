"""LogRotator 测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ocos.logging.rotator import LogRotator


@pytest.fixture
def log_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestLogRotator:
    def test_rotate_small_file_not_rotated(self, log_dir):
        """小文件不轮转。"""
        path = os.path.join(log_dir, "test.log")
        with open(path, "w") as f:
            f.write("small\n")

        rotator = LogRotator(log_dir=log_dir, max_bytes=10 * 1024 * 1024)
        rotated = rotator.rotate_if_needed("test.log")
        assert rotated is False

    def test_rotate_large_file(self, log_dir):
        """大文件被轮转。"""
        path = os.path.join(log_dir, "test.log")
        with open(path, "w") as f:
            f.write("x" * 100)

        rotator = LogRotator(log_dir=log_dir, max_bytes=50)
        rotated = rotator.rotate_if_needed("test.log")
        assert rotated is True
        assert os.path.exists(os.path.join(log_dir, "test.log.1"))
        # 新文件应被重新创建（在使用中，但 rotator 自身不重建）

    def test_rotate_multiple_backups(self, log_dir):
        """多次轮转创建序列备份。"""
        rotator = LogRotator(log_dir=log_dir, max_bytes=10, backup_count=3)
        for _ in range(4):
            path = os.path.join(log_dir, "test.log")
            with open(path, "w") as f:
                f.write("x" * 20)
            rotator.rotate_if_needed("test.log")

        assert os.path.exists(os.path.join(log_dir, "test.log.1"))
        assert os.path.exists(os.path.join(log_dir, "test.log.2"))
        assert os.path.exists(os.path.join(log_dir, "test.log.3"))

    def test_list_logs(self, log_dir):
        """list_logs 返回目录中的日志文件信息。"""
        Path(os.path.join(log_dir, "ocos.log")).write_text("content\n")
        Path(os.path.join(log_dir, "ocos.log.1")).write_text("old\n")

        rotator = LogRotator(log_dir=log_dir)
        logs = rotator.list_logs()
        paths = [str(l["path"]) for l in logs]
        assert any("ocos.log" in p for p in paths)
        assert len(logs) >= 2

    def test_compress_old(self, log_dir):
        """compress_old 压缩备份文件。"""
        path = os.path.join(log_dir, "test.log")
        with open(path, "w") as f:
            f.write("x" * 100)

        rotator = LogRotator(log_dir=log_dir, max_bytes=10, backup_count=2)
        rotator.rotate_if_needed("test.log")  # → test.log.1

        compressed = rotator.compress_old("test.log")
        assert compressed >= 1
        assert os.path.exists(os.path.join(log_dir, "test.log.1.gz"))
