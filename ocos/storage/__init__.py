"""OCOS Storage — 持久化层包导出。

注意：event_store、dead_letter_queue、checkpoint 的导入为 lazy，
因为这些模块在子任务 21-01-2/3/4 中才创建。
"""

from ocos.storage.base import StorageBase
from ocos.storage.working_memory import SQLiteWorkingMemory
from ocos.storage.migrations import ensure_schema

# ── Lazy 导入封装（避免尚未创建的模块引发 ImportError）──────────────────────

def _lazy_import(module_name: str, class_name: str):
    """延迟导入，第一次访问时加载。"""
    import importlib
    mod = importlib.import_module(module_name)
    return getattr(mod, class_name)


def get_event_store(*args, **kwargs):
    """获取 SQLiteEventStore 实例（lazy import）。"""
    cls = _lazy_import("ocos.storage.event_store", "SQLiteEventStore")
    return cls(*args, **kwargs)


def get_dlq(*args, **kwargs):
    """获取 SQLiteDLQ 实例（lazy import）。"""
    cls = _lazy_import("ocos.storage.dead_letter_queue", "SQLiteDLQ")
    return cls(*args, **kwargs)


def get_checkpoint_manager(*args, **kwargs):
    """获取 CheckpointManager 实例（lazy import）。"""
    cls = _lazy_import("ocos.storage.checkpoint", "CheckpointManager")
    return cls(*args, **kwargs)


__all__ = [
    "StorageBase",
    "SQLiteWorkingMemory",
    "ensure_schema",
    "get_event_store",
    "get_dlq",
    "get_checkpoint_manager",
]

