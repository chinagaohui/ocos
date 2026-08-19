"""Phase 41: Personal Memory Intelligence — 个人记忆智慧。

三层严格分离:
    Memory            → "发生过什么"
    ExperienceProfile → "呈现什么统计规律" (Phase 40)
    Personal Wisdom   → "未来应该如何判断" (Phase 41)

核心约束:
    PM41-01: Memory ≠ Wisdom          (存储不是理解)
    PM41-02: Pattern ≠ Principle      (统计不是必然)
    PM41-03: Wisdom ≠ Command         (智慧不能直接控制行为)
    PM41-04: Wisdom ≠ Identity        (经验不能改变主体)

智慧链路:
    Experience → Pattern Detection → Candidate Wisdom
    → Validation → Confirmed Wisdom → Application (认知参考)
"""

from ocos.personal_memory.wisdom_types import (
    WisdomState,
    WisdomScope,
    WisdomEvidence,
    WisdomItem,
    WisdomCollection,
)
from ocos.personal_memory.pattern_interpreter import (
    PatternInterpreter,
    InterpretationResult,
)
from ocos.personal_memory.wisdom_validator import (
    WisdomValidator,
    ValidationDecision,
    ValidationResult,
)
from ocos.personal_memory.wisdom_store import WisdomStore
from ocos.personal_memory.reflection_engine import (
    ReflectionEngine,
    ReflectionResult,
)

__all__ = [
    # 类型
    "WisdomState",
    "WisdomScope",
    "WisdomEvidence",
    "WisdomItem",
    "WisdomCollection",
    # 解释
    "PatternInterpreter",
    "InterpretationResult",
    # 验证
    "WisdomValidator",
    "ValidationDecision",
    "ValidationResult",
    # 存储
    "WisdomStore",
    # 反射
    "ReflectionEngine",
    "ReflectionResult",
]
