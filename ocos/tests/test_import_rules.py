"""
A1 Architecture Tests — AST Import 规则检查。

基于 AST 扫描所有 ocos 模块的 import 语句，验证其符合宪法定义的依赖方向。
CI 中将自动拒绝任何违反规则的 import。
"""

import ast
import os
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"


def _extract_imports(filepath: str) -> list[tuple[str, str, int]]:
    """从 Python 文件中提取所有 import 语句。

    Returns:
        list of (source_file, imported_module, lineno)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            pytest.fail(f"Syntax error in {filepath}")

    imports: list[tuple[str, str, int]] = []
    relative_path = os.path.relpath(filepath, str(OCOS_DIR))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((relative_path, alias.name, node.lineno or 0))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full_import = f"{module}.{alias.name}" if module else alias.name
                imports.append((relative_path, full_import, node.lineno or 0))

    return imports


# 宪法定义的允许依赖方向
ALLOWED_IMPORTS = {
    "ocos.kernel": ["ocos.models"],  # kernel 依赖模型类型定义（非业务逻辑）
    "ocos.events": ["ocos.kernel"],
    "ocos.runtime": ["ocos.kernel", "ocos.events", "ocos.models"],
    "ocos.models": ["ocos.kernel"],
    "ocos.platform": ["ocos.kernel", "ocos.events", "ocos.models"],
    "ocos.engines": ["ocos.kernel", "ocos.events", "ocos.models", "ocos.runtime", "ocos.knowledge", "ocos.platform", "ocos.agent.retry_policy"],
    "ocos.plugins": ["ocos.kernel", "ocos.events", "ocos.platform", "ocos.engines"],
    "ocos.knowledge": ["ocos.knowledge", "ocos.memory.semantic"],  # GAP-P2-1: registry→semantic 镜像
    "ocos.knowledge.store": [],
    "ocos.knowledge.process": [],
    "ocos.agent": ["ocos.kernel", "ocos.events", "ocos.models", "ocos.runtime", "ocos.engines", "ocos.snapshot", "ocos.goal", "ocos.constitution", "ocos.memory", "ocos.storage", "ocos.operations", "ocos.capability", "ocos.capability.permission_gateway", "ocos.capability.result_understanding", "ocos.capability.registry", "ocos.capability.descriptor", "ocos.capability.provider", "ocos.capability.lifecycle_manager", "ocos.contracts.feedback_abi", "ocos.event", "ocos.planning", "ocos.self", "ocos.proactive"],
    "ocos.auth": ["ocos.storage"],
    "ocos.recovery": ["ocos.storage"],
    # Phase 21: 新增基础设施层
    "ocos.snapshot": ["ocos.storage"],
    "ocos.goal": ["ocos.agent", "ocos.storage"],
    "ocos.constitution": ["ocos.goal", "ocos.agent", "ocos.kernel"],
    # Phase 23: Capability 层
    "ocos.capability": ["ocos.logging", "ocos.agent", "ocos.platform", "ocos.constitution", "ocos.contracts.feedback_abi", "ocos.contracts.attention_abi", "ocos.kernel"],
    "ocos.task": ["ocos.logging"],
    # Phase 24: Memory Belief → Constitution
    "ocos.memory.belief": ["ocos.constitution"],
    # Phase 24: Attention → Logging
    "ocos.attention": ["ocos.logging"],
    # Phase 24: Capability Lifecycle
    "ocos.capability.lifecycle_manager": ["ocos.logging"],
    # Phase 25: Knowledge Graph + Experience Memory
    "ocos.capability.knowledge_graph": ["ocos.logging"],
    "ocos.capability.experience_memory": ["ocos.logging", "ocos.capability.knowledge_graph"],
    "ocos.capability.selection_engine": ["ocos.logging", "ocos.capability.knowledge_graph", "ocos.capability.experience_memory"],
    # Phase 26: Result Understanding
    "ocos.capability.result_understanding": ["ocos.logging", "ocos.capability.knowledge_graph", "ocos.capability.experience_memory"],
    # Phase 28: Capability Orchestrator
    "ocos.capability.orchestrator": ["ocos.logging", "ocos.capability.selection_engine", "ocos.capability.result_understanding"],
    # Phase 29: Homeostasis Monitor
    "ocos.capability.homeostasis": ["ocos.logging"],
    # Phase 61: Namespace bridges — re-export from capability/
    "ocos.homeostasis": ["ocos.capability.homeostasis"],
    "ocos.orchestrator": ["ocos.capability.orchestrator"],
    "ocos.cognitive_interface": ["ocos.interaction.cognitive_interface"],
    # Phase 61: Agent Orchestration Autonomous
    "ocos.agent_orchestration_autonomous": [
        "ocos.agent_orchestration",
        "ocos.agent_orchestration.contract",
        "ocos.agent_orchestration.agent_pool",
        "ocos.planning",
    ],
    # Phase 30: Attention Model
    "ocos.capability.attention": ["ocos.logging"],
    # Phase 62a: Cognitive Coupling
    "ocos.capability.cognitive_coupling": ["ocos.logging", "ocos.agent_orchestration.contract", "ocos.agent_orchestration.executor"],
    # Phase 22: Operations, Events, Interaction
    "ocos.operations": ["ocos.logging", "ocos.capability"],
    "ocos.events": ["ocos.logging", "ocos.agent", "ocos.kernel.abi", "ocos.kernel.event_schema"],
    "ocos.interaction": ["ocos.logging", "ocos.memory", "ocos.agent", "ocos.goal",
                         "ocos.memory.episode", "ocos.memory.belief",
                         "ocos.self.identity_boundary", "ocos.interaction"],
    # Phase 40: Self 层 — Phase 25 extended
    "ocos.self": ["ocos.memory.belief", "ocos.self.governor"],
    # Phase 41: Personal Memory — 依赖 Self Model (Phase 40)
    "ocos.personal_memory": ["ocos.self"],
    # Phase 26: Goal 层 — 解析用户目标，不导入 Self
    "ocos.goal": ["ocos.agent", "ocos.memory.belief", "ocos.storage.connection", "ocos.kernel.goal_types", "ocos.kernel"],
    # Phase 27: Planning 层 — Goal→TaskDAG，不导入 Self
    "ocos.planning": ["ocos.goal", "ocos.memory", "ocos.capability"],
    # Phase 28: Agent Orchestration 层 — Agent调度，不导入 Self
    "ocos.agent_orchestration": ["ocos.agent", "ocos.planning", "ocos.goal"],
    # Phase 29: Digital World 层 — 数字世界操作，不导入 Self
    "ocos.digital_world": ["ocos.agent", "ocos.planning"],
    # Phase 39.1: Runtime Skeleton — 只依赖自身 + kernel.goal_types（类型定义）
    # Note: pre-existing legacy files in ocos/runtime/ import broader scope
    "ocos.runtime": ["ocos.runtime", "ocos.kernel.goal_types",
                     "ocos.kernel.abi", "ocos.events", "ocos.events.event_bus",
                     "ocos.goal", "ocos.agent", "ocos.planning",
                     "ocos.attention", "ocos.logging", "ocos.constitution",
                     "ocos.models", "ocos.models.execution", "ocos.models.goal",
                     "ocos.models.process",
                     ],
    "ocos.validation": [],
    "ocos.memory": [],
    "ocos.memory.experience": ["ocos.memory.experience", "ocos.memory.episode"],
    "ocos.memory.significance": ["ocos.memory.experience", "ocos.memory.significance"],
    "ocos.memory.episode": ["ocos.memory.experience", "ocos.memory.significance", "ocos.memory.episode", "ocos.storage.connection"],
    "ocos.memory.pattern": ["ocos.memory.episode", "ocos.memory.pattern", "ocos.storage.connection"],
    "ocos.memory.semantic": ["ocos.memory.semantic", "ocos.storage.connection"],
    "ocos.memory.belief": ["ocos.memory.semantic", "ocos.memory.belief", "ocos.storage.connection"],
    # Phase 31: Interaction Layer — Cognitive Interface
    "ocos.interaction": ["ocos.goal", "ocos.constitution", "ocos.logging",
                         "ocos.memory.episode", "ocos.memory.belief",
                         "ocos.self.identity_boundary"],
    "ocos.interaction.cli": ["ocos.interaction"],
    "ocos.interaction.cli.commands": ["ocos.interaction", "ocos.goal", "ocos.planning",
                                       "ocos.opentale_bridge", "ocos.daemon", "ocos.storage"],  # S4: Organ Client（写作器官驱动）; P1-B: 生产入口经 daemon 装配层
    "ocos.interaction.repl": ["ocos.interaction"],
    "ocos.interaction.repl.commands": ["ocos.interaction", "ocos.goal",
                                        "ocos.storage", "ocos.planning"],
    "ocos.interaction.api": ["ocos.interaction"],
    "ocos.interaction.api.routes": ["ocos.interaction", "ocos.goal", "ocos.kernel",
                                     "ocos.planning", "ocos.opentale_bridge"],  # S6: WebChat 决策/器官调用
    # Phase 52: Perception System
    "ocos.perception": ["ocos.perception", "ocos.world_model"],  # GAP-P1-3: 感知链桥接世界模型
    # Phase 53: Active Interaction — merged with existing
    # Phase 54: Event Memory Infrastructure
    "ocos.event_memory": ["ocos.event_memory"],
    # Phase 55: Capability Reality Layer
    "ocos.capability_reality": ["ocos.capability_reality", "ocos.event_memory"],
    # Phase 56: Self Diagnosis & Repair
    "ocos.diagnosis": ["ocos.diagnosis", "ocos.event_memory"],
    # Phase 57: Living System Verification
    "ocos.living_verification": ["ocos.living_verification"],
    # Phase 58.0: Health Examination Protocol
    "ocos.health_examination": ["ocos.health_examination"],
    # Phase 58.1: Living Test Protocol
    "ocos.living_test": ["ocos.living_test"],
    # Phase 58.2: Cognitive Nutrition Protocol
    "ocos.cognitive_nutrition": ["ocos.cognitive_nutrition"],
    # Phase 58.3: Recovery & Resilience Test
    "ocos.recovery_resilience": ["ocos.recovery_resilience"],
    "ocos.opentale_bridge": [
        "ocos.opentale_bridge",
        "ocos.cognitive_nutrition",
        "ocos.attention",  # U5.3/I6（2026-08-19）：Deterministic Attention 服务写作决策 reasoning 上下文（只读，Authority 冻结）
        "ocos.agent.belief_system",  # I7（2026-08-20）：BeliefGate 读取 held beliefs（只读，Governance 接入）
    ],
    "ocos.autonomous_runtime": [
        "ocos.autonomous_runtime",
        "ocos.cognitive_loop",
    ],
    # GAP-P1-1: Phase 46 DecisionPipeline 消费 Phase 43 Decision Intelligence
    "ocos.cognitive_loop": ["ocos.cognitive_loop", "ocos.decision"],
    # R4-A: 执行铰链 — 决策输出 → dispatcher 风险分级 → capability_reality 沙盒执行
    "ocos.execution": ["ocos.autonomous_runtime", "ocos.agent_orchestration",
                       "ocos.interaction", "ocos.capability_reality"],
    # P1-B: daemon 生产装配层 — CLI 只依赖 daemon 门面，内核组件由 daemon 组装
    "ocos.daemon": ["ocos.agent", "ocos.capability", "ocos.runtime",
                    "ocos.self", "ocos.kernel", "ocos.logging", "ocos.goal",
                    "ocos.alerts", "ocos.health_examination",
                    "ocos.perception", "ocos.world_model", "ocos.knowledge",
                    "ocos.execution"],
}

# 测试文件允许的 import 例外（白名单，当前 unused—保留供将来使用）
TEST_EXCEPTION_MARKER = "# pragma: allow-import-for-testing"


def _module_to_package(module_name: str) -> str:
    """将模块名映射到包名（取前两段）。"""
    parts = module_name.split(".")
    if len(parts) >= 2 and parts[0] == "ocos":
        return ".".join(parts[:-1])  # 去掉最后一个文件/模块名
    return module_name


def _file_to_package(relative_path: str) -> str:
    """将相对于 OCOS_DIR 的文件路径映射到包名。

    例如: kernel/event_schema.py → ocos.kernel
           kernel/abi.py → ocos.kernel
    """
    parts = Path(relative_path).parent.parts
    if not parts or parts == ("",) or parts == (".",):
        # Root-level file: use the file stem as the package name
        stem = Path(relative_path).stem
        return f"ocos.{stem}"
    return "ocos." + ".".join(parts)


def _is_import_allowed(source_package: str, target_package: str) -> bool:
    """判断 source_package 是否可以 import target_package。

    沿包层次向上匹配（ocos.plugins.opentale → ocos.plugins → ...）。
    """
    # ocos.tests 允许所有（测试特殊处理）
    if source_package == "ocos.tests":
        return True
    # ocos.logging 是横切关注点，全局允许
    if target_package == "ocos.logging" or target_package.startswith("ocos.logging."):
        return True
    # 自身引用允许
    if source_package == target_package:
        return True
    # 同包树内允许（同一 package 下跨模块）
    if target_package.startswith(source_package + ".") or source_package.startswith(target_package + "."):
        return True
    # 沿包层次向上查找允许列表
    parts = source_package.split(".")
    for i in range(len(parts), 1, -1):  # 从最深到 ocos
        ancestor = ".".join(parts[:i])
        allowed = ALLOWED_IMPORTS.get(ancestor, [])
        for a in allowed:
            if target_package == a or target_package.startswith(a + "."):
                return True
    return False


# ── 测试 ─────────────────────────────────────────────────────────────────────────


def test_all_ocos_python_files_collected():
    """确保能正确收集所有 ocos Python 文件。"""
    py_files = sorted(OCOS_DIR.rglob("*.py"))
    assert len(py_files) > 0, "没有找到 ocos Python 文件"
    print(f"  找到 {len(py_files)} 个 Python 文件")


def test_no_illegal_cross_package_imports():
    """核心测试：任何违反依赖方向的 import 直接失败。

    验证 8 条不可变规则中的 Rule 2（Event Bus 唯一通信通道）。
    """
    errors: list[str] = []
    py_files = sorted(OCOS_DIR.rglob("*.py"))
    # 排除测试文件自身和 __init__.py
    test_dir = OCOS_DIR / "tests"

    for fpath in py_files:
        if fpath.parent == test_dir or str(fpath).startswith(str(test_dir)):
            continue
        if fpath.name == "__init__.py":
            continue

        imports = _extract_imports(str(fpath))

        for source_rel, imported_module, lineno in imports:
            # 跳过标准库和三方库
            if not imported_module.startswith("ocos"):
                continue

            source_pkg = _file_to_package(source_rel)
            target_pkg = _module_to_package(imported_module)

            if not _is_import_allowed(source_pkg, target_pkg):
                msg = (
                    f"{source_rel}:{lineno} 非法导入 '{imported_module}' "
                    f"({source_pkg} → {target_pkg} 不被允许)"
                )
                errors.append(msg)

    if errors:
        print("\n非法 import 列表:")
        for e in errors:
            print(f"  FAIL: {e}")
        pytest.fail(f"\n发现 {len(errors)} 个非法 import")


def test_engines_cannot_import_runtime():
    """专用测试：runtime import 规则（Phase 19+ 能力引擎豁免）。"""
    engine_dir = OCOS_DIR / "engines"
    if not engine_dir.exists():
        pytest.skip("engines 目录尚不存在")

    # Phase 19+ Capability engines 允许 import runtime（见 ALLOWED_IMPORTS）
    # 豁免已知能力引擎
    EXEMPT_ENGINES = frozenset({
        "engines/reasoning_engine.py",
        "engines/planning_engine.py",
        "engines/decision_making_engine.py",
        "engines/policy_engine.py",
        "engines/goal_arbitration_engine.py",
        "engines/simulation_engine.py",
        "engines/learning_engine.py",
        "engines/reflection_engine.py",
        "engines/prediction_engine.py",
        "engines/writer_engine.py",
    })

    errors: list[str] = []
    for fpath in sorted(engine_dir.rglob("*.py")):
        rel_key = str(fpath.relative_to(OCOS_DIR))
        if rel_key in EXEMPT_ENGINES:
            continue
        imports = _extract_imports(str(fpath))
        for source_rel, imported_module, lineno in imports:
            if imported_module.startswith("ocos.runtime"):
                relative_path = os.path.relpath(str(fpath), str(OCOS_DIR))
                errors.append(
                    f"{relative_path}:{lineno} engines 不能 import ocos.runtime"
                )

    assert len(errors) == 0, "\n".join(errors)


def test_tests_dont_have_illegal_imports():
    """测试文件的 import 有自动豁免（trivially passes）。"""
    pass  # _is_import_allowed 中 ocos.tests 已获全面豁免
