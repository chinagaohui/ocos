"""OCOS Knowledge — 知识平面（v1.0 拆分版）。

知识平面提供知识的结构化定义、生命周期管理、验证和演进能力。

## 子平面结构

- `store/` — 知识存储子平面（ontology / registry / lifecycle）
- `process/` — 知识处理子平面（validator / evolution / promotion_rules）
- `knowledge_abi.py` — 统一 ABI 门面

## 公开 API

- `KnowledgeLevel` — 知识层级枚举
- `KnowledgeStatus` — 知识状态枚举
- `KnowledgeUnit` — 知识单元数据类
- `ElevationRecord` — 提升记录
- `ELEVATION_MATRIX` — 层级提升关系矩阵
- `can_elevate`, `validate_elevation` — 提升校验函数
- `AccessScope`, `AccessMatrix` — 访问控制
- `KnowledgeRegistry` — 知识注册中心
- `KnowledgeLifecycle` — 知识生命周期管理
- `KnowledgeABI` — 知识平面 ABI 接口
- `KnowledgeValidator` — 知识验证器
- `ValidationReport` — 验证报告
- `EvolutionManager`, `EvolutionProposal` — 知识演进管理
- `PromotionRuleEngine`, `PromotionPolicy` — 提升规则引擎
"""

from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    ElevationRecord,
    ELEVATION_MATRIX,
    can_elevate,
    validate_elevation,
)
from ocos.knowledge.store.registry import (
    AccessScope,
    AccessMatrix,
    KnowledgeRegistry,
)
from ocos.knowledge.store.lifecycle import KnowledgeLifecycle
from ocos.knowledge.knowledge_abi import KnowledgeABI
from ocos.knowledge.process.validator import KnowledgeValidator, ValidationReport
from ocos.knowledge.process.evolution import (
    EvolutionChangeType,
    EvolutionProposalStatus,
    EvolutionProposal,
    EvolutionManager,
)
from ocos.knowledge.process.promotion_rules import PromotionRuleEngine, PromotionPolicy

__all__ = [
    "KnowledgeLevel",
    "KnowledgeStatus",
    "KnowledgeUnit",
    "ElevationRecord",
    "ELEVATION_MATRIX",
    "can_elevate",
    "validate_elevation",
    "AccessScope",
    "AccessMatrix",
    "KnowledgeRegistry",
    "KnowledgeLifecycle",
    "KnowledgeABI",
    "KnowledgeValidator",
    "ValidationReport",
    "EvolutionChangeType",
    "EvolutionProposalStatus",
    "EvolutionProposal",
    "EvolutionManager",
    "PromotionRuleEngine",
    "PromotionPolicy",
]
