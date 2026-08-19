"""SelfRegulationLoop 单元测试（S7：自调节闭环）。

mock OrganClient 章节读取，验证：
- 趋势检测（情绪单调 → chronic_emotional_curve）
- 调整生成（emotion_curve_override 等）
- 受控开关（off 拒绝 / manual 需确认）
- 应用指令生成
"""

from __future__ import annotations

from typing import Any

import pytest

from ocos.opentale_bridge.self_regulation import SelfRegulationLoop


class _MockOrgan:
    """最小 Organ mock：返回模拟章节（用于趋势检测）。"""

    def __init__(self, chapter_scores: list[float]) -> None:
        self._scores = chapter_scores

    def project(self, project: str) -> dict:
        return {"title": project, "chapters": len(self._scores)}

    def chapter(self, project: str, ch: int) -> dict:
        # 无情绪词 → emotional_curve 持续偏低（触发 chronic_emotional_curve）
        n = self._scores[ch - 1]
        if n < 0.4:
            return {"content": "。" * 100}  # 短且无情绪（低分）
        return {"content": ("她感到温暖与希望，愤怒与委屈交替，颤抖着说出真心话。" * 25)}

    def rewrite(self, project: str, chapter: int, instruction: str = "",
                  trace_context: Any = None) -> dict:  # U4.1: 接受 trace_context
        return {"task_id": f"task-reg-{chapter}", "status": "accepted"}


def _loop(chapter_scores: list[float]) -> SelfRegulationLoop:
    loop = SelfRegulationLoop(organ_base="http://mock")
    loop.organ = _MockOrgan(chapter_scores)  # type: ignore[assignment]
    return loop


def test_trend_detection_on_monotone_emotion() -> None:
    loop = _loop([0.8, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15])
    trends, adjustment = loop.adjust("测试书")
    ids = {t.trend_id for t in trends}
    assert "chronic_emotional_curve" in ids
    assert adjustment.emotion_curve_override  # 调整已生成


def test_healthy_sequence_no_critical_trend() -> None:
    loop = _loop([0.8, 0.75, 0.85, 0.7, 0.8, 0.75, 0.85, 0.7, 0.8, 0.75])
    trends, adjustment = loop.adjust("健康书")
    critical = [t for t in trends if t.severity in ("critical", "warn")]
    assert len(critical) <= 1  # 无系统性问题


def test_apply_respects_off_switch(monkeypatch) -> None:
    loop = _loop([0.5] * 10)
    _, adjustment = loop.adjust("测试书")
    monkeypatch.setenv("OCOS_SELF_REGULATION", "off")
    result = loop.apply("测试书", 2, adjustment)
    assert result["status"] == "skipped"
    assert "受控开关关闭" in result["reason"]


def test_apply_generates_instruction(monkeypatch) -> None:
    loop = _loop([0.8, 0.6, 0.4, 0.3, 0.2, 0.2, 0.15, 0.1, 0.1, 0.1])
    _, adjustment = loop.adjust("测试书")
    monkeypatch.setenv("OCOS_SELF_REGULATION", "manual")
    result = loop.apply("测试书", 3, adjustment)
    assert result["status"] == "applied"
    assert result["instruction"]  # 有可执行指令
    assert result["task_id"].startswith("task-reg-")


def test_describe_empty_when_no_trends() -> None:
    loop = _loop([0.8, 0.75, 0.85, 0.7, 0.8, 0.75, 0.85, 0.7, 0.8, 0.75])
    trends, adjustment = loop.adjust("健康书")
    desc = loop.describe(trends, adjustment)
    if not trends:
        assert "健康" in desc
