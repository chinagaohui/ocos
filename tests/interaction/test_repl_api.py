"""Phase 27B/C — REPL + HTTP API 测试。

IFACE-11: REPL shell 初始化
IFACE-12: REPL 命令处理不抛异常
IFACE-13: REPL 权限边界
IFACE-14: API Pydantic 模型验证
IFACE-15: API FastAPI app 路由注册
IFACE-16: API 权限边界
IFACE-17: REPL completer 命令补全
IFACE-18: API 响应模型序列化
IFACE-19: REPL + API 共享 PermissionGuard
IFACE-20: 跨包导入规则
"""

import json

import pytest
from fastapi.testclient import TestClient

from ocos.interaction.base import InteractionSession, PermissionGuard
from ocos.interaction.repl.shell import OcosShell
from ocos.interaction.repl.completer import ReplCompleter, complete_command
from ocos.interaction.api.models import (
    GoalCreateRequest,
    PlanRequest,
    MemoryQueryRequest,
    APIResponse,
    GoalResponse,
    PlanResponse,
    HealthResponse,
    GoalDomainAPI,
    GoalStatusAPI,
)
from ocos.interaction.api.server import app


# ── IFACE-11: REPL shell 初始化 ──────────────────────────────────

def test_repl_shell_init():
    shell = OcosShell()
    assert shell.session is not None
    assert shell.session.caller == "repl"
    assert shell.intro  # has intro text
    assert shell.prompt == "\nOCOS > "


# ── IFACE-12: REPL 命令处理不抛异常 ──────────────────────────────

class TestReplCommands:
    """验证所有 REPL 命令不抛异常。"""

    def test_plan_command(self):
        shell = OcosShell()
        shell.do_plan("帮我写一本科幻小说")

    def test_plan_empty(self):
        shell = OcosShell()
        shell.do_plan("")

    def test_memory_command(self):
        shell = OcosShell()
        shell.do_memory("科幻")

    def test_memory_empty(self):
        shell = OcosShell()
        shell.do_memory("")

    def test_belief_command(self):
        shell = OcosShell()
        shell.do_belief("self")

    def test_belief_empty(self):
        shell = OcosShell()
        shell.do_belief("")

    def test_goal_command(self):
        shell = OcosShell()
        shell.do_goal("")

    def test_goal_with_id(self):
        shell = OcosShell()
        shell.do_goal("GOAL-abc")

    def test_self_command(self):
        shell = OcosShell()
        shell.do_self("")

    def test_trace_command(self):
        shell = OcosShell()
        shell.do_trace("TRACE-001")

    def test_trace_empty(self):
        shell = OcosShell()
        shell.do_trace("")

    def test_help_command(self):
        shell = OcosShell()
        shell.do_help("")
        shell.do_help("plan")
        shell.do_help("unknown")

    def test_default_creates_goal(self):
        shell = OcosShell()
        shell.default("帮我写书")

    def test_default_empty(self):
        shell = OcosShell()
        shell.default("")  # should not raise


# ── IFACE-13: REPL 权限边界 ──────────────────────────────────────

def test_repl_permission_guard_consistent():
    """CLI 和 REPL 使用相同的 PermissionGuard 规则。"""
    guard = PermissionGuard()

    # Allowed
    for action in ["create_goal", "query_memory", "request_plan", "view_belief", "view_self", "view_trace"]:
        assert guard.check(action).allowed, f"REPL should allow {action}"

    # Forbidden
    for action in ["modify_self", "modify_identity", "write_memory", "modify_constitution"]:
        assert not guard.check(action).allowed, f"REPL should reject {action}"


# ── IFACE-14: API Pydantic 模型 ──────────────────────────────────

class TestAPIModels:
    """API 请求/响应模型验证。"""

    def test_goal_create_request_valid(self):
        req = GoalCreateRequest(goal="写书", domain=GoalDomainAPI.writing, priority=3)
        assert req.goal == "写书"
        assert req.domain == GoalDomainAPI.writing
        assert req.priority == 3

    def test_goal_create_request_validation(self):
        # 空 goal
        with pytest.raises(Exception):
            GoalCreateRequest(goal="")
        # 优先级超出范围
        with pytest.raises(Exception):
            GoalCreateRequest(goal="test", priority=0)
        with pytest.raises(Exception):
            GoalCreateRequest(goal="test", priority=6)

    def test_plan_request(self):
        req = PlanRequest(goal="分析市场", domain=GoalDomainAPI.analysis)
        assert req.goal == "分析市场"

    def test_memory_query_request(self):
        req = MemoryQueryRequest(query="科幻", limit=5)
        assert req.query == "科幻"
        assert req.limit == 5

    def test_api_response_model(self):
        resp = APIResponse(success=True, message="ok")
        d = resp.model_dump()
        assert d["success"] is True
        assert d["message"] == "ok"
        assert "timestamp" in d


# ── IFACE-15: API FastAPI app ────────────────────────────────────

def test_app_routes_registered():
    paths = _get_app_paths()
    assert "/ocos/health" in paths, f"Paths: {paths}"
    assert "/ocos/goal" in paths
    assert "/ocos/goal/{goal_id}" in paths
    assert "/ocos/plan" in paths
    assert "/ocos/memory/query" in paths
    assert "/ocos/belief" in paths
    assert "/ocos/trace/{trace_id}" in paths


def _get_app_paths():
    """Extract route paths from app, handling both Route and _IncludedRouter."""
    paths = []
    for r in app.routes:
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "original_router"):
            # _IncludedRouter in FastAPI 0.139+
            for sub in r.original_router.routes:
                if hasattr(sub, "path"):
                    paths.append(sub.path)
    return paths


@pytest.fixture
def client(monkeypatch):
    # S1.2: 业务逻辑测试 — 显式关闭 Bearer Token 门
    monkeypatch.setenv("OCOS_API_AUTH_DISABLED", "true")
    return TestClient(app)


def test_health_check(client):
    resp = client.get("/ocos/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


def test_create_goal_api(client):
    resp = client.post("/ocos/goal", json={
        "goal": "写一本科幻小说",
        "domain": "writing",
        "priority": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "Goal created" in data["message"]


def test_create_goal_empty(client):
    resp = client.post("/ocos/goal", json={"goal": ""})
    assert resp.status_code == 422  # validation error


def test_request_plan_api(client):
    resp = client.post("/ocos/plan", json={
        "goal": "分析科幻小说市场趋势",
        "domain": "analysis",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_query_memory_api(client):
    # S4.2: 占位端点 501 化 — EpisodeStore 未接线不再 200 空结果
    resp = client.post("/ocos/memory/query", json={
        "query": "科幻",
        "limit": 5,
    })
    assert resp.status_code == 501
    assert "not implemented" in str(resp.json()["detail"])


def test_query_beliefs_api(client):
    # S4.2: 占位端点 501 化
    resp = client.get("/ocos/belief?domain=self&min_confidence=0.5&limit=10")
    assert resp.status_code == 501
    assert "not implemented" in str(resp.json()["detail"])


def test_get_trace_api(client):
    # S4.2: 占位端点 501 化
    resp = client.get("/ocos/trace/TRACE-001")
    assert resp.status_code == 501
    assert "not implemented" in str(resp.json()["detail"])


def test_get_goal_api(client):
    # S2.8: GET /ocos/goal/{id} 已接 GoalStore 真实查询——
    # 不存在的目标返回 404（原 TBD 占位恒 200）
    resp = client.get("/ocos/goal/GOAL-nonexistent-xyz")
    assert resp.status_code == 404


# ── IFACE-16: API 权限边界 ───────────────────────────────────────

def test_api_permission_guard_forbidden_actions():
    """API 层拒绝禁止的操作。"""
    guard = PermissionGuard()
    for forbidden in ["modify_self", "modify_identity", "write_memory"]:
        result = guard.check(forbidden)
        assert not result.allowed, f"API should reject {forbidden}"
        assert len(result.violations) > 0


# ── IFACE-17: REPL completer ─────────────────────────────────────

def test_completer_all_commands():
    assert "plan" in complete_command("")
    assert "memory" in complete_command("")
    assert "belief" in complete_command("")
    assert len(complete_command("pl")) == 1
    assert complete_command("pl") == ["plan"]
    assert complete_command("zzz") == []


def test_repl_completer_class():
    c = ReplCompleter()
    cmds = c.commands
    assert "plan" in cmds
    assert "exit" in cmds


# ── IFACE-18: API 响应模型序列化 ─────────────────────────────────

def test_goal_response_serialization():
    resp = GoalResponse(
        goal_id="GOAL-abc",
        status=GoalStatusAPI.pending,
        domain=GoalDomainAPI.writing,
        priority=3,
        caller="api",
        created_at="2026-07-24T00:00:00Z",
    )
    d = json.dumps(resp.model_dump())
    assert "GOAL-abc" in d


def test_plan_response_serialization():
    resp = PlanResponse(
        goal_id="GOAL-abc",
        status=GoalStatusAPI.planning,
        note="Test",
    )
    assert resp.note == "Test"


# ── IFACE-19: REPL + API 共享 PermissionGuard ────────────────────

def test_shared_permission_rules():
    """CLI、REPL、API 使用完全相同的权限检查逻辑。"""
    from ocos.interaction.base import ALLOWED_ACTIONS, FORBIDDEN_ACTIONS

    allowed = set(ALLOWED_ACTIONS)
    forbidden = set(FORBIDDEN_ACTIONS)

    # 无交集（一个操作不能既允许又禁止）
    assert allowed & forbidden == set(), "ALLOWED and FORBIDDEN must be disjoint"

    # 6 条禁止规则
    assert len(forbidden) == 6

    # 10 条允许规则（2026-08-23 增 analyze_quality/analyze_trend；
    # S1.3 增 self_improve/approve_action——API 写面显式白名单）
    assert len(allowed) == 10


# ── IFACE-20: 跨包导入规则 ───────────────────────────────────────

def test_repl_api_imports_stay_within_boundary():
    """REPL 和 API 不导入 Self/Belief 写接口。"""
    import ast
    from pathlib import Path

    forbidden = {
        "ocos.self.self_model",
        "ocos.self.monitor",
        "ocos.self.governor",
    }

    # Allowed exceptions — context.py is the designated bridge
    allowed_exceptions = {
        "ocos.memory.belief.store.BeliefStore",
        "ocos.memory.belief.models.BeliefStatus",
        "ocos.memory.episode.store.EpisodeStore",
        "ocos.self.identity_boundary.IdentityBoundary",
        "ocos.goal.models",
        "ocos.storage.connection",
    }

    interaction_root = Path(__file__).parent.parent.parent / "ocos" / "interaction"

    violations = []
    for f in interaction_root.rglob("*.py"):
        try:
            tree = ast.parse(f.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "")
                names = [a.name for a in node.names]
                for name in (names if isinstance(node, ast.Import) else [f"{module}.{n}" for n in names]):
                    for fb in forbidden:
                        if name == fb or name.startswith(fb):
                            # Check if this is an allowed exception (context.py bridge)
                            if any(name == ae or name.startswith(ae) for ae in allowed_exceptions):
                                continue
                            violations.append(f"{f.relative_to(interaction_root.parent)}: {name}")

    assert not violations, f"Illegal imports in REPL/API: {violations}"
