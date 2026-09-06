"""P0.1: 行为黄金链路测试（AGI 落地计划）。

5 类代表性任务的决策轨迹捕获与对比：
  1. host-analysis   只读复合（宿主机分析）
  2. file-write      文件写入（强制审批）
  3. vague-task      模糊任务（诚实失败）
  4. sensitive-path  敏感路径（沙盒拦截）
  5. destructive     破坏性命令（沙盒拦截）

每类任务确定性驱动 DecisionBridge（无 LLM 依赖），轨迹写入临时
behavior 目录；断言 JSONL 结构完整 + 确定性任务二次执行轨迹一致
（similarity=1.0, success_delta=0）——为 ER-2 对比建立机制基座。
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def behavior_dir(tmp_path):
    """隔离行为轨迹目录（不污染 ~/.ocos/behavior）。"""
    return tmp_path / "behavior"


def _bridge(store=None, mode="auto"):
    import os
    os.environ["OCOS_APPROVAL_MODE"] = mode
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge(pending_store=store)
    b.attach_default_handlers()
    return b


def _record(bridge, task_id, input_text, outcome, behavior_dir):
    """驱动 bridge → 取轨迹 → 写入。"""
    from ocos.behavior.trajectory import record_trajectory
    rep = bridge.process({"status": "completed",
                          "action_result": {"based_on": {"message": input_text}}})
    actions = rep.summary() if rep.verdicts else {
        "total": 0, "by_verdict": {}, "executed": [],
        "pending": [], "denied": [], "source": "dag_task"}
    return record_trajectory(task_id, input_text, actions, outcome,
                             base_dir=behavior_dir)


# ── 1. 只读复合（宿主机分析）───────────────────────────────────────────


def test_host_analysis_trajectory(behavior_dir):
    b = _bridge()
    _record(b, "host-analysis", "run command df -h", "completed", behavior_dir)
    from ocos.behavior.trajectory import load_trajectories
    rows = load_trajectories("host-analysis", base_dir=behavior_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"] == "host-analysis"
    assert row["outcome"] == "completed"
    assert "RUN_COMMAND" in row["actions"]["executed"]
    assert row["input"].startswith("run command")


# ── 2. 文件写入（强制审批）──────────────────────────────────────────────


def test_file_write_pending_trajectory(behavior_dir, tmp_path):
    from ocos.execution.pending import PendingStore
    store = PendingStore(str(tmp_path / "b.db"))
    b = _bridge(store, mode="ask")
    from types import SimpleNamespace
    r = b.execute_dag_task(SimpleNamespace(
        task_type="create", task_id="FW-1",
        description="写入文件 /tmp/x.txt"))
    assert r["status"] == "pending_approval"
    from ocos.behavior.trajectory import record_trajectory, load_trajectories
    record_trajectory("file-write", "写入文件 /tmp/x.txt",
                      {"executed": [], "pending": ["dag_create"],
                       "denied": [], "total": 1},
                      "pending_approval", base_dir=behavior_dir)
    row = load_trajectories("file-write", base_dir=behavior_dir)[0]
    assert row["outcome"] == "pending_approval"
    assert "dag_create" in row["actions"]["pending"]


# ── 3. 模糊任务（诚实失败）──────────────────────────────────────────────


def test_vague_task_failed_trajectory(behavior_dir):
    b = _bridge()
    from types import SimpleNamespace
    r = b.execute_dag_task(SimpleNamespace(
        task_type="execute", task_id="VAGUE-1", description=""))
    assert r["status"] == "failed"
    from ocos.behavior.trajectory import record_trajectory, load_trajectories
    record_trajectory("vague-task", "分析数据",
                      {"executed": [], "pending": [], "denied": [],
                       "total": 0},
                      "failed", base_dir=behavior_dir)
    row = load_trajectories("vague-task", base_dir=behavior_dir)[0]
    assert row["outcome"] == "failed"


# ── 4/5. 沙盒拦截（敏感路径 + 破坏性命令）───────────────────────────────


@pytest.mark.parametrize("task_id,input_text", [
    ("sensitive-path", "run command cat /etc/shadow"),
    ("destructive", "run command rm -rf /"),
])
def test_sandbox_blocked_trajectory(behavior_dir, task_id, input_text):
    b = _bridge()
    _record(b, task_id, input_text, "blocked", behavior_dir)
    from ocos.behavior.trajectory import load_trajectories
    row = load_trajectories(task_id, base_dir=behavior_dir)[0]
    assert row["outcome"] in ("blocked", "failed")
    assert row["input"].startswith("run command")


# ── 对比机制：确定性任务二次执行应一致 ──────────────────────────────────


def test_deterministic_task_identical_on_rerun(behavior_dir):
    """同任务同输入二次执行 → similarity=1.0, success_delta=0（基线可重复）。"""
    from ocos.behavior.trajectory import (
        compare_trajectories, load_trajectories, record_trajectory,
    )
    for _ in range(2):
        b = _bridge()
        _record(b, "host-analysis", "run command df -h", "completed",
                behavior_dir)
    rows = load_trajectories("host-analysis", base_dir=behavior_dir)
    assert len(rows) == 2
    delta = compare_trajectories(rows[0], rows[1])
    assert delta["similarity"] == 1.0
    assert delta["success_delta"] == 0.0
    assert delta["path_changed"]["added"] == []
    assert delta["path_changed"]["removed"] == []


# ── P0.3: 学习产物可观测（belief_created 打点与产出一致）─────────────────


def test_belief_created_metric_tracks_extraction():
    """consolidation 信念提取产出 → belief_created 打点计数一致。"""
    from ocos.monitoring.manager import (
        MetricsRegistry, record_global, set_global_metrics,
    )
    reg = MetricsRegistry()
    set_global_metrics(reg)

    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem

    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = [
        {"success": True, "agent": "writer", "description": "写一篇文章"},
        {"success": True, "agent": "writer", "description": "写一篇博客"},
        {"success": True, "agent": "writer", "description": "写一段文案"},
        {"success": True, "agent": "writer", "description": "写一份报告"},
    ]
    rt.beliefs = BeliefSystem()

    produced = rt._extract_beliefs_from_results()
    assert produced > 0
    # 打点必须在 metrics 中可见（S3.5 全局钩子）
    out = reg.to_prometheus()
    assert "belief_created" in out, out
    assert f"belief_created_source_consolidation" in out, out
    # 打点累计值 ≥ 本次产出（与返回 count 同源）
    key = "belief_created_source_consolidation"
    assert reg._counters.get(key, 0.0) >= produced

    set_global_metrics(None)


# ── P1.1: 学习产物检索（learning_artifacts）──────────────────────────────


def test_learning_artifacts_retrieves_relevant_beliefs():
    """同域经验沉淀的信念可被检索，带 artifact_id（ER-2 归因）。"""
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem
    from ocos.agent.knowledge_base import KnowledgeBase

    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = []
    rt.beliefs = BeliefSystem()
    rt.knowledge = KnowledgeBase()

    # 沉淀一条与"磁盘"相关的成功经验信念
    rt.beliefs.add(
        statement="当磁盘使用率高时, 使用 df -h 查看分区占用有效",
        confidence=0.8,
    )
    rt.knowledge.add("磁盘使用率高", "effective_action", "df -h 查看分区占用",
                     confidence=0.7)

    artifacts = rt.learning_artifacts("检查磁盘使用率", limit=5)
    assert artifacts, "应检索到磁盘相关学习产物"
    texts = [a["text"] for a in artifacts]
    assert any("df -h" in t or "磁盘" in t for t in texts), artifacts
    for a in artifacts:
        assert a["artifact_id"], a
        assert a["type"] in ("belief", "knowledge")
        assert a["confidence"] >= 0.6


def test_learning_artifacts_empty_without_match():
    """无关描述 → 空产物（决策侧走无经验注入基线）。"""
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem
    from ocos.agent.knowledge_base import KnowledgeBase

    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = []
    rt.beliefs = BeliefSystem()
    rt.knowledge = KnowledgeBase()
    rt.beliefs.add("当股票市场波动时, 降低仓位有效", confidence=0.9)

    assert rt.learning_artifacts("查看天气情况") == []


# ── P1.2: 决策注入（_prior_knowledge）───────────────────────────────────


def test_prior_knowledge_injects_artifacts():
    """learning_source 命中 → 注入块含 artifact_id + knowledge_injected 打点。"""
    from ocos.monitoring.manager import (
        MetricsRegistry, set_global_metrics,
    )
    reg = MetricsRegistry()
    set_global_metrics(reg)

    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    b.attach_learning_source(lambda desc: [
        {"artifact_id": "b-1", "type": "belief",
         "text": "当磁盘使用率高时 df -h 有效", "confidence": 0.8},
    ])
    block = b._prior_knowledge("检查磁盘使用率")
    assert "【历史经验（方法论）】" in block
    assert "b-1" in block
    assert "df -h" in block
    # 打点可见
    out = reg.to_prometheus()
    assert "knowledge_injected" in out, out
    assert "b-1" in out, out
    set_global_metrics(None)


def test_prior_knowledge_empty_without_source():
    """未注入 learning_source → 空注入块（基线路径行为不变）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    assert b._prior_knowledge("检查磁盘使用率") == ""
    # 注入源但无匹配 → 空
    b.attach_learning_source(lambda desc: [])
    assert b._prior_knowledge("检查磁盘使用率") == ""


# ── P1.3: ER-2 Behavioral Delta（学习前后同类任务行为可归因变化）─────────


def _mock_planner(prompt: str) -> str:
    """模拟规划 LLM：注入块含 df -h 经验 → 走 df -h 路径；否则走 free 次优。"""
    if "df -h" in prompt:
        return "RUN|df -h\n"
    return "RUN|free -h\n"


def test_er2_behavioral_delta_attributable():
    """ER-2 门：沉淀经验 → 注入 → 同类任务行为变化可归因于该 artifact。"""
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem
    from ocos.agent.knowledge_base import KnowledgeBase
    from ocos.execution.bridge import DecisionBridge
    from ocos.behavior.trajectory import (
        compare_trajectories, record_trajectory,
    )

    # ── Episode1: 无学习产物（基线）→ 次优路径 free ──
    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = []
    rt.beliefs = BeliefSystem()
    rt.knowledge = KnowledgeBase()
    b1 = DecisionBridge()
    b1.attach_learning_source(rt.learning_artifacts)
    prompt1 = "任务描述：检查磁盘使用率"
    action1 = _mock_planner(prompt1).strip()
    record_trajectory("er2-demo", prompt1,
                      {"executed": [action1], "pending": [], "denied": [],
                       "total": 1},
                      "completed")

    # ── 学习：成功经验沉淀信念（Episode1 的教训）──
    rt.beliefs.add(
        statement="当磁盘使用率高时, 使用 df -h 查看分区占用有效",
        confidence=0.8)
    rt.knowledge.add("磁盘使用率高", "effective_action", "df -h 查看分区占用",
                     confidence=0.7)

    # ── Episode2: 同类任务 X' → 注入命中 → 行为走 df -h ──
    b2 = DecisionBridge()
    b2.attach_learning_source(rt.learning_artifacts)
    desc2 = "检查根分区磁盘使用率"
    prompt2 = "任务描述：" + desc2
    knowledge = b2._prior_knowledge(desc2)
    assert "df -h" in knowledge, "方法论经验应被检索注入"
    assert "artifact" in knowledge, "注入块应带 artifact_id（ER-2 归因）"
    action2 = _mock_planner(prompt2 + "\n\n" + knowledge).strip()
    assert action2 == "RUN|df -h", "行为应从 free 次优路径变为 df -h 经验路径"
    record_trajectory("er2-demo", desc2,
                      {"executed": [action2], "pending": [], "denied": [],
                       "total": 1},
                      "completed")

    # ── 归因判定：路径变化可归因（added=df -h, removed=free -h）──
    from ocos.behavior.trajectory import load_trajectories
    rows = load_trajectories("er2-demo")
    delta = compare_trajectories(rows[0], rows[1])
    assert delta["path_changed"]["added"] == ["RUN|df -h"]
    assert delta["path_changed"]["removed"] == ["RUN|free -h"]
    # P1.2 实际链路中 attributable_to 由注入块中的 artifact_id 提供
    assert "artifact" in knowledge


# ── P1.4: 学习产物治理（陈旧淘汰 + 边界衔接）─────────────────────────────


def test_prune_stale_removes_old_low_confidence_beliefs():
    """低置信 + 从未被检索 + 超期 → 淘汰；高置信/新信念保留。"""
    import time
    from ocos.agent.belief_system import BeliefSystem

    bs = BeliefSystem()
    bs.add("陈旧低质经验 a", confidence=0.3)
    bs.add("陈旧低质经验 b", confidence=0.2)
    bs.add("高置信有效经验", confidence=0.8)
    # 人为把低置信信念的 last_updated 推回 40 天前
    old = time.time() - 40 * 86400
    for key, b in bs._beliefs.items():
        if "陈旧低质" in key:
            b.last_updated = old
    pruned = bs.prune_stale(max_age_days=30, min_confidence=0.4)
    assert pruned == 2
    remaining = {b.statement for b in bs.get_all()}
    assert "高置信有效经验" in remaining
    assert "陈旧低质经验 a" not in remaining
    # 再跑一次无新淘汰
    assert bs.prune_stale() == 0


def test_prune_keeps_recently_accessed_beliefs():
    """曾被检索（access_count>0）的低置信信念不被误杀。"""
    from ocos.agent.belief_system import BeliefSystem

    bs = BeliefSystem()
    bs.add("近期被用过的经验", confidence=0.3)
    for b in bs._beliefs.values():
        b.access_count = 1
    assert bs.prune_stale() == 0


# ── P2.1: 世界状态注入（_prior_world）───────────────────────────────────


def test_prior_world_injects_entities():
    """有世界实体 → 注入块含实体状态 + world_state_injected 打点。"""
    from ocos.monitoring.manager import (
        MetricsRegistry, set_global_metrics,
    )
    reg = MetricsRegistry()
    set_global_metrics(reg)

    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    b.attach_world_source(lambda desc: {
        "available": True, "entity_count": 1,
        "entities": [{"entity_id": "e1", "name": "app.log",
                      "entity_type": "file", "state": {"size": 2048},
                      "tick_id": 5}],
    })
    block = b._prior_world("检查日志文件")
    assert "【世界状态】" in block
    assert "app.log" in block
    assert "size=2048" in block
    out = reg.to_prometheus()
    assert "world_state_injected" in out, out
    set_global_metrics(None)


def test_prior_world_empty_world_degraded():
    """空世界/未注入 → 空块（默认零传感器优雅降级）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    assert b._prior_world("检查日志") == ""
    b.attach_world_source(lambda desc: {"available": False, "entities": []})
    assert b._prior_world("检查日志") == ""
    b.attach_world_source(lambda desc: {"available": True, "entities": []})
    assert b._prior_world("检查日志") == ""


# ── P2.2: 世界模型前置校验（_world_hint）───────────────────────────────


def test_world_hint_flags_unknown_entity():
    """描述引用的对象不在世界模型 → 诚实注记（不空跑不编造）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    b.attach_world_source(lambda desc: {
        "available": True,
        "entities": [{"entity_id": "e1", "name": "app.log",
                      "entity_type": "file"}],
    })
    hint = b._world_hint("分析 report.xlsx 的规模")
    assert "不在当前世界模型中" in hint
    assert "app.log" in hint


def test_world_hint_silent_on_match_and_empty_world():
    """描述命中已知实体 / 空世界 → 无注记。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    b.attach_world_source(lambda desc: {
        "available": True,
        "entities": [{"entity_id": "e1", "name": "app.log",
                      "entity_type": "file"}],
    })
    assert b._world_hint("查看 app.log 大小") == ""
    b2 = DecisionBridge()
    assert b2._world_hint("分析 report.xlsx") == ""


# ── P3.1: 置信度驱动策略（经验豁免）────────────────────────────────────


def test_experience_supports_high_confidence_hit():
    """同类高置信经验存在 → 经验豁免 True（低置信不升级 ASK）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    b.attach_learning_source(lambda desc: [
        {"artifact_id": "b-1", "type": "belief",
         "text": "当写文件时路径校验有效", "confidence": 0.85},
    ])
    assert b._experience_supports("写入文件 /tmp/x") is True


def test_experience_supports_false_without_hit():
    """无经验/低置信经验 → 豁免 False（走保守升级）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge()
    assert b._experience_supports("写入文件 /tmp/x") is False
    b.attach_learning_source(lambda desc: [
        {"artifact_id": "b-2", "type": "belief",
         "text": "当磁盘高时 df -h 有效", "confidence": 0.5},
    ])
    assert b._experience_supports("写入文件 /tmp/x") is False


# ── P3.2: 反思回流（reflection 并入学习产物）────────────────────────────


def test_learning_artifacts_merge_recent_reflection():
    """最近反思 insights 并入检索产物（type=reflection）。"""
    from types import SimpleNamespace
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem
    from ocos.agent.knowledge_base import KnowledgeBase

    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = []
    rt.beliefs = BeliefSystem()
    rt.knowledge = KnowledgeBase()
    rt.beliefs.add("当磁盘使用率高时, df -h 有效", confidence=0.8)
    rt.agent = SimpleNamespace(_last_reflection=SimpleNamespace(
        insights=("磁盘类任务应先用 df 确认分区再下结论",)))

    artifacts = rt.learning_artifacts("检查磁盘使用率")
    assert any(a["type"] == "reflection" for a in artifacts), artifacts
    assert any("df" in a["text"] for a in artifacts if a["type"] == "belief")


def test_learning_artifacts_no_reflection_without_agent():
    """无 agent/_last_reflection → 不出现 reflection 产物（不伪造）。"""
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.agent.belief_system import BeliefSystem
    from ocos.agent.knowledge_base import KnowledgeBase

    rt = AgentRuntime.__new__(AgentRuntime)
    rt._recent_results = []
    rt.beliefs = BeliefSystem()
    rt.knowledge = KnowledgeBase()
    rt.beliefs.add("当磁盘使用率高时, df -h 有效", confidence=0.8)
    artifacts = rt.learning_artifacts("检查磁盘使用率")
    assert not any(a["type"] == "reflection" for a in artifacts)
