"""Phase 45: CapabilityGraph — 能力关系图。

描述能力之间的层级和依赖关系:
    software_development
        ├── code_generation
        ├── testing
        ├── debugging
        └── deployment
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import CapabilityType


@dataclass
class CapabilityGraph:
    """能力关系图。

    基于 CapabilityType 的分类体系构建。
    """

    _hierarchy: dict[str, list[str]] = field(default_factory=lambda: {
        "software_development": [
            "code_generation", "code_review", "testing", "debugging", "deployment",
        ],
        "research": [
            "search", "browser", "data_analysis",
        ],
        "content_creation": [
            "document_generation",
        ],
        "automation": [
            "file_operation", "api_call",
        ],
    })

    def children(self, cap_type: CapabilityType) -> list[str]:
        """获取某类型下的子能力名称。"""
        return self._hierarchy.get(cap_type.value, [])

    def parent_of(self, cap_type: CapabilityType) -> str | None:
        """获取某能力的父类别。"""
        for parent, kids in self._hierarchy.items():
            if cap_type.value in kids:
                return parent
        return None

    def is_related(self, a: CapabilityType, b: CapabilityType) -> bool:
        """两个类型是否在同一类别下。"""
        pa = self.parent_of(a)
        pb = self.parent_of(b)
        if pa and pb:
            return pa == pb
        return a == b

    def all_siblings(self, cap_type: CapabilityType) -> list[str]:
        """获取同类型下的所有兄弟能力。"""
        parent = self.parent_of(cap_type)
        if parent:
            return [c for c in self._hierarchy.get(parent, []) if c != cap_type.value]
        return []

    def root_categories(self) -> list[str]:
        return list(self._hierarchy.keys())


__all__ = ["CapabilityGraph"]
