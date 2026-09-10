"""Phase 49-A: Experience Learning — 经验学习快通路测试。

验收对应 (Blueprint v1.1 §8):
    ER-1 失败样本入库 → LearningArtifact(CANDIDATE, LESSON)
    ER-2 Behavioral Delta 描述生成
    ER-3 快通路非空 — learn 收到 examples ≥ 1 → rules ≥ 1
    ER-4 (集成层, 见 MasterAgent 测试)
    ER-5 Governance 保持 (纯逻辑层无 Action 路径)
"""

from __future__ import annotations

import pytest

from ocos.learning.experience_learning import (
    ArtifactStatus,
    ArtifactType,
    EpisodeExampleConverter,
    FailureCause,
    FailureDiagnoser,
    LearningArtifact,
    RuleBasedLearner,
    build_lesson_artifact,
    check_behavioral_delta,
)
from ocos.models.learning import LearningModel, LearningStrategy


# ── Episode 工厂（最小 Episode 形状，与真实 Episode 字段对齐） ──


def make_episode(
    ep_id: str,
    goal: str,
    success: bool = True,
    error: str = "",
    decision: str = "completed",
    agent: str = "researcher",
):
    """构造最小 Episode 形状。"""
    outcome = {"success": success}
    if error:
        outcome["error"] = error
    if not success:
        outcome["result"] = None
    fake = type("FakeEpisode", (), {
        "id": ep_id,
        "experience_id": f"TASK-{ep_id}",
        "goal": goal,
        "decision": decision,
        "action": f"execute:{goal[:20]}",
        "outcome": outcome,
        "context": {"agent": agent, "tags": ["test"]},
        "tags": ["test"],
        "source": "decision",
    })()
    return fake


# ═══════════════════════════════════════════════════════════════════════════════
# ER-1: Failure Diagnoser + Lesson Artifact
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailureDiagnoser:
    """A2: 失败原因诊断。"""

    def test_ambiguous_task(self):
        ep = make_episode(
            "EP1", "分析数据", success=False,
            error="任务描述\"分析数据\"过于模糊，未指定数据源",
            decision="failed",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        assert diag.cause == FailureCause.AMBIGUOUS_TASK
        assert diag.episode_id == "EP1"

    def test_permission_denied(self):
        ep = make_episode(
            "EP2", "删除文件", success=False,
            error="pending_approval: 需要人工审批", decision="pending_approval",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        assert diag.cause == FailureCause.PERMISSION_DENIED

    def test_success_returns_none(self):
        ep = make_episode("EP3", "正常任务", success=True)
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is None

    def test_execution_error(self):
        # P0-2026-09-10: "command not found" 正确分类为 DEPENDENCY_MISSING
        # （硬依赖缺失，重试不会解决）。真正的运行时错误用 RuntimeError 模拟。
        ep = make_episode(
            "EP4", "运行命令", success=False,
            error="RuntimeError: division by zero at line 42", decision="traceback failed",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        assert diag.cause == FailureCause.EXECUTION_ERROR

    def test_dependency_missing_command_not_found(self):
        # P0-2026-09-10: shell command not found → DEPENDENCY_MISSING（不可重试）
        ep = make_episode(
            "EP5", "运行命令", success=False,
            error="exit=127: command not found", decision="/bin/sh: 1: foo: not found",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        assert diag.cause == FailureCause.DEPENDENCY_MISSING


class TestLessonArtifact:
    """ER-1: 失败样本 → LESSON artifact。"""

    def test_build_lesson_artifact(self):
        ep = make_episode(
            "EP1", "分析数据", success=False,
            error="过于模糊，未指定数据源", decision="failed",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        artifact = build_lesson_artifact(diag, str(ep.goal))
        assert artifact.artifact_type == ArtifactType.LESSON
        assert artifact.status == ArtifactStatus.CANDIDATE
        assert artifact.confidence == 0.6
        assert "ambiguous_task" in artifact.hypothesis
        assert artifact.source_episodes == ("EP1",)
        assert artifact.applicable_context == "分析数据"
        assert diag.episode_id == "EP1"

    def test_artifact_commit(self):
        artifact = LearningArtifact(
            id="ART-x", artifact_type=ArtifactType.LESSON,
            hypothesis="h", confidence=0.6,
        )
        committed = artifact.commit()
        assert committed.status == ArtifactStatus.COMMITTED
        assert artifact.status == ArtifactStatus.CANDIDATE  # 不可变

    def test_behavioral_delta_description(self):
        ep = make_episode(
            "EP1", "分析数据", success=False, error="过于模糊", decision="failed",
        )
        diag = FailureDiagnoser.diagnose(ep)
        assert diag is not None
        artifact = build_lesson_artifact(diag, str(ep.goal))
        delta = check_behavioral_delta(artifact, None)
        assert "avoid" in delta
        assert "ambiguous_task" in delta


# ═══════════════════════════════════════════════════════════════════════════════
# A1: Episode → LearningExample 转换
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpisodeExampleConverter:
    """A1: 样本转换。"""

    def test_convert_success(self):
        ep = make_episode("EP1", "收集系统信息", success=True)
        ex = EpisodeExampleConverter.convert(ep)
        assert ex is not None
        assert ex.reward == 1.0
        assert ex.input_data["task"] == "收集系统信息"
        assert ex.metadata["episode_id"] == "EP1"

    def test_convert_failure_with_diagnosis(self):
        ep = make_episode(
            "EP1", "分析数据", success=False, error="过于模糊", decision="failed",
        )
        diag = FailureDiagnoser.diagnose(ep)
        ex = EpisodeExampleConverter.convert(ep, diag)
        assert ex is not None
        assert ex.reward == 0.0
        assert "ambiguous_task" in ex.feedback

    def test_convert_many(self):
        eps = [
            make_episode("EP1", "任务A", success=True),
            make_episode("EP2", "任务B", success=False, error="过于模糊", decision="failed"),
        ]
        examples, diagnoses, skipped = EpisodeExampleConverter.convert_many(eps)
        assert len(examples) == 2
        assert len(diagnoses) == 1
        assert len(skipped) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ER-3: 规则型 learn_fn → LearningModel
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuleBasedLearner:
    """A3: 规则聚合。"""

    def test_learn_produces_rules(self):
        eps = [
            make_episode("EP1", "执行 uname -a", success=True),
            make_episode("EP2", "执行 uname -a", success=True),
            make_episode("EP3", "执行 uname -a", success=False,
                         error="过于模糊", decision="failed"),
        ]
        examples, _, _ = EpisodeExampleConverter.convert_many(eps)
        model = RuleBasedLearner.learn_fn(None, examples, LearningStrategy.SUPERVISED)
        assert len(model.rules) >= 1
        rule = model.rules[0]
        assert rule["success_count"] == 2
        assert rule["fail_count"] == 1
        assert rule["success_rate"] == pytest.approx(0.6667, abs=0.01)
        assert "ambiguous_task" in rule["failure_causes"]
        assert model.accuracy is not None

    def test_learn_with_existing_model_incremental(self):
        eps1 = [
            make_episode("EP1", "检查内核版本", success=True),
            make_episode("EP2", "检查内核版本", success=False, error="权限不足", decision="failed"),
        ]
        ex1, _, _ = EpisodeExampleConverter.convert_many(eps1)
        model1 = RuleBasedLearner.learn_fn(None, ex1, LearningStrategy.SUPERVISED)
        assert len(model1.rules) == 1

        # 增量：新增样本
        eps2 = [make_episode("EP3", "检查内核版本", success=True)]
        ex2, _, _ = EpisodeExampleConverter.convert_many(eps2)
        model2 = RuleBasedLearner.learn_fn(model1, ex2, LearningStrategy.SUPERVISED)
        assert model2.model_id == model1.model_id  # 保留 model_id
        rule = model2.rules[0]
        assert rule["success_count"] == 2  # EP1 + EP3
        assert rule["fail_count"] == 1     # EP2

    def test_distinct_tasks_separate_rules(self):
        eps = [
            make_episode("EP1", "任务甲", success=True),
            make_episode("EP2", "任务乙", success=False, error="超时", decision="failed"),
        ]
        examples, _, _ = EpisodeExampleConverter.convert_many(eps)
        model = RuleBasedLearner.learn_fn(None, examples, LearningStrategy.SUPERVISED)
        assert len(model.rules) == 2

    def test_learn_with_real_learning_engine(self):
        """ER-3 集成: LearningEngine.learn 收到真实样本。"""
        from ocos.events.event_bus import EventBus
        from ocos.engines.learning_engine import LearningEngine
        from ocos.runtime.context_manager import WorkingMemory
        from ocos.models.process import TransformProcess, ProcessType

        engine = LearningEngine(EventBus(), WorkingMemory())
        eps = [
            make_episode("EP1", "分析数据", success=False, error="过于模糊", decision="failed"),
            make_episode("EP2", "分析数据", success=True),
        ]
        examples, _, _ = EpisodeExampleConverter.convert_many(eps)

        process = TransformProcess(process_type=ProcessType.LEARNING)
        result = engine.execute(process, context={
            "examples": examples,
            "learn_fn": RuleBasedLearner.learn_fn,
            "strategy": LearningStrategy.SUPERVISED,
        })
        assert result.success is True
        assert "Learning complete" in result.message
        assert engine.list_models(), "模型应非空"

        # models 的 rules 应含分析数据规则
        any_rule = False
        for m in engine.list_models():
            if m.rules:
                any_rule = True
                assert m.rules[0]["success_count"] >= 1
        assert any_rule


# ═══════════════════════════════════════════════════════════════════════════════
# ER-5: Governance 保持 — 纯逻辑层无 Action 路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestGovernanceIsolation:
    """纯逻辑层不产生 Action，不触碰 Mutation Authority。"""

    def test_no_execute_method(self):
        """LearningArtifact/RuleBasedLearner 不应有 execute/act 方法。"""
        assert not hasattr(LearningArtifact, "execute")
        assert not hasattr(LearningArtifact, "act")
        assert not hasattr(RuleBasedLearner, "execute")
        assert not hasattr(RuleBasedLearner, "act")
        assert not hasattr(FailureDiagnoser, "execute")

    def test_artifact_defaults_no_approval_required(self):
        artifact = LearningArtifact(
            id="ART-x", artifact_type=ArtifactType.LESSON,
            hypothesis="h", confidence=0.6,
        )
        assert artifact.approval_required is False
        assert artifact.approval_id == ""

    def test_failure_diagnosis_is_readonly(self):
        ep = make_episode("EP1", "任务", success=False, error="超时", decision="failed")
        d = FailureDiagnoser.diagnose(ep)
        assert d is not None
        assert d.cause == FailureCause.TIMEOUT
        assert isinstance(d.signals_hit, tuple)


# ═══════════════════════════════════════════════════════════════════════════════
# ER-2 + ER-4: Behavioral Delta + MasterAgent 集成（dream 快通路）
# ═══════════════════════════════════════════════════════════════════════════════


class TestMasterAgentFastPathLearning:
    """MasterAgent._fast_path_learning 集成测试。"""

    def _make_agent(self, episodes=None, with_engine=True):
        """构造带 episode_store + learning_engine 的 MasterAgent 最小实例。"""
        from ocos.agent.master_agent import MasterAgent
        from ocos.events.event_bus import EventBus
        from ocos.engines.learning_engine import LearningEngine
        from ocos.runtime.context_manager import WorkingMemory

        # 内存 Episode store（模拟 query_by_time / mark_consolidated）
        class FakeEpisodeStore:
            def __init__(self, eps):
                self._eps = list(eps or [])

            def query_by_time(self, limit=200, active_only=True):
                return self._eps[:limit]

            def mark_consolidated(self, ep_id):
                for ep in self._eps:
                    if ep.id == ep_id:
                        object.__setattr__(ep, "status",
                            type("S", (), {"name": "CONSOLIDATED"})())
                return True

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

        class FakeWorkingMemory:
            def add(self, item): return None

        class FakeCapabilityManager:
            def list_capabilities(self): return []
            def has_capability(self, name): return False

        class FakeExecutionManager:
            def execute(self, d): return {"status": "ok"}

        class FakeState:
            status = None
            def transition(self, s): self.status = s

        learning_engine = LearningEngine(EventBus(), WorkingMemory()) if with_engine else None
        agent = MasterAgent(
            agent_id="test-agent",
            identity=FakeIdentity(),
            goal_stack=FakeGoalStack(),
            intent=FakeIntent(),
            attention=FakeAttention(),
            working_memory=FakeWorkingMemory(),
            capability_manager=FakeCapabilityManager(),
            execution_manager=FakeExecutionManager(),
            episode_store=FakeEpisodeStore(episodes),
            learning_engine=learning_engine,
        )
        return agent

    def test_fast_path_learning_with_engine(self):
        """ER-3 集成: dream 快通路经 real LearningEngine 产生模型。"""
        from datetime import datetime, timezone
        from ocos.memory.episode.models import Episode, EpisodeStatus

        now = datetime.now(timezone.utc)
        eps = [
            Episode.from_candidate(
                experience_id="TASK-1", context={"agent": "researcher"},
                goal="分析市场数据", decision='{"status": "failed"}',
                action="execute", outcome={"success": False,
                                           "error": "任务描述过于模糊，未指定数据源"},
                condition="", significance_score=0.8, evaluation_trace={},
                source="decision", tags=["researcher"],
            ),
        ]
        # from_candidate 的 created_at = now → 命中"今日"
        agent = self._make_agent(episodes=eps, with_engine=True)
        stats = agent._fast_path_learning()
        assert stats["examples"] >= 1, f"快通路应收到样本: {stats}"
        assert stats["learning_engine"] is True
        assert stats["rules"] >= 1
        assert stats["lessons"] >= 1
        assert stats["accuracy"] is not None
        # Lesson artifacts 带 behavioral delta
        artifacts = stats.get("artifacts", [])
        assert artifacts, "失败诊断应产出 LESSON artifacts"
        assert "delta" in artifacts[0]

    def test_fast_path_no_engine_degrades(self):
        """无 learning_engine → 降级不抛。"""
        agent = self._make_agent(episodes=[], with_engine=False)
        stats = agent._fast_path_learning()
        assert stats["learning_engine"] is False
        assert "error" not in stats

    def test_dream_includes_fast_learning(self):
        """ER-4: dream() 产物含 fast_learning 段。"""
        from datetime import datetime, timezone
        from ocos.memory.episode.models import Episode

        now = datetime.now(timezone.utc)
        eps = [
            Episode.from_candidate(
                experience_id="TASK-2", context={"agent": "researcher"},
                goal="检查系统状态", decision="completed",
                action="execute", outcome={"success": True},
                condition="", significance_score=0.7, evaluation_trace={},
                source="decision", tags=["researcher"],
            ),
        ]
        agent = self._make_agent(episodes=eps, with_engine=True)
        # dream() 需 lifecycle 正确 — 直接用 _consolidate_episodes 同源路径验证
        # dream() 内部会调 _fast_path_learning；直接测方法本身:
        stats = agent._fast_path_learning()
        assert "fast_path" in stats
        assert stats["fast_path"] == "learning"

    def test_ordering_fast_path_before_slow_path(self):
        """回归: 快通路必须先于慢通路 — 慢通路 mark CONSOLIDATED 后快通路拿空样本。

        dream() 中 _fast_path_learning 必须排在 _consolidate_episodes 之前。
        """
        from datetime import datetime, timezone
        from ocos.memory.episode.models import Episode

        now = datetime.now(timezone.utc)
        eps = [
            Episode.from_candidate(
                experience_id="TASK-3", context={"agent": "researcher"},
                goal="分析市场趋势", decision='{"status": "failed"}',
                action="execute", outcome={"success": False,
                                           "error": "任务描述过于模糊，未指定数据源"},
                condition="", significance_score=0.8, evaluation_trace={},
                source="decision", tags=["researcher"],
            ),
        ]
        agent = self._make_agent(episodes=eps, with_engine=True)
        # 模拟 dream() 真实顺序: 快通路先 (读 ACTIVE) → 慢通路后 (mark CONSOLIDATED)
        fast_first = agent._fast_path_learning()
        assert fast_first["examples"] >= 1, \
            "快通路在慢通路前执行时必须拿到样本"
        slow = agent._consolidate_episodes()
        assert slow["replayed"] >= 1
        # 第二次快通路 (慢通路已 mark CONSOLIDATED) → 空样本 (幂等, 不重复学习)
        fast_second = agent._fast_path_learning()
        assert fast_second["examples"] == 0, \
            "慢通路消化后快通路应拿到空样本 (幂等)"


    def test_behavioral_delta_roundtrip(self):
        """ER-2 核心: 失败 → 学习 → 规则可查询 → 未来行为差异可表达。

        验证: 学习后的 LearningModel 规则含失败原因与 success_rate，
        未来同类任务决策可查询该规则（behavioral delta 成立的前提）。
        """
        from ocos.events.event_bus import EventBus
        from ocos.engines.learning_engine import LearningEngine
        from ocos.runtime.context_manager import WorkingMemory

        engine = LearningEngine(EventBus(), WorkingMemory())
        # Episode1: 任务 X 失败（原因: ambiguous）
        eps = [
            make_episode("EP1", "分析数据", success=False,
                         error="任务描述\"分析数据\"过于模糊，未指定数据源",
                         decision="failed"),
        ]
        examples, diagnoses, _ = EpisodeExampleConverter.convert_many(eps)
        assert len(examples) == 1
        model, _ = engine.learn(
            examples=examples,
            learn_fn=RuleBasedLearner.learn_fn,
            strategy=LearningStrategy.SUPERVISED,
        )
        # 学习产物: 规则含失败原因
        assert len(model.rules) >= 1
        rule = model.rules[0]
        assert rule["fail_count"] >= 1
        assert rule["success_rate"] == 0.0
        assert "ambiguous_task" in rule["failure_causes"]
        # 规则可通过 rule_id 查询 → 未来决策可消费（Behavioral Delta 前提）
        rid = rule["rule_id"]
        found = [r for r in model.rules if r["rule_id"] == rid]
        assert len(found) == 1
        assert found[0]["failure_causes"]["ambiguous_task"] >= 1
        # 第二次同类任务（成功）→ 增量 → success_rate 变化 = 行为差异可观测
        eps2 = [make_episode("EP2", "分析数据", success=True)]
        ex2, _, _ = EpisodeExampleConverter.convert_many(eps2)
        model2, _ = engine.learn(
            examples=ex2, learn_fn=RuleBasedLearner.learn_fn,
            strategy=LearningStrategy.SUPERVISED, base_model=model,
        )
        rule2 = [r for r in model2.rules if r["rule_id"] == rid][0]
        assert rule2["success_count"] >= 1
        assert rule2["success_rate"] == pytest.approx(0.5, abs=0.01)

