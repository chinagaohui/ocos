"""S2.3: Experience Boundary 严格模式回归（白皮书 P2，评审版 R5-5）。

- 默认（OCOS_EXPERIENCE_BOUNDARY_STRICT 未设）：仅记录违规，行为不变
- 严格模式（=true）：Self 污染候选置 REJECTED → SignificanceGate FAIL
"""

from __future__ import annotations

import pytest

from ocos.memory.experience.builder import ExperienceBuilder
from ocos.memory.experience.models import ExperienceStatus
from ocos.memory.experience.models import TraceBundle
from ocos.memory.significance.evaluator import SignificanceEvaluator


def _bundle() -> TraceBundle:
    return TraceBundle(
        observation={"input": "用户让我总结报告"},
        reasoning_trace_id="r-1",
        decision_trace_id="d-1",
        action_result={"output": "已总结"},
        outcome={"result": "success"},
    )


def _builder() -> ExperienceBuilder:
    return ExperienceBuilder()


class TestBoundaryStrict:
    def _self_polluted_bundle(self) -> TraceBundle:
        return TraceBundle(
            observation={"input": "用户让我总结报告",
                         "identity": "我是有意识的主体"},
            reasoning_trace_id="r-1",
            decision_trace_id="d-1",
            action_result={"output": "已总结"},
            outcome={"result": "success"},
        )

    def test_explicit_false_records_only(self, monkeypatch):
        """OCOS_EXPERIENCE_BOUNDARY_STRICT=false（S3.13 后的回退开关）。"""
        monkeypatch.setenv("OCOS_EXPERIENCE_BOUNDARY_STRICT", "false")
        builder = _builder()
        candidate = builder.build(trace_bundle=self._self_polluted_bundle(),
                                  source="decision", context={})
        assert candidate.status == ExperienceStatus.COMPLETE
        assert "self_violations" in (candidate.rejection_reason or "")

    def test_default_mode_strict(self, monkeypatch):
        """S3.13: 未设置环境变量时默认严格（阻断）。"""
        monkeypatch.delenv("OCOS_EXPERIENCE_BOUNDARY_STRICT", raising=False)
        builder = _builder()
        candidate = builder.build(trace_bundle=self._self_polluted_bundle(),
                                  source="decision", context={})
        assert candidate.status == ExperienceStatus.REJECTED

    def test_strict_mode_rejects(self, monkeypatch):
        monkeypatch.setenv("OCOS_EXPERIENCE_BOUNDARY_STRICT", "true")
        builder = _builder()
        candidate = builder.build(trace_bundle=self._self_polluted_bundle(),
                                  source="decision", context={})
        assert candidate.status == ExperienceStatus.REJECTED
        gate = SignificanceEvaluator()
        decision = gate.evaluate(candidate)
        assert decision.verdict.value in ("fail", "FAIL")

    def test_clean_candidate_unaffected_in_strict_mode(self, monkeypatch):
        monkeypatch.setenv("OCOS_EXPERIENCE_BOUNDARY_STRICT", "true")
        builder = _builder()
        candidate = builder.build(trace_bundle=_bundle(),
                                  source="decision", context={})
        assert candidate.status == ExperienceStatus.COMPLETE
