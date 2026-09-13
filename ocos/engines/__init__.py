"""ocos/engines/ — 认知引擎 (Consolidation/Retrieval/Planning)。

引擎通过模块级 __manifest__ 属性声明元数据 (EngineManifest,
见 ocos/platform/engine_manifest.py 的 EngineDiscoverer 扫描)。
WriterEngine 已归档至 ocos/_archive/engines/（收敛裁决 P1，
writer 角色现役由 DecisionBridge/TaskDAG LLM 承担）。

COG-V2 Phase4 验尸归档（零生产消费者，仅测试引用）：
forgetting/goal_arbitration/policy/prediction/promotion/simulation_engine
与 narrative_pipeline 同目录归档；现役记忆遗忘由 ocos.memory.forgetting
（ForgettingService，dream 附属纯 SQL 服务）承担。
"""

# 统一导出各引擎 manifest (C.5: planning 引擎补 manifest)
from ocos.engines.consolidation_engine import __manifest__ as _consolidation_manifest  # noqa: F401
from ocos.engines.retrieval_engine import __manifest__ as _retrieval_manifest  # noqa: F401
from ocos.engines.planning_engine import __manifest__ as _planning_manifest  # noqa: F401

__all__ = [
    "consolidation_engine",
    "retrieval_engine",
    "planning_engine",
]
