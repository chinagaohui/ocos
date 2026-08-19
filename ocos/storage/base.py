"""StorageBase — 所有持久化存储的抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class StorageBase(ABC, Generic[T]):
    """存储抽象基类。所有存储实现（SQLite、内存、未来远程）继承此类。"""

    @abstractmethod
    def store(self, key: str, value: T, **kwargs) -> str:
        """存储一条记录，返回记录 ID。"""

    @abstractmethod
    def load(self, key: str) -> Optional[T]:
        """按 key 加载一条记录，不存在返回 None。"""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除一条记录，返回是否成功。"""

    @abstractmethod
    def list(self, pattern: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[T]:
        """列举记录。支持模式匹配、分页。"""

    @abstractmethod
    def connect(self, **kwargs) -> None:
        """建立底层连接。"""

    @abstractmethod
    def close(self) -> None:
        """关闭底层连接。"""
