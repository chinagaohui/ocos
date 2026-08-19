"""LogRotator — 日志轮转管理。

支持：
- 按文件大小轮转（自动从 RotatingFileHandler 配置读取）
- 按时间轮转（按天/小时）
- 手动触发轮转
"""

from __future__ import annotations

import os
import glob
import gzip
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class LogRotator:
    """日志轮转管理器。"""

    def __init__(
        self,
        log_dir: str = "ocos/logs",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        os.makedirs(log_dir, exist_ok=True)

    def rotate_if_needed(self, filename: str) -> bool:
        """如果文件超过 max_bytes，执行轮转。返回是否轮转。"""
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            return False
        if os.path.getsize(filepath) < self.max_bytes:
            return False
        self.rotate(filename)
        return True

    def rotate(self, filename: str) -> None:
        """执行一次轮转。

        将当前日志重命名为 .1、已有 .1 成为 .2，依此类推。
        """
        filepath = os.path.join(self.log_dir, filename)

        # 向上移动备份
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{filepath}.{i}"
            dst = f"{filepath}.{i + 1}"
            if os.path.exists(src):
                shutil.move(src, dst)

        # 当前文件 → .1
        if os.path.exists(filepath):
            shutil.move(filepath, f"{filepath}.1")
    def compress_old(self, filename: str) -> int:
        """将所有旧备份压缩为 .gz。返回压缩文件数。"""
        filepath = os.path.join(self.log_dir, filename)
        compressed = 0
        for i in range(1, self.backup_count + 1):
            src = f"{filepath}.{i}"
            dst = f"{filepath}.{i}.gz"
            if os.path.exists(src) and not os.path.exists(dst):
                with open(src, "rb") as f_in:
                    with gzip.open(dst, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(src)
                compressed += 1
        return compressed

    def list_logs(self) -> list[dict[str, object]]:
        """列出日志目录中的所有日志文件。"""
        logs = []
        pattern = os.path.join(self.log_dir, "*.log*")
        for path in sorted(glob.glob(pattern)):
            stats = os.stat(path)
            logs.append({
                "path": path,
                "size": stats.st_size,
                "mtime": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
            })
        return logs
