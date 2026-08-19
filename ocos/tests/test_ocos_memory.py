"""OcosMemory 测试（S8-P2：M3 编排 / M4 巩固 / M5 遗忘 + M6/C3 统一）。

用临时 OCOS_MEMORY_DIR 隔离，不触碰真实记忆。
"""

from __future__ import annotations

import pytest

from ocos.opentale_bridge.bridge_model import OcosDecision
from ocos.opentale_bridge.ocos_memory import OcosMemory


@pytest.fixture
def memory(tmp_path, monkeypatch) -> OcosMemory:
    monkeypatch.setenv("OCOS_MEMORY_DIR", str(tmp_path))
    return OcosMemory()


def _decision(pid: str, focus: str = "investigation") -> OcosDecision:
    return OcosDecision(decision_id=pid, primary_focus=focus,
                        emotional_tone="suspense", pacing_directive="accelerate",
                        chapter_goal=f"第 1 章 {focus}")


def test_m6_record_and_prune(memory: OcosMemory) -> None:
    for i in range(memory.KEEP_DECISION + 5):
        memory.record_decision("批量", _decision(f"d{i}", "conflict"))
    n = len(memory._read_tail_jsonl(memory.decision_path, 10000))
    assert n == memory.KEEP_DECISION  # M5 遗忘生效


def test_m4_consolidate_high_score(memory: OcosMemory) -> None:
    memory.record_decision("高分书", _decision("d1", "investigation"))
    memory.record_feedback("高分书", {"project": "高分书", "book_review_score": 88.0, "chapters": 3})
    lt = memory.longterm_memory()
    assert lt["高分书"]["book_review_score"] == 88.0
    assert lt["高分书"]["focus"] == "investigation"  # 从决策历史补充


def test_m4_skip_low_score(memory: OcosMemory) -> None:
    memory.record_feedback("低分书", {"project": "低分书", "book_review_score": 60.0, "chapters": 2})
    assert "低分书" not in memory.longterm_memory()


def test_m3_recall_aggregates(memory: OcosMemory) -> None:
    memory.record_decision("聚合书", _decision("d1", "conflict"))
    memory.record_feedback("聚合书", {"project": "聚合书", "book_review_score": 85.0, "chapters": 5})
    ctx = memory.recall("聚合书")
    assert "conflict" in ctx      # 决策历史
    assert "85.0" in ctx          # 反馈
    assert "高分验证" in ctx      # 长期经验（M4 已巩固）


def test_feedback_path_creates_dir(memory: OcosMemory) -> None:
    memory.record_feedback("新书", {"project": "新书", "book_review_score": 90.0})
    assert memory.feedback_path("新书").exists()
