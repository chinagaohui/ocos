"""Phase 25.3 — Gate Tests: SelfModelBuilder。

验证:
  25.3-B01: 空 BeliefStore → 最小 SelfModel
  25.3-B02: 有 self Belief → CapabilityState 匹配
  25.3-B03: 预设局限始终包含
  25.3-B04: statement 通过 StatementValidator
  25.3-B05: Builder 不写入 BeliefStore
  25.3-B06: build_and_approve → governor_approval_id 已填充
  25.3-B07: 审批拒绝 → None
"""

import pytest
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

from ocos.memory.belief.models import Belief, BeliefStatus
from ocos.memory.belief.store import BeliefStore
from ocos.self.identity_boundary import IdentityBoundary
from ocos.self.builder import SelfModelBuilder
from ocos.self.models import CapabilityName, PRESET_LIMITATIONS


def _now():
    return datetime.now(timezone.utc)


def _make_boundary():
    return IdentityBoundary.create_default()


def _make_empty_store():
    """空 BeliefStore (无 self domain 数据)。"""
    store = MagicMock(spec=BeliefStore)
    store.query_by_domain.return_value = []
    return store


def _make_store_with_beliefs(beliefs_data: list[dict]):
    """创建 Mock BeliefStore + Belief 列表。"""
    store = MagicMock(spec=BeliefStore)
    built_beliefs = []
    for bd in beliefs_data:
        belief = Belief.create(
            statement=bd["statement"],
            source_knowledge_ids=bd.get("source_knowledge_ids", []),
            evidence_ids=bd.get(
                "evidence_ids",
                [f"ev-{bd['statement'][:8]}"] if bd.get("confidence", 0.7) > 0 else [],
            ),
            confidence=bd.get("confidence", 0.7),
            uncertainty=bd.get("uncertainty", 0.2),
            scope=bd.get("scope", {"domain": "self"}),
        )
        built_beliefs.append(belief)
    store.query_by_domain.return_value = built_beliefs
    return store, built_beliefs


# ── 25.3-B01: 空 BeliefStore → 最小 SelfModel ───────────────────────────

def test_empty_store_produces_minimal_selfmodel():
    store = _make_empty_store()
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    model = builder.build()
    assert model is not None
    assert model.version == 1
    # 所有能力处于 uncertain 状态
    assert all(cs.status == "uncertain" for cs in model.capability_states)
    # 预设局限存在
    assert model.has_preset_limitations()


# ── 25.3-B02: 有 self Belief → CapabilityState 匹配 ─────────────────────

def test_beliefs_map_to_capabilities():
    store, _beliefs = _make_store_with_beliefs([
        {
            "statement": "当前系统的文字理解能力对中文文本处理准确",
            "confidence": 0.85,
        },
        {
            "statement": "当前系统的模式识别能发现数据规律",
            "confidence": 0.75,
        },
    ])
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    model = builder.build()
    # 文字理解应该激活
    text_understanding = next(
        cs for cs in model.capability_states
        if cs.name == CapabilityName.TEXT_UNDERSTANDING
    )
    assert text_understanding.status == "active"
    assert text_understanding.confidence_score > 0.7

    # 模式识别应该激活
    pattern = next(
        cs for cs in model.capability_states
        if cs.name == CapabilityName.PATTERN_RECOGNITION
    )
    assert pattern.status == "active"


# ── 25.3-B03: 预设局限始终包含 ──────────────────────────────────────────

def test_preset_limitations_always_included():
    store = _make_empty_store()
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    model = builder.build()
    assert model.has_preset_limitations()
    assert len(model.limitations) >= len(PRESET_LIMITATIONS)


# ── 25.3-B04: statement 通过 StatementValidator ──────────────────────────

def test_generated_statement_is_valid():
    store = _make_empty_store()
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    model = builder.build()
    # statement 不应包含禁止词汇（由 StatementValidator 在 build 中检查）
    # 如果包含，build 会抛出 ValueError
    assert model.statement
    assert len(model.statement) <= 200


# ── 25.3-B05: Builder 不写入 BeliefStore ────────────────────────────────

def test_builder_only_reads():
    store = _make_empty_store()
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    builder.build()

    # 确认只有 query_by_domain 被调用，无写入方法
    store.query_by_domain.assert_called()
    # add / update / weaken / archive 不应被调用
    for forbidden in ("add", "update", "weaken", "archive", "insert"):
        method = getattr(store, forbidden, None)
        if method:
            method.assert_not_called()


# ── 25.3-B06: build_and_approve → approval_id ───────────────────────────

def test_build_and_approve_success():
    store = _make_empty_store()
    boundary = IdentityBoundary.create_default()

    governor = MagicMock()
    # 模拟审批成功: (success, EvolutionRecord, message)
    mock_record = MagicMock()
    mock_record.new_version = 1
    mock_record.record_id = "REC-TEST-001"
    governor.approve.return_value = (True, mock_record, "approved")

    builder = SelfModelBuilder(store, boundary)
    model = builder.build_and_approve(governor)

    # 首次构建 + approve 应该成功（首次不受频率限制）
    assert model is not None
    assert model.governor_approval_id
    assert model.version >= 1


# ── 25.3-B07: 审批拒绝 → None ────────────────────────────────────────────

def test_build_and_approve_denied():
    store, _beliefs = _make_store_with_beliefs([
        {
            "statement": "当前系统拥有自我意识和一个独立的身份",
            "confidence": 0.9,
        },
    ])
    boundary = _make_boundary()
    governor = MagicMock()
    governor.approve.return_value = (False, None, "denied")  # 拒绝

    builder = SelfModelBuilder(store, boundary)
    model = builder.build_and_approve(governor)
    assert model is None


# ── B08: limitation from belief ──────────────────────────────────────────

def test_limitations_extracted_from_beliefs():
    store, _beliefs = _make_store_with_beliefs([
        {
            "statement": "当前系统不能直接操作物理设备",
            "confidence": 0.9,
        },
        {
            "statement": "当前系统无法处理实时音视频流",
            "confidence": 0.8,
        },
    ])
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    model = builder.build()
    # 5 preset + 2 extracted = at least 7
    assert len(model.limitations) >= 7

    descs = {l.description for l in model.limitations}
    assert "当前系统不能直接操作物理设备" in descs
    assert "当前系统无法处理实时音视频流" in descs


# ── B09: version increments ──────────────────────────────────────────────

def test_version_increments():
    store = _make_empty_store()
    boundary = _make_boundary()
    builder = SelfModelBuilder(store, boundary)

    v1 = builder.build()
    assert v1.version == 1

    # v2 builds from v1
    v2 = builder.build(previous=v1)
    assert v2.version == 2
    assert v2.previous_version_id == v1.model_id
