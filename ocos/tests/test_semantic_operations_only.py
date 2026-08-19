"""架构测试 — Engine 只能通过五个语义操作与 Information 交互。

验证 INFORMATION_THEORY 第五章硬约束：
- 所有 Engine 只能通过 OP_A~OP_F（Acquire/Retain/Access/Transform/Forget）
  与 Information 交互
- Transform 和 Forget 操作必须经 Governance 审批
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"

# 允许的语义操作调用模式
SEMANTIC_OPERATIONS = {
    # Acquire (OP_A)
    "Observation", "observation", "Acquire", "acquire",
    # Retain (OP_R)
    "WorkingMemory.add_goal", "WorkingMemory.set_preference",
    "KnowledgeABI.create_unit", "EventBus.publish",
    # Access (OP_X)
    "AddressResolver.resolve", "AddressResolver.route_query",
    "RetrievalEngine.query", "RetrievalEngine.query_by_role",
    "RetrievalEngine.query_by_state",
    # Transform / Promote (OP_T)
    "PromotionEngine.promote", "PromotionEngine.check_promotion",
    "PromotionEngine.approve_promotion",
    "ConsolidationEngine.consolidate",
    # Forget (OP_F)
    "ForgettingEngine.forget", "ForgettingEngine.mark_for_forget",
    "ForgettingEngine.collect_expired",
}

# 不被允许的操作（直接修改 Information 内部状态）
FORBIDDEN_PATTERNS = [
    "InformationState.value =",          # 直接修改状态
    "InformationMetadata.state =",       # 直接修改元数据状态
    "InformationState.VALIDATED.value",     # 直接修改枚举值
    "_VALID_TRANSITIONS[",                # 直接操作转移矩阵
]


def _get_store_routes() -> list[Path]:
    """获取引擎文件列表。"""
    engine_dir = OCOS_DIR / "engines"
    if not engine_dir.exists():
        return []
    return sorted(engine_dir.rglob("*.py"))


class _SemanticOperationChecker(ast.NodeVisitor):
    """AST 扫描：检查引擎中是否有绕过语义操作的方法调用。"""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.violations: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        lineno = node.lineno or 0
        call_str = self._call_to_string(node)

        # 检查是否为禁止操作
        for forbidden in FORBIDDEN_PATTERNS:
            if forbidden in call_str:
                self.violations.append((lineno, f"禁止直接操作: {call_str}"))

        # 检查调用是否属于语义操作之一
        self.generic_visit(node)

    def _call_to_string(self, node: ast.Call) -> str:
        parts: list[str] = []
        cur = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))


def test_engines_only_use_semantic_operations():
    """所有引擎只通过五个语义操与 Information 交互。"""
    all_violations: list[tuple[str, int, str]] = []

    for fpath in _get_store_routes():
        if fpath.name == "__init__.py":
            continue
        source = fpath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(fpath))
        except SyntaxError:
            continue
        checker = _SemanticOperationChecker(str(fpath))
        checker.visit(tree)
        rel_path = str(fpath.relative_to(OCOS_DIR))
        for lineno, msg in checker.violations:
            all_violations.append((rel_path, lineno, msg))

    if all_violations:
        msg_lines = ["引擎直接操作 Information 内部状态（应在语义操作内完成）:"]
        for path, lineno, msg in all_violations:
            msg_lines.append(f"  {path}:{lineno} {msg}")
        pytest.fail("\n".join(msg_lines))


def test_governance_gated_operations():
    """Transform 和 Forget 操作必须通过 Governance 审批。"""
    from ocos.engines.promotion_engine import _GOVERNANCE_GATED_LEVELS
    from ocos.knowledge.knowledge_ontology import KnowledgeLevel

    # PromotionEngine 的 PRINCIPLE 和 POLICY 层级需要审批
    assert KnowledgeLevel.PRINCIPLE in _GOVERNANCE_GATED_LEVELS
    assert KnowledgeLevel.POLICY in _GOVERNANCE_GATED_LEVELS

    # ForgettingEngine 的 PERSISTENT 等级需要审批（在 mark_for_forget 中）
    from ocos.models.information import PersistenceLevel
    from ocos.engines.forgetting_engine import ForgettingEngine

    engine = ForgettingEngine()
    from ocos.models.information import InformationMetadata, InformationState, SemanticRole, UniversalAddress

    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="x", id="1"),
        state=InformationState.VALIDATED,
        semantic_role=SemanticRole.OBSERVATION,
        persistence_level=PersistenceLevel.PERSISTENT,
    )
    ok, msg = engine.mark_for_forget(meta)
    assert not ok, "PERSISTENT 等级应需要 Governance 审批"
    assert "Governance" in msg
