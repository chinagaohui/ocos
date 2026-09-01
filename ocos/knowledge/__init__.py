"""Knowledge module — 统一的知识管理接口."""

from ocos.knowledge.manager import (
    KnowledgeManager,
    KnowledgeResult,
    ExternalSource,
    create_knowledge_manager,
)

__all__ = [
    "KnowledgeManager",
    "KnowledgeResult",
    "ExternalSource",
    "create_knowledge_manager",
]
