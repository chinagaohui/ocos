"""Phase 49-C: Skill 生长 + 失败重规划测试 (Blueprint L4/L5/L6)。

验收对应:
    L4 (C1): Replanner — 失败→重试/跳过/替代决策
    L5 (C2): SkillProposer — 成功≥3 → 候选 (N=候选生成阈值, 非成立阈值)
    L5/L6 (C3): GovernedSkillCommitter — 验证/审批/注册 四段
"""

from __future__ import annotations

import pytest

from ocos.learning.skill_growth import (
    CANDIDATE_MIN_SUCCESS,
    GovernedSkillCommitter,
    ReplanAction,
    ReplanDecision,
    SkillProposal,
    SkillProposalStatus,
    SkillProposer,
    TaskReplanner,
)


# ═══════════════════════════════════════════════════════════════════════════════
# C1 — Replanner (L4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskReplanner:
    """L4: 失败→动作决策。"""

    def test_ambiguous_blocks(self):
        d = TaskReplanner.decide("T-1", "ambiguous_task")
        assert d.action == ReplanAction.AMBIGUOUS_BLOCK
        assert d.retryable is False
        assert TaskReplanner.is_terminal(d) is True

    def test_execution_error_retryable(self):
        d = TaskReplanner.decide("T-2", "execution_error", retry_count=0)
        assert d.action == ReplanAction.RETRY
        assert d.retryable is True
        assert TaskReplanner.should_retry(d) is True

    def test_retry_exhausted_skips(self):
        d = TaskReplanner.decide("T-3", "execution_error", retry_count=2)
        assert d.action == ReplanAction.SKIP_DEPENDENTS
        assert d.retryable is False
        assert TaskReplanner.is_terminal(d) is True
        assert "exceeds max" in d.reason

    def test_permission_denied_continues(self):
        d = TaskReplanner.decide("T-4", "permission_denied")
        assert d.action == ReplanAction.CONTINUE_NEXT
        assert d.retryable is False

    def test_tool_unavailable_skips(self):
        d = TaskReplanner.decide("T-5", "tool_unavailable")
        assert d.action == ReplanAction.SKIP_DEPENDENTS

    def test_unknown_continues(self):
        d = TaskReplanner.decide("T-6", "unknown")
        assert d.action == ReplanAction.CONTINUE_NEXT

    def test_retry_policy_fields(self):
        d = TaskReplanner.decide("T-7", "timeout", retry_count=1)
        assert d.action == ReplanAction.RETRY
        assert d.retry_count == 1
        assert d.cause == "timeout"


# ═══════════════════════════════════════════════════════════════════════════════
# C2 — SkillProposer (L5)
# ═══════════════════════════════════════════════════════════════════════════════


def make_episode(ep_id, goal, success=True, agent="researcher",
                 task_type="analyze"):
    """构造最小 Episode 形状。"""
    outcome = {"success": success}
    return type("FakeEpisode", (), {
        "id": ep_id,
        "goal": goal,
        "outcome": outcome,
        "context": {"agent": agent, "task_type": task_type},
        "decision": "completed" if success else "failed",
    })()


class TestSkillProposer:
    """L5: 成功 N 次 → 候选。"""

    def test_below_threshold_no_proposal(self):
        eps = [
            make_episode("E1", "检查磁盘空间"),
            make_episode("E2", "检查磁盘空间"),
        ]
        proposals = SkillProposer.propose_from_episodes(eps)
        assert proposals == []  # 2 < 3

    def test_at_threshold_proposes(self):
        eps = [
            make_episode("E1", "检查磁盘空间"),
            make_episode("E2", "检查磁盘空间"),
            make_episode("E3", "检查磁盘空间"),
        ]
        proposals = SkillProposer.propose_from_episodes(eps)
        assert len(proposals) == 1
        p = proposals[0]
        assert p.status == SkillProposalStatus.CANDIDATE
        assert p.success_count == 3
        assert p.trigger_pattern == "检查磁盘空间"
        assert p.source_episodes == ("E1", "E2", "E3")

    def test_failures_excluded(self):
        eps = [
            make_episode("E1", "任务X", success=True),
            make_episode("E2", "任务X", success=False),
            make_episode("E3", "任务X", success=True),
        ]
        proposals = SkillProposer.propose_from_episodes(eps)
        assert proposals == []  # 成功仅 2 < 3

    def test_analyze_is_read_only(self):
        """analyze/verify 类 → 不要求审批。"""
        eps = [
            make_episode(f"E{i}", "查询日志", task_type="analyze")
            for i in range(3)
        ]
        proposals = SkillProposer.propose_from_episodes(eps)
        assert len(proposals) == 1
        assert proposals[0].approval_required is False

    def test_execute_is_write_requires_approval(self):
        """execute/create 类 → 即使成功也需审批 (治理)。"""
        eps = [
            make_episode(f"E{i}", "部署服务", task_type="execute")
            for i in range(5)
        ]
        proposals = SkillProposer.propose_from_episodes(eps)
        assert len(proposals) == 1
        assert proposals[0].approval_required is True  # N=5 也不授予

    def test_candidate_threshold_value(self):
        assert CANDIDATE_MIN_SUCCESS == 3


# ═══════════════════════════════════════════════════════════════════════════════
# C3 — GovernedSkillCommitter (L5/L6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGovernedCommitter:
    """L5/L6: 候选→验证→审批→注册。"""

    def _proposal(self, approval_required=False):
        return SkillProposal(
            skill_id="SKL-abc", name="auto:检查磁盘",
            trigger_pattern="检查磁盘空间",
            procedure=("researcher:analyze",),
            success_count=3, confidence=0.8,
            approval_required=approval_required,
        )

    def test_validate_read_only(self):
        p = self._proposal(approval_required=False)
        v = GovernedSkillCommitter.validate(p)
        assert v.status == SkillProposalStatus.VALIDATED

    def test_validate_write_stays_candidate(self):
        p = self._proposal(approval_required=True)
        v = GovernedSkillCommitter.validate(p)
        assert v.status == SkillProposalStatus.CANDIDATE  # 等待审批

    def test_approve_write(self):
        p = self._proposal(approval_required=True)
        a = GovernedSkillCommitter.approve(p, approval_id="APPR-1")
        assert a.status == SkillProposalStatus.VALIDATED
        assert a.approval_id == "APPR-1"
        assert a.approval_required is False

    def test_commit_only_validated(self):
        """CANDIDATE 不可注册 — 治理。"""
        registry = _FakeRegistry()
        p = self._proposal(approval_required=False)  # CANDIDATE
        result = GovernedSkillCommitter.commit(p, registry)
        assert result is None  # 未验证不注册
        assert registry.saved == []

    def test_commit_validated_saves(self):
        registry = _FakeRegistry()
        p = self._proposal(approval_required=False)
        v = GovernedSkillCommitter.validate(p)
        skill = GovernedSkillCommitter.commit(v, registry)
        assert skill is not None
        assert registry.saved == [skill]
        assert skill.id == "SKL-abc"

    def test_commit_after_approval(self):
        """写类: 审批后 VALIDATED → 可注册。"""
        registry = _FakeRegistry()
        p = self._proposal(approval_required=True)
        a = GovernedSkillCommitter.approve(p, "APPR-2")
        skill = GovernedSkillCommitter.commit(a, registry)
        assert skill is not None
        assert registry.saved == [skill]

    def test_write_skill_registered_still_governed(self):
        """注册后无 execute 权限 — Skill 本身不含执行权。"""
        registry = _FakeRegistry()
        p = self._proposal(approval_required=True)
        a = GovernedSkillCommitter.approve(p, "APPR-3")
        skill = GovernedSkillCommitter.commit(a, registry)
        assert skill is not None
        # Skill 对象无 execute/act 方法 — 执行权在 DecisionBridge
        assert not hasattr(skill, "execute")
        assert not hasattr(skill, "act")


class _FakeRegistry:
    """最小 SkillRegistry 替身。"""

    def __init__(self):
        self.saved = []

    def save_skill(self, skill):
        self.saved.append(skill)


# ═══════════════════════════════════════════════════════════════════════════════
# 集成: AgentRuntime._replan_failed_task + MasterAgent.grow_skills
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentRuntimeReplanIntegration:
    """L4 集成: AgentRuntime 失败重规划。"""

    def _make_runtime(self):
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.agent.master_agent import MasterAgent
        from ocos.agent.capability_manager import CapabilityManager
        from ocos.agent.execution_manager import ExecutionManager
        from ocos.agent.goal_stack import GoalStack
        from ocos.agent.intent import Intent
        from ocos.agent.state import AgentState

        class FakeIdentity:
            def verify(self): return True
            def get_identity_id(self): return "id-1"

        class FakeAttention:
            def current_focus(self): return None

        class FakeWM:
            def add(self, item): return None

        agent = MasterAgent(
            agent_id="test", identity=FakeIdentity(),
            goal_stack=GoalStack(), intent=Intent(),
            attention=FakeAttention(), working_memory=FakeWM(),
            capability_manager=CapabilityManager(),
            execution_manager=ExecutionManager(),
            state=AgentState(),
        )
        rt = AgentRuntime.__new__(AgentRuntime)  # 跳过完整 boot
        rt._task_retry_count = {}
        rt.agent = agent
        return rt

    def test_retryable_failure_schedules_retry(self):
        rt = self._make_runtime()
        task = type("T", (), {"description": "运行 python 脚本",
                              "task_type": "execute",
                              "agent_type": "researcher"})()
        meta = rt._replan_failed_task("TASK-1", task,
                                      "exit=2: module not found")
        assert meta["decision"] == "retry_pending"
        assert meta["cause"] == "execution_error"
        assert rt._task_retry_count.get("TASK-1") == 1

    def test_ambiguous_failure_terminal(self):
        rt = self._make_runtime()
        task = type("T", (), {"description": "分析数据",
                              "task_type": "analyze",
                              "agent_type": "researcher"})()
        meta = rt._replan_failed_task("TASK-2", task,
                                      "任务描述\"分析数据\"过于模糊")
        assert meta["decision"] != "retry_pending"
        assert meta["cause"] == "ambiguous_task"
        assert rt._task_retry_count.get("TASK-2") is None

    def test_retry_exhausted_terminal(self):
        rt = self._make_runtime()
        task = type("T", (), {"description": "任务X",
                              "task_type": "execute",
                              "agent_type": "researcher"})()
        rt._task_retry_count["TASK-3"] = 2  # 已达上限
        meta = rt._replan_failed_task("TASK-3", task, "exit=1: boom")
        assert meta["decision"] != "retry_pending"
        assert meta["cause"] == "execution_error"


class _FakeEpisodeStore:
    def __init__(self, saved):
        self.saved = saved

    def save(self, episode):
        self.saved.append(episode)


class _FakeHub:
    """P5.1: 最小 MemoryHub 替身（is_initialized + episode.save）。"""

    def __init__(self):
        self.saved = []
        self.episode = _FakeEpisodeStore(self.saved)

    def is_initialized(self):
        return True


class TestP51FailureLessonPipeline:
    """P5.1 (AGI 计划): 失败归因重规划 — 教训回学习管道。"""

    def _make_runtime(self):
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.agent.master_agent import MasterAgent
        from ocos.agent.capability_manager import CapabilityManager
        from ocos.agent.execution_manager import ExecutionManager
        from ocos.agent.goal_stack import GoalStack
        from ocos.agent.intent import Intent
        from ocos.agent.state import AgentState

        class FakeIdentity:
            def verify(self): return True
            def get_identity_id(self): return "id-1"

        class FakeAttention:
            def current_focus(self): return None

        class FakeWM:
            def add(self, item): return None

        agent = MasterAgent(
            agent_id="test", identity=FakeIdentity(),
            goal_stack=GoalStack(), intent=Intent(),
            attention=FakeAttention(), working_memory=FakeWM(),
            capability_manager=CapabilityManager(),
            execution_manager=ExecutionManager(),
            state=AgentState(),
        )
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._task_retry_count = {}
        rt.agent = agent
        rt._memory_hub = _FakeHub()
        return rt

    def test_terminal_failure_records_lesson(self):
        """不可修正失败（模糊任务）→ failure_lesson 入库且带结构化 cause。"""
        rt = self._make_runtime()
        task = type("T", (), {"description": "分析数据",
                              "task_type": "analyze",
                              "agent_type": "researcher"})()
        meta = rt._replan_failed_task("TASK-1", task,
                                      "任务描述\"分析数据\"过于模糊")
        assert meta["decision"] != "retry_pending"
        lesson = meta.get("lesson", {})
        assert lesson.get("recorded") is True
        assert lesson.get("cause") == "ambiguous_task"
        assert lesson.get("artifact_id", "").startswith("ART-")
        # Episode 已落 hub（source="lesson", 带 failure_lesson 标签）
        eps = rt._memory_hub.saved
        assert len(eps) == 1
        assert eps[0].source == "lesson"
        assert "failure_lesson" in eps[0].tags
        assert eps[0].outcome["cause"] == "ambiguous_task"

    def test_retry_exhausted_records_lesson(self):
        """重试耗尽 → 终态失败 + 教训入库。"""
        rt = self._make_runtime()
        task = type("T", (), {"description": "任务X",
                              "task_type": "execute",
                              "agent_type": "researcher"})()
        rt._task_retry_count["TASK-2"] = 2  # 已达上限
        meta = rt._replan_failed_task("TASK-2", task, "exit=1: boom")
        assert meta["decision"] != "retry_pending"
        assert meta["cause"] == "execution_error"
        assert meta["lesson"]["recorded"] is True

    def test_retryable_failure_skips_lesson(self):
        """可重试失败（执行错误）→ 仅重试，不写教训（等终态才归档）。"""
        rt = self._make_runtime()
        task = type("T", (), {"description": "运行 python 脚本",
                              "task_type": "execute",
                              "agent_type": "researcher"})()
        meta = rt._replan_failed_task("TASK-3", task,
                                      "exit=2: module not found")
        assert meta["decision"] == "retry_pending"
        assert "lesson" not in meta or meta["lesson"].get("recorded") is False
        assert rt._memory_hub.saved == []  # 无 lesson episode

    def test_uninitialized_hub_skips_gracefully(self):
        """未装配 memory hub → 静默跳过（裸实例兼容，不抛）。"""
        rt = self._make_runtime()
        del rt._memory_hub  # 模拟未装配 hub 的裸实例
        task = type("T", (), {"description": "分析数据",
                              "task_type": "analyze",
                              "agent_type": "researcher"})()
        meta = rt._replan_failed_task("TASK-4", task,
                                      "任务描述\"分析数据\"过于模糊")
        assert meta["decision"] != "retry_pending"
        assert meta.get("lesson", {}).get("recorded") is False


class TestMasterAgentSkillGrowthIntegration:
    """L5/L6 集成: grow_skills_from_episodes。"""

    def _make_agent(self, with_registry=True):
        from ocos.agent.master_agent import MasterAgent

        class FakeIdentity:
            def verify(self): return True
            def get_identity_id(self): return "id-1"

        class FakeGoalStack:
            def peek(self): return None

        class FakeIntent:
            def get_intent_description(self): return ""
            def get_intent_type(self): return "general"
            def extract(self, obs, entry=None): return str(obs)

        class FakeAttention:
            def current_focus(self): return None
            def needs_sleep(self): return False
            def reset(self): return None

        class FakeWM:
            def add(self, item): return None

        class FakeCapabilityManager:
            def list_capabilities(self): return []
            def has_capability(self, name): return False

        class FakeExecutionManager:
            def execute(self, d): return {"status": "ok"}

        agent = MasterAgent(
            agent_id="test", identity=FakeIdentity(),
            goal_stack=FakeGoalStack(), intent=FakeIntent(),
            attention=FakeAttention(), working_memory=FakeWM(),
            capability_manager=FakeCapabilityManager(),
            execution_manager=FakeExecutionManager(),
        )
        if with_registry:
            agent.set_skill_registry(_FakeRegistry())
        return agent

    def test_read_only_skills_auto_commit(self):
        agent = self._make_agent(with_registry=True)
        eps = [
            make_episode(f"E{i}", "检查系统负载", task_type="analyze")
            for i in range(3)
        ]
        stats = agent.grow_skills_from_episodes(eps)
        assert stats["proposals"] == 1
        assert stats["validated"] == 1
        assert stats["committed"] == 1
        assert stats["pending_approval"] == 0

    def test_write_skills_pending_approval(self):
        agent = self._make_agent(with_registry=True)
        eps = [
            make_episode(f"E{i}", "部署服务", task_type="execute")
            for i in range(4)
        ]
        stats = agent.grow_skills_from_episodes(eps)
        assert stats["proposals"] == 1
        assert stats["pending_approval"] == 1
        assert stats["committed"] == 0
        assert len(stats.get("pending", [])) == 1
        assert stats["pending"][0]["approval_required"] is True

    def test_no_registry_proposes_only(self):
        """无 registry → 只验不提交 (不静默落库)。"""
        agent = self._make_agent(with_registry=False)
        eps = [
            make_episode(f"E{i}", "检查端口", task_type="analyze")
            for i in range(3)
        ]
        stats = agent.grow_skills_from_episodes(eps)
        assert stats["proposals"] == 1
        assert stats["validated"] == 1
        assert stats["committed"] == 0  # 无 registry 不落库

    def test_fast_path_learning_includes_skill_growth(self):
        """dream 快通路产物含 skill_growth 段。"""
        from datetime import datetime, timezone
        from ocos.memory.episode.models import Episode
        from ocos.events.event_bus import EventBus
        from ocos.engines.learning_engine import LearningEngine
        from ocos.runtime.context_manager import WorkingMemory

        class FakeStore:
            def query_by_time(self, limit=200):
                now = datetime.now(timezone.utc)
                return [Episode.from_candidate(
                    experience_id="T-i", context={"agent": "researcher",
                                                  "task_type": "analyze"},
                    goal="检查系统状态", decision="completed",
                    action="execute", outcome={"success": True},
                    condition="", significance_score=0.7,
                    evaluation_trace={}, source="decision",
                    tags=["researcher"],
                ) for i in range(3)]

        agent = self._make_agent(with_registry=True)
        agent._episode_store = FakeStore()
        agent._learning_engine = LearningEngine(
            EventBus(), WorkingMemory())
        stats = agent._fast_path_learning()
        assert stats["examples"] >= 3
        sg = stats.get("skill_growth", {})
        assert sg.get("proposals", 0) >= 1

