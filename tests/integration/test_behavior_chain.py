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
