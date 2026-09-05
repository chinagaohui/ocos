"""FIX-20: LearningEngine 产出消费链路端到端测试。

链路: RuleBasedLearner.learn_fn → LearningModel.rules
      → persist_latest_rules (daemon dream 后调用, 原为死代码)
      → load_learning_rules (converse._recall_context 调用)
      → MemoryRecall.format_for_prompt 注入 (含无召回场景, 原提前 return 丢规则)
"""
from types import SimpleNamespace

from ocos.learning.persistence import (
    load_learning_rules,
    persist_latest_rules,
)
from ocos.learning.experience_learning import RuleBasedLearner
from ocos.engines.learning_engine import LearningEngine
from ocos.models.learning import LearningExample
from ocos.memory.hub import MemoryHub
from ocos.memory.recall import MemoryRecall


def _make_engine_with_rules(tasks: list[tuple[str, float, str]]):
    engine = LearningEngine(event_bus=None, working_memory=None)
    examples = [
        LearningExample(input_data={"task": t}, reward=r, feedback=f)
        for t, r, f in tasks
    ]
    model, _ = engine.learn(
        examples=examples,
        learn_fn=RuleBasedLearner.learn_fn,
    )
    return engine, model


def test_persist_and_load_roundtrip(tmp_path):
    db = str(tmp_path / "ocos.db")
    engine, _ = _make_engine_with_rules([
        ("分析任务: uname -a + df -h", 1.0, ""),
        ("分析任务: uname -a + df -h", 1.0, ""),
        ("分析任务: uname -a + df -h", 0.0, "command_not_found: bogus"),
    ])
    agent = SimpleNamespace(_learning_engine=engine)

    saved = persist_latest_rules(agent, db)
    assert saved == 1  # 同一指纹 3 样本聚合为 1 条规则

    rules = load_learning_rules(db)
    assert len(rules) == 1
    rule = rules[0]
    assert rule["success_count"] == 2
    assert rule["fail_count"] == 1
    assert 0.0 < rule["success_rate"] < 1.0
    assert "command_not_found" in rule["failure_causes"]


def test_persist_skips_when_no_engine(tmp_path):
    assert persist_latest_rules(SimpleNamespace(), str(tmp_path / "x.db")) == 0


def test_persist_skips_when_engine_empty(tmp_path):
    engine = LearningEngine(event_bus=None, working_memory=None)
    agent = SimpleNamespace(_learning_engine=engine)
    assert persist_latest_rules(agent, str(tmp_path / "x.db")) == 0


def test_persist_fails_gracefully_on_bad_db(tmp_path):
    engine, _ = _make_engine_with_rules([("任务A", 1.0, ""), ("任务A", 0.0, "x")])
    agent = SimpleNamespace(_learning_engine=engine)
    assert persist_latest_rules(agent, ":memory:") == 0


def test_format_prompt_keeps_rules_without_recalls(tmp_path):
    hub = MemoryHub(str(tmp_path / "mem.db"))
    hub.initialize()
    recall = MemoryRecall(memory_hub=hub)
    rules = [{
        "task_pattern": "分析: uname + df",
        "success_count": 3,
        "fail_count": 0,
        "success_rate": 1.0,
    }]
    out = recall.format_for_prompt(context="磁盘还剩多少", learning_rules=rules)
    assert "学习规则" in out
    assert "✅" in out
    assert "分析: uname + df" in out


def test_format_prompt_marks_failing_rules(tmp_path):
    hub = MemoryHub(str(tmp_path / "mem.db"))
    hub.initialize()
    recall = MemoryRecall(memory_hub=hub)
    rules = [{
        "task_pattern": "部署: 重启服务",
        "success_count": 1,
        "fail_count": 2,
        "success_rate": 0.3333,
    }]
    out = recall.format_for_prompt(context="重启服务", learning_rules=rules)
    assert "⚠️" in out


def test_format_prompt_excludes_low_sample_rules(tmp_path):
    hub = MemoryHub(str(tmp_path / "mem.db"))
    hub.initialize()
    recall = MemoryRecall(memory_hub=hub)
    rules = [{
        "task_pattern": "单样本任务",
        "success_count": 1,
        "fail_count": 0,
        "success_rate": 1.0,
    }]
    out = recall.format_for_prompt(context="单样本任务", learning_rules=rules)
    assert "学习规则" not in out
