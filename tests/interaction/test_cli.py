"""Phase 27A — CLI 入口测试。

IFACE-01: GoalRequest 权限边界 — 拒绝不合法 caller
IFACE-02: GoalRequest → UserGoal 转换 — 合法输入通过
IFACE-03: PermissionGuard — ALLOWED_ACTIONS 通过
IFACE-04: PermissionGuard — FORBIDDEN_ACTIONS 拒绝
IFACE-05: CLI goal create — 端到端集成
IFACE-06: CLI plan — 端到端集成
IFACE-07: CLI memory/belief/self/trace — 只读命令
IFACE-08: CLI 无参数 — help 输出
IFACE-09: InteractionSession 记录计数
IFACE-10: 跨包导入规则 — interaction 不依赖 foridden imports
"""

import pytest

from ocos.interaction.base import (
    ALLOWED_ACTIONS,
    FORBIDDEN_ACTIONS,
    GoalRequest,
    InteractionSession,
    PermissionGuard,
)
from ocos.goal.models import GoalDomain, GoalSource, GoalStatus, UserGoal, CALLER_WHITELIST
from ocos.interaction.cli.main import main


# ── IFACE-01: 权限边界 — 不合法 caller ─────────────────────────────

def test_goal_request_rejects_unknown_caller():
    with pytest.raises(ValueError, match="not in CALLER_WHITELIST"):
        GoalRequest.create(
            raw_input="test",
            objective="test",
            domain=GoalDomain.WRITING,
            caller="hacker",
        )


# ── IFACE-02: GoalRequest → UserGoal 转换 ──────────────────────────

def test_goal_request_to_user_goal_valid():
    req = GoalRequest.create(
        raw_input="帮我写书",
        objective="写一本小说",
        domain=GoalDomain.WRITING,
        caller="cli",
        priority=4,
    )
    goal = req.to_user_goal()

    assert goal.id.startswith("GOAL-")
    assert goal.raw_input == "帮我写书"
    assert goal.objective == "写一本小说"
    assert goal.domain == GoalDomain.WRITING
    assert goal.source == GoalSource.HUMAN
    assert goal.caller == "cli"
    assert goal.priority == 4
    assert goal.status == GoalStatus.PENDING


def test_goal_request_create_with_constraints():
    req = GoalRequest.create(
        raw_input="写科幻",
        objective="写科幻小说",
        domain=GoalDomain.WRITING,
        caller="orchestrator",
        constraints=("字数 > 50000", "角色 > 5"),
    )
    goal = req.to_user_goal()
    assert len(goal.constraints) == 2
    assert "字数 > 50000" in goal.constraints
    assert goal.source == GoalSource.HUMAN
    assert goal.caller == "orchestrator"


# ── IFACE-03: PermissionGuard — ALLOWED_ACTIONS 通过 ───────────────

@pytest.mark.parametrize("action", [
    "create_goal",
    "query_memory",
    "request_plan",
    "view_belief",
    "view_self",
    "view_trace",
])
def test_permission_guard_allows_valid_actions(action):
    guard = PermissionGuard()
    result = guard.check(action)
    assert result.allowed, f"Expected allowed for '{action}', got: {result.violations}"


# ── IFACE-04: PermissionGuard — FORBIDDEN_ACTIONS 拒绝 ─────────────

@pytest.mark.parametrize("action", [
    "modify_self",
    "modify_identity",
    "write_memory",
    "modify_goal",
    "modify_constitution",
])
def test_permission_guard_rejects_forbidden_actions(action):
    guard = PermissionGuard()
    result = guard.check(action)
    assert not result.allowed, f"Expected rejection for '{action}'"
    assert any("FORBIDDEN" in v for v in result.violations)


def test_permission_guard_rejects_unknown_action():
    guard = PermissionGuard()
    result = guard.check("delete_everything")
    assert not result.allowed
    assert any("not in ALLOWED_ACTIONS" in v for v in result.violations)


# ── IFACE-05: CLI goal create ──────────────────────────────────────

def test_cli_goal_create():
    exit_code = main(["goal", "create", "写一本科幻小说"])
    assert exit_code == 0


# ── IFACE-06: CLI plan ─────────────────────────────────────────────

def test_cli_plan():
    exit_code = main(["plan", "分析市场", "--domain", "analysis"])
    assert exit_code == 0


# ── IFACE-07: CLI 只读命令 ─────────────────────────────────────────

def test_cli_memory_query():
    assert main(["memory", "query", "科幻"]) == 0

def test_cli_memory_recent():
    assert main(["memory", "recent"]) == 0

def test_cli_belief_list():
    assert main(["belief", "list"]) == 0

def test_cli_belief_summary():
    assert main(["belief", "summary"]) == 0

def test_cli_self_status():
    assert main(["self", "status"]) == 0

def test_cli_self_identity():
    assert main(["self", "identity"]) == 0

def test_cli_trace_show():
    # S4.2: 决策追踪存储未接线 → 明确"未实现"退出码 2（原 0 误导脚本）
    assert main(["trace", "show", "TRACE-001"]) == 2

def test_cli_goal_status():
    # FIX-VAL2: 不存在的 goal 必须返回非零（脚本化语义），而非静默 0
    assert main(["goal", "status", "GOAL-nonexistent00"]) == 1

def test_cli_goal_list():
    assert main(["goal", "list"]) == 0


# ── IFACE-08: CLI 无参数 help ──────────────────────────────────────

def test_cli_no_args_shows_help():
    exit_code = main([])
    assert exit_code == 1  # no command = error + help


# ── IFACE-09: InteractionSession ───────────────────────────────────

def test_interaction_session_recording():
    session = InteractionSession(caller="cli")
    assert session.goals_created == []
    assert session.queries_made == 0

    session.record_goal("GOAL-001")
    session.record_goal("GOAL-002")
    session.record_query()
    session.record_query()

    assert len(session.goals_created) == 2
    assert session.queries_made == 2

    summary = session.summary
    assert summary["caller"] == "cli"
    assert summary["goals_created"] == 2
    assert summary["queries_made"] == 2


# ── IFACE-10: 跨包导入规则 ─────────────────────────────────────────

def test_interaction_does_not_import_forbidden():
    """Interaction Layer 不能导入被宪法禁止的模块。"""
    import ast
    from pathlib import Path

    forbidden_imports = {
        "ocos.self.self_model",   # Self 层在 interaction 之上
        "ocos.self.monitor",      # Self 演化在 interaction 之上
    }

    interaction_root = Path(__file__).parent.parent.parent / "ocos" / "interaction"
    files = list(interaction_root.rglob("*.py"))

    violations = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_imports:
                        if alias.name == forbidden or alias.name.startswith(forbidden):
                            violations.append(f"{f.name}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_imports:
                        if node.module == forbidden or (
                            node.module and forbidden and node.module.startswith(forbidden)
                        ):
                            violations.append(
                                f"{f.name}: from {node.module} import ..."
                            )

    assert len(violations) == 0, f"Interaction layer has forbidden imports: {violations}"
