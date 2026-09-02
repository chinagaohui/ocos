"""Phase S: KnowledgeGraph — 用户知识图谱。"""

from .graph import (
    KnowledgeGraph,
    Entity,
    Relation,
    Fact,
    EntityType,
    RelationType,
)
from .manager import (
    KnowledgeGraphManager,
    ExtractionResult,
)

__all__ = [
    "KnowledgeGraph",
    "Entity",
    "Relation",
    "Fact",
    "EntityType",
    "RelationType",
    "KnowledgeGraphManager",
    "ExtractionResult",
]
