"""OCOS self_models 自模型不变式测试。

Phase 25.3 SelfModel 约束：
    - 全部 frozen=True
    - capability_domains 闭合，不可运行时扩展
    - PRESET_LIMITATIONS 不可被移除
    - maturity dimensions 必须包含所有 key
    - confidence_score ∈ [0.0, 1.0]
"""

import pytest

from ocos.self.models import (
    CapabilityDomain,
    CapabilityName,
    CAPABILITY_NAME_TO_DOMAIN,
    CapabilityState,
    Limitation,
    PRESET_LIMITATIONS,
    MaturitySnapshot,
    MATURITY_DIMENSIONS,
    SelfModel,
)


class TestCapabilityDomain:
    """能力域闭合集合。"""

    def test_three_domains(self):
        domains = {d.value for d in CapabilityDomain}
        assert domains == {"cognition", "memory", "self"}

    def test_name_to_domain_mapping_complete(self):
        """所有 CapabilityName 必须映射到对应域。"""
        for name in CapabilityName:
            assert name.domain in CapabilityDomain


class TestCapabilityName:
    """能力名闭合集合 + 域归属。"""

    def test_eight_capabilities(self):
        names = {n.value for n in CapabilityName}
        expected = {
            "text-understanding", "pattern-recognition", "simulation",
            "experience-recall", "knowledge-retrieval", "belief-accuracy",
            "boundary-awareness", "limitation-awareness",
        }
        assert names == expected

    def test_cognition_capabilities(self):
        cognition = {n for n in CapabilityName if n.domain == CapabilityDomain.COGNITION}
        assert len(cognition) == 3

    def test_memory_capabilities(self):
        memory = {n for n in CapabilityName if n.domain == CapabilityDomain.MEMORY}
        assert len(memory) == 3

    def test_self_capabilities(self):
        self_caps = {n for n in CapabilityName if n.domain == CapabilityDomain.SELF}
        assert len(self_caps) == 2


class TestCapabilityState:
    """CapabilityState 不变式。"""

    def test_valid_confidence_range(self):
        cs = CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=0.8,
            belief_ids=("BLF-001",),
            evidence_summary="high accuracy on NLP tasks",
            last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        assert cs.confidence_score == 0.8
        assert cs.domain == CapabilityDomain.COGNITION

    def test_confidence_zero_allowed(self):
        cs = CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=0.0,
            belief_ids=(),
            evidence_summary="no evidence yet",
            last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        assert cs.confidence_score == 0.0

    def test_confidence_one_allowed(self):
        cs = CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=1.0,
            belief_ids=(),
            evidence_summary="perfect",
            last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        assert cs.confidence_score == 1.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence_score"):
            CapabilityState(
                name=CapabilityName.TEXT_UNDERSTANDING,
                confidence_score=-0.1,
                belief_ids=(),
                evidence_summary="",
                last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

    def test_confidence_over_one_rejected(self):
        with pytest.raises(ValueError, match="confidence_score"):
            CapabilityState(
                name=CapabilityName.TEXT_UNDERSTANDING,
                confidence_score=1.1,
                belief_ids=(),
                evidence_summary="",
                last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

    def test_valid_status(self):
        for status in ("active", "uncertain", "deprecated"):
            cs = CapabilityState(
                name=CapabilityName.PATTERN_RECOGNITION,
                confidence_score=0.5,
                belief_ids=(),
                evidence_summary="test",
                last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                status=status,
            )
            assert cs.status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            CapabilityState(
                name=CapabilityName.TEXT_UNDERSTANDING,
                confidence_score=0.5,
                belief_ids=(),
                evidence_summary="test",
                last_updated=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                status="broken",
            )


class TestLimitation:
    """Limitation 不变式。"""

    def test_valid_limitation(self):
        dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        lim = Limitation(
            description="cannot access physical world",
            category="scope",
            severity="scope",
            evidence_belief_ids=(),
            acknowledged_at=dt,
        )
        assert lim.category == "scope"
        assert lim.severity == "scope"

    def test_valid_categories(self):
        for cat in ("architectural", "capability", "scope", "temporal"):
            lim = Limitation(
                description="test", category=cat, severity="hard",
                evidence_belief_ids=(),
                acknowledged_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            assert lim.category == cat

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError, match="category"):
            Limitation(
                description="test", category="invalid", severity="hard",
                evidence_belief_ids=(),
                acknowledged_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

    def test_valid_severities(self):
        for sev in ("hard", "soft", "scope"):
            lim = Limitation(
                description="test", category="architectural", severity=sev,
                evidence_belief_ids=(),
                acknowledged_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            assert lim.severity == sev

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            Limitation(
                description="test", category="capability", severity="extreme",
                evidence_belief_ids=(),
                acknowledged_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )


class TestPresetLimitations:
    """预设局限不可变且完整。"""

    def test_five_preset_limitations(self):
        assert len(PRESET_LIMITATIONS) == 5

    def test_all_preset_are_architectural_or_scope(self):
        for lim in PRESET_LIMITATIONS:
            assert lim.category in ("architectural", "scope")
            assert lim.severity in ("hard", "scope")

    def test_preset_descriptions_known(self):
        descs = {lim.description for lim in PRESET_LIMITATIONS}
        assert "不能创建新目标" in descs
        assert "不能修改 IdentityBoundary" in descs
        assert "不能写入 Memory" in descs
        assert "不能访问物理世界" in descs
        assert "不能自行获取网络权限" in descs

    def test_preset_have_no_evidence(self):
        for lim in PRESET_LIMITATIONS:
            assert lim.evidence_belief_ids == ()


class TestMaturitySnapshot:
    """成熟度快照不变式。"""

    def test_all_dimensions_present(self):
        dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        snap = MaturitySnapshot(
            current_phase="47",
            phase_history=("22", "25", "39", "47"),
            dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
            capability_count=8,
            limitation_count=5,
            snapshot_at=dt,
        )
        for dim in MATURITY_DIMENSIONS:
            assert dim in snap.dimensions

    def test_missing_dimension_rejected(self):
        dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        with pytest.raises(ValueError, match="Missing maturity dimension"):
            MaturitySnapshot(
                current_phase="47",
                phase_history=(),
                dimensions={"theory": 0.5},  # 缺少其他维度
                capability_count=0,
                limitation_count=0,
                snapshot_at=dt,
            )

    def test_dimension_out_of_range_rejected(self):
        dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        dims = {d: 0.5 for d in MATURITY_DIMENSIONS}
        dims["runtime"] = 1.5
        with pytest.raises(ValueError, match="runtime"):
            MaturitySnapshot(
                current_phase="47",
                phase_history=(),
                dimensions=dims,
                capability_count=0,
                limitation_count=0,
                snapshot_at=dt,
            )

    def test_negative_dimension_rejected(self):
        dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        dims = {d: 0.5 for d in MATURITY_DIMENSIONS}
        dims["self"] = -0.1
        with pytest.raises(ValueError, match="self"):
            MaturitySnapshot(
                current_phase="47",
                phase_history=(),
                dimensions=dims,
                capability_count=0,
                limitation_count=0,
                snapshot_at=dt,
            )


class TestSelfModel:
    """SelfModel 核心不变式。"""

    def _make_self_model(self, version=1, limitations=None):
        import datetime as dtm
        now = dtm.datetime.now(dtm.timezone.utc)
        return SelfModel(
            model_id=f"SM-v{version}",
            version=version,
            capability_states=(),
            limitations=limitations or PRESET_LIMITATIONS,
            maturity=MaturitySnapshot(
                current_phase="47",
                phase_history=(),
                dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
                capability_count=0,
                limitation_count=len(PRESET_LIMITATIONS),
                snapshot_at=now,
            ),
            statement=f"Self model v{version}: deterministic cognitive engine",
            created_at=now,
            previous_version_id=None,
            governor_approval_id=f"GOV-APPROVE-v{version}",
        )

    def test_valid_self_model(self):
        sm = self._make_self_model()
        assert sm.version == 1
        assert sm.has_preset_limitations() is True

    def test_version_must_be_positive(self):
        import datetime as dtm
        now = dtm.datetime.now(dtm.timezone.utc)
        with pytest.raises(ValueError, match="version"):
            SelfModel(
                model_id="SM-0", version=0,
                capability_states=(),
                limitations=PRESET_LIMITATIONS,
                maturity=MaturitySnapshot(
                    current_phase="47", phase_history=(),
                    dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
                    capability_count=0, limitation_count=5, snapshot_at=now,
                ),
                statement="test", created_at=now,
                previous_version_id=None, governor_approval_id="g",
            )

    def test_empty_model_id_rejected(self):
        import datetime as dtm
        now = dtm.datetime.now(dtm.timezone.utc)
        with pytest.raises(ValueError, match="model_id"):
            SelfModel(
                model_id="", version=1,
                capability_states=(),
                limitations=PRESET_LIMITATIONS,
                maturity=MaturitySnapshot(
                    current_phase="47", phase_history=(),
                    dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
                    capability_count=0, limitation_count=5, snapshot_at=now,
                ),
                statement="test", created_at=now,
                previous_version_id=None, governor_approval_id="g",
            )

    def test_has_preset_limitations_true(self):
        sm = self._make_self_model()
        assert sm.has_preset_limitations() is True

    def test_has_preset_limitations_false_when_removed(self):
        import datetime as dtm
        now = dtm.datetime.now(dtm.timezone.utc)
        # 去掉一个预设局限
        limited = tuple(l for l in PRESET_LIMITATIONS if "不能创建新目标" not in l.description)
        sm = SelfModel(
            model_id="SM-bad", version=1,
            capability_states=(),
            limitations=limited,
            maturity=MaturitySnapshot(
                current_phase="47", phase_history=(),
                dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
                capability_count=0, limitation_count=len(limited), snapshot_at=now,
            ),
            statement="test", created_at=now,
            previous_version_id=None, governor_approval_id="g",
        )
        assert sm.has_preset_limitations() is False

    def test_capability_names(self):
        import datetime as dtm
        now = dtm.datetime.now(dtm.timezone.utc)
        caps = (
            CapabilityState(
                name=CapabilityName.TEXT_UNDERSTANDING,
                confidence_score=0.9, belief_ids=(),
                evidence_summary="good", last_updated=now,
            ),
            CapabilityState(
                name=CapabilityName.BOUNDARY_AWARENESS,
                confidence_score=0.95, belief_ids=(),
                evidence_summary="excellent", last_updated=now,
            ),
        )
        sm = SelfModel(
            model_id="SM-caps", version=1,
            capability_states=caps,
            limitations=PRESET_LIMITATIONS,
            maturity=MaturitySnapshot(
                current_phase="47", phase_history=(),
                dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
                capability_count=2, limitation_count=5, snapshot_at=now,
            ),
            statement="test", created_at=now,
            previous_version_id=None, governor_approval_id="g",
        )
        names = sm.capability_names()
        assert names == ("text-understanding", "boundary-awareness")

    def test_limitations_by_category(self):
        sm = self._make_self_model()
        arch = sm.limitations_by_category("architectural")
        assert len(arch) >= 3  # 至少 3 条 architectural

    def test_limitations_by_severity(self):
        sm = self._make_self_model()
        hard = sm.limitations_by_severity("hard")
        assert len(hard) >= 3  # 至少 3 条 hard

    def test_frozen_dataclass(self):
        sm = self._make_self_model()
        with pytest.raises((TypeError, AttributeError)):
            sm.version = 2
