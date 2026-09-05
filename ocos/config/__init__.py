"""OCOS 统一配置管理（S3.3，白皮书 P3 / §6）。

三层优先级：环境变量 > ~/.ocos/config.json > 内置默认值。
不加载 .env（代码零 load_dotenv 惯例，见白皮书 §6.2——保持现状）。

新代码必须使用 OCOSConfig.get()；旧模块渐进迁移。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_instance: "OCOSConfig | None" = None


def _config_file() -> Path:
    return Path(os.environ.get(
        "OCOS_CONFIG_PATH", "~/.ocos/config.json")).expanduser()


DEFAULTS: dict[str, str] = {
    "OCOS_DB_PATH": "~/.ocos/ocos.db",
    "OCOS_API_PORT": "8900",
    "OCOS_API_HOST": "127.0.0.1",
    "OCOS_ORGAN_BASE": "http://127.0.0.1:8000/api/organ",
    "OCOS_ALERTS_DIR": "~/.ocos/alerts",
    "OCOS_RECOVERY_DIR": "~/.ocos/recovery",
    "OCOS_LLM_DAILY_CAP": "500",
    "OCOS_TICK_BUDGET": "15",
    "OCOS_RATE_LIMIT": "60",
    "OCOS_MONITORING_PORT": "9090",
    "OCOS_WEBHOOK_PORT": "8901",
    "OCOS_API_BASE": "http://localhost:8900",
}


class OCOSConfig:
    """进程级配置单例（线程安全）。"""

    def __init__(self) -> None:
        self._file_cache: dict[str, Any] = {}
        self._file_mtime: float = 0.0
        self._reload_file()

    def _reload_file(self) -> None:
        path = _config_file()
        try:
            mtime = path.stat().st_mtime
        except OSError:
            self._file_cache = {}
            self._file_mtime = 0.0
            return
        if mtime == self._file_mtime and self._file_cache:
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        # 扁平化一层：顶层标量 + api./llm. 段的键（如 api.token）
        flat: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    flat[f"{k}.{k2}"] = v2
            else:
                flat[k] = v
        self._file_cache = flat
        self._file_mtime = mtime

    def get(self, key: str, default: Any = None) -> Any:
        """三层优先级读取。"""
        env_val = os.environ.get(key)
        if env_val is not None and env_val != "":
            return env_val
        with _lock:
            self._reload_file()
            if key in self._file_cache:
                return self._file_cache[key]
            # 顶层段点键兜底（如 "api.token"）
        return default

    def get_str(self, key: str, default: str = "") -> str:
        v = self.get(key, default)
        return str(v) if v is not None else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default


def get_config() -> OCOSConfig:
    """单例访问。"""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OCOSConfig()
    return _instance


def get_str(key: str, default: str = "") -> str:
    """模块级便捷入口：环境变量 > config.json > DEFAULTS > default。"""
    cfg = get_config()
    if key in DEFAULTS:
        return cfg.get_str(key, DEFAULTS[key] if default == "" else default)
    return cfg.get_str(key, default)


def get_int(key: str, default: int = 0) -> int:
    cfg = get_config()
    if key in DEFAULTS:
        try:
            return int(cfg.get(key, DEFAULTS[key] if default == 0 else default))
        except (TypeError, ValueError):
            return default
    return cfg.get_int(key, default)
