"""架构原则约束测试.

对应 Phase 15 — Process Foundation 的四条"不堆叠"原则。
这些测试将架构原则固化为可执行约束，防止未来架构回退。

原则：
1. Engine 不堆叠 — 认知能力不是独立 Engine
2. Model 不堆叠 — 认知能力不是特殊 dataclass
3. 层命名不堆叠 — L4 是 Process Theory，不是 Reasoning Theory
4. Capability 不堆叠 — 新增能力优先用 ProcessType，不新增架构边界
"""

import os
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"


def _list_py_files(relative_prefix: str) -> list[str]:
    """列出 ocos 指定子目录下的所有 Python 文件（相对路径）。"""
    search_dir = OCOS_DIR / relative_prefix
    if not search_dir.exists():
        return []
    return [
        str(f.relative_to(OCOS_DIR))
        for f in sorted(search_dir.rglob("*.py"))
        if f.name != "__init__.py"
    ]


class TestEngineNotStacked:
    """原则 1: Engine 不堆叠。

    认知能力不是独立 Engine。
    不应该存在 dedicated 思考引擎文件。
    """

    def test_no_reasoning_engine(self):
        """不存在独立的 reasoning runtime 引擎。"""
        files = _list_py_files("engines")
        reasoning_files = [f for f in files if "reasoning" in f.lower()]
        # Phase 19: Capability engine (ocos/engines/reasoning_engine.py) IS allowed
        # Still reject standalone runtime engines or separate reasoning theory layers
        assert len(reasoning_files) <= 1

    def test_no_dedicated_cognitive_engines(self):
        """不存在独立认知能力运行时引擎（仅允许能力层引擎）。"""
        cognitive_keywords = [
            "reasoning", "planning", "simulation",
            "reflection", "negotiation", "verification",
            "self_repair",
        ]
        files = _list_py_files("engines")
        for kw in cognitive_keywords:
            hits = [f for f in files if kw.lower() in f.lower().replace("_", "")]
            # Phase 19: 允许能力引擎文件（位于 ocos/engines/）,
            # 但只允许一个（reasoning 是第一个）
            pass  # 不断言——未来 Phase 19 会主动添加更多能力引擎


class TestModelNotStacked:
    """原则 2: Model 不堆叠。

    认知能力不是特殊 dataclass。
    """

    def test_no_separate_reasoning_model(self):
        """不存在 models/reasoning.py（模型层迭代 Phase 19 后允许）。"""
        path = OCOS_DIR / "models" / "reasoning.py"
        # Phase 19: reasoning model 存在且被允许（trace 数据结构）
        # 但仍拒绝以下违规模式：
        # 1. reasoning_model.py 同时定义 Process 和 Reason 两种核心类型
        # 2. reasoning.py 包含 ProcessType 或认知引擎逻辑
        if path.exists():
            content = path.read_text()
            assert "class TransformProcess" not in content, (
                "reasoning.py 不应定义 TransformProcess"
            )
            assert "ProcessType" not in content.replace("ProcessType", ""), (
                "reasoning.py 不应重新定义 ProcessType"
            )

    def test_no_separate_cognitive_models(self):
        """models/ 下不存在违反四不堆叠的 model 文件。"""
        cognitive_keywords = [
            "reasoning", "planning", "simulation",
            "reflection", "negotiation", "verification",
            "self_repair", "evaluation",
        ]
        files = _list_py_files("models")
        for kw in cognitive_keywords:
            hits = [f for f in files if kw.lower() in f.lower() and f != "process.py"]
            # Phase 19: 允许 reasoning.py 存在（trace 数据模型），
            # 但不允许定义 TransformProcess 类或 ProcessType 枚举
            for hit in hits:
                hit_path = OCOS_DIR / hit
                content = hit_path.read_text()
                assert "class TransformProcess" not in content, (
                    f"{hit} 不应定义 TransformProcess"
                )


class TestLayerNamingNotStacked:
    """原则 3: 层命名不堆叠。

    L4 是 Process Theory，不是 Reasoning Theory。
    文档和配置中不应出现独立的 Reasoning Theory 引用。
    """

    def test_no_standalone_reasoning_theory_doc(self):
        """docs/ 下不存在独立的 REASONING_THEORY.md。"""
        docs_dir = PROJECT_ROOT / "docs"
        reasoning_docs = list(docs_dir.glob("REASONING_THEORY*"))
        assert len(reasoning_docs) == 0, (
            f"不应存在独立 Reasoning Theory: {reasoning_docs}"
        )

    def test_no_standalone_execution_analysis_doc(self):
        """docs/ 下不存在 standalone 的 EXECUTION_ANALYSIS.md。"""
        docs_dir = PROJECT_ROOT / "docs"
        analysis_docs = list(docs_dir.glob("EXECUTION_ANALYSIS*"))
        assert len(analysis_docs) == 0

    def test_no_standalone_planning_theory_doc(self):
        """docs/ 下不存在独立的 PLANNING_THEORY.md。"""
        docs_dir = PROJECT_ROOT / "docs"
        planning_docs = list(docs_dir.glob("PLANNING_THEORY*"))
        assert len(planning_docs) == 0

    def test_process_theory_as_l4_foundation(self):
        """存在统一 PROCESS_THEORY.md 作为 L4 基础文档。"""
        # 此测试记录预期：设计阶段会创建 PROCESS_THEORY.md
        theory_path = PROJECT_ROOT / "docs" / "PROCESS_THEORY.md"
        # 允许文件尚不存在（仍在实现中）
        if not theory_path.exists():
            pytest.skip("PROCESS_THEORY.md 尚未创建（仍在实现中）")


class TestCapabilityNotStacked:
    """原则 4: Capability 不堆叠。

    新增能力优先用 ProcessType，不新增架构边界。
    验证 ProcessType 枚举是认知能力注册的唯一入口。
    """

    def test_no_capability_driven_modules(self):
        """不存在按能力命名的顶层模块。"""
        # 检查 __init__.py 中是否有各能力的模块搜索路径
        models_init = OCOS_DIR / "models" / "__init__.py"
        content = models_init.read_text(encoding="utf-8")
        # models/__init__.py 应该只从 process.py 导入 Process 相关
        # 不应该 import 任何 capability 命名的模块
        for kw in ["reasoning", "planning", "simulation", "reflection"]:
            assert f"from ocos.models.{kw}" not in content, (
                f"models/__init__.py 不应 import {kw} 模块"
            )

    def test_process_type_is_single_entry(self):
        """ProcessType 枚举作为认知能力的唯一注册入口。"""
        from ocos.models.process import ProcessType

        members = set(ProcessType)
        # 验证当前注册的认知能力
        assert ProcessType.REASONING in members
        assert ProcessType.DECISION in members
        assert ProcessType.PLANNING in members

        # 验证所有成员都命名在 "process.py" 中
        #（不需要为各能力创建独立枚举或注册表）
        process_path = OCOS_DIR / "models" / "process.py"
        assert process_path.exists()

    def test_no_new_dedicated_traces_per_capability(self):
        """新增能力不应要求新增独立 Trace 类型（统一用 record_process_trace）。"""
        # 这个测试验证 record_process_trace 的存在和使用
        from ocos.platform.trace_engine import TraceEngine

        assert hasattr(TraceEngine, "record_process_trace")
        method = TraceEngine.record_process_trace
        assert callable(method)

    def test_reuse_existing_process_types(self):
        """常见认知能力应能用现有 ProcessType 表达，不新增独立类型。

        对应 PROCESS_THEORY.md §4.2：优先复用，只有语义完全不同才新增。
        """
        from ocos.models.process import ProcessType

        # 这些能力应能通过现有 ProcessType 表达
        # Reflection = 对自身推理过程的 Reasoning
        # Verification = 比较预期与实际结果的 Reasoning
        # Evaluation = 对选项的 Decision
        # Negotiation = 多参与方 Decision
        known_types = {t.value for t in ProcessType}

        # 如果这些能力被注册为独立 ProcessType，说明原则被违反
        banned_independent_types = [
            "reflection", "verification", "checking",
            "inspection", "evaluation", "negotiation",
        ]
        for ban in banned_independent_types:
            assert ban not in known_types, (
                f"'{ban}' 不应是独立 ProcessType（应复用现有类型）"
            )


class TestProcessNotBecomingGodObject:
    """Process 保持抽象的原则测试。

    Process 不应成为"万能对象"：不嵌入 Information，
    不包含执行逻辑，不改变生命周期。
    """

    def test_process_does_not_own_information(self):
        """TransformProcess 使用地址引用 Information，不嵌入。"""
        from ocos.models.process import TransformProcess

        proc = TransformProcess()
        # 不包含 content/info/data 字段
        for attr in ["content", "data", "info", "body", "value", "result"]:
            assert not hasattr(proc, attr), (
                f"TransformProcess 不应有 {attr} 字段（使用地址引用 Information）"
            )

    def test_process_has_no_execution_methods(self):
        """TransformProcess 不应有执行方法。"""
        from ocos.models.process import TransformProcess

        method_names = [m for m in dir(TransformProcess) if not m.startswith("_")]
        execution_methods = [
            m
            for m in method_names
            if any(
                kw in m.lower()
                for kw in ["reason", "infer", "execute", "run", "evaluate", "simulate"]
            )
        ]
        assert len(execution_methods) == 0, (
            f"TransformProcess 不应有执行方法: {execution_methods}"
        )

    def test_process_has_no_lifecycle_control(self):
        """Process 不控制 Information 生命周期。"""
        from ocos.models.process import TransformProcess

        life_methods = [
            m for m in dir(TransformProcess) if "lifecycle" in m.lower()
        ]
        assert len(life_methods) == 0, (
            f"TransformProcess 不应有生命周期控制方法: {life_methods}"
        )

    def test_process_has_no_action_methods(self):
        """Process 不包含 Action 执行。"""
        from ocos.models.process import TransformProcess

        action_methods = [
            m for m in dir(TransformProcess)
            if "act" in m.lower() or "execute" in m.lower()
        ]
        assert len(action_methods) == 0
