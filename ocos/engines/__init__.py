"""ocos/engines/ — 认知引擎 (Consolidation/Retrieval/Planning/Writer)。

引擎通过模块级 __manifest__ 属性声明元数据 (EngineManifest,
见 ocos/platform/engine_manifest.py 的 EngineDiscoverer 扫描)。
"""

# 统一导出各引擎 manifest (C.5: planning/writer 引擎补 manifest)
from ocos.engines.consolidation_engine import __manifest__ as _consolidation_manifest  # noqa: F401
from ocos.engines.retrieval_engine import __manifest__ as _retrieval_manifest  # noqa: F401
from ocos.engines.planning_engine import __manifest__ as _planning_manifest  # noqa: F401
from ocos.engines.writer_engine import __manifest__ as _writer_manifest  # noqa: F401

__all__ = [
    "consolidation_engine",
    "retrieval_engine",
    "planning_engine",
    "writer_engine",
]
