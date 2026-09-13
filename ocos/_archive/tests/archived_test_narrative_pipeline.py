"""NarrativePipeline 推导层单元测试。"""
from __future__ import annotations

import pytest

from ocos.engines.narrative_pipeline import (
    apply_budget_constraints,
    derive_policy,
    _derive_pov_type,
    _derive_emotion_profile,
    _chapter_base_intensity,
)


class TestDerivePolicy:
    """Contract → Policy 推导。"""

    def test_default_policy_for_relationship(self):
        """relationship driver 推导正确 pacing 和 emotion 配置。"""
        contract = {
            "primary_driver": "relationship",
            "reveal_strategy": "gradual",
            "emotion_curve": "oscillation",
            "reader_expectation": {"closure": 0.3},
        }
        policy = derive_policy(contract)

        assert policy["pacing_profile"]["default_pacing_type"] == "character_moment"
        assert policy["pacing_profile"]["default_intensity"] > 0
        assert policy["voice_profile"]["pov_type"] == "single"
        assert policy["emotion_profile"]["curve"] == "oscillation"
        assert policy["chapter_ending"]["rule"] == "emotional_cliffhanger"

    def test_survival_driver_pacing(self):
        """survival driver 推导 rising_action pacing。"""
        contract = {"primary_driver": "survival"}
        policy = derive_policy(contract)
        assert policy["pacing_profile"]["default_pacing_type"] == "rising_action"

    def test_delayed_reveal_intensity_boost(self):
        """delayed reveal 提高 intensity factor。"""
        contract = {
            "primary_driver": "mystery",
            "reveal_strategy": "delayed",
            "pacing_profile": {"default_intensity": 0.5},
        }
        policy = derive_policy(contract)
        assert policy["pacing_profile"]["default_intensity"] > 0.5

    def test_catharsis_emotion_curve(self):
        """catharsis curve 推导 pressure→release→reflection 三阶段。"""
        contract = {"emotion_curve": "catharsis", "primary_driver": "relationship"}
        policy = derive_policy(contract)
        stages = policy["emotion_profile"]["stages"]
        assert "pressure" in stages
        assert "release" in stages
        assert stages["release"]["emotion"] == "catharsis"

    def test_pov_types(self):
        """POV 类型推导。"""
        assert _derive_pov_type({"pov_policy": {"type": "dual", "switching_rule": "chapter_boundary"}}) == "dual_chapter_boundary"
        assert _derive_pov_type({"pov_policy": {"type": "single"}}) == "single"
        assert _derive_pov_type({}) == "single"  # relationship default


class TestApplyConstraints:
    """Policy → Chapter 约束应用。"""

    def test_intensity_blend_respects_curve(self):
        """intensity blend 遵循进度曲线（开场低→高潮高→结尾回落）。"""
        chapters = [
            {"chapter": i, "intensity": 0.5, "pacing_type": "balanced"}
            for i in range(1, 11)
        ]
        policy = derive_policy({
            "primary_driver": "relationship",
            "pacing_profile": {"default_intensity": 0.7},
            "emotion_curve": "oscillation",
        })
        result = apply_budget_constraints(chapters, policy)

        intensities = [ch["intensity"] for ch in result]
        # 开场 < 中部
        assert intensities[0] < intensities[6], \
            f"Opening {intensities[0]:.2f} should be < climax {intensities[6]:.2f}"

        # 结尾回落
        assert intensities[-1] <= intensities[3] + 0.1

    def test_ending_rule_injection(self):
        """chapter_ending_rule 注入所有章节。"""
        chapters = [{"chapter": i, "intensity": 0.5} for i in range(1, 4)]
        policy = {"pacing_profile": {}, "voice_profile": {}, "emotion_profile": {},
                  "chapter_ending": {"rule": "cliffhanger"}}
        result = apply_budget_constraints(chapters, policy)
        for ch in result:
            assert ch["chapter_ending_rule"] == "cliffhanger"

    def test_emotion_target_oscillation(self):
        """oscillation 曲线在多个情感阶段间切换。"""
        chapters = [{"chapter": i, "intensity": 0.5} for i in range(1, 21)]
        policy = derive_policy({
            "primary_driver": "relationship",
            "emotion_curve": "oscillation",
        })
        result = apply_budget_constraints(chapters, policy)
        emotions = [ch.get("emotion_target", "") for ch in result]
        unique = set(emotions)
        # oscillation 应产生多种情感
        assert len(unique) >= 3, \
            f"oscillation should produce 3+ emotions, got {unique}"
        assert "warmth" in unique or "catharsis" in unique, \
            f"Should have warm/catharsis peaks, got {unique}"

    def test_nonlinear_ratchet_curve(self):
        """ratchet 曲线：tension 逐步升温不回落。"""
        chapters = [{"chapter": i, "intensity": 0.5} for i in range(1, 11)]
        policy = derive_policy({
            "primary_driver": "power",
            "emotion_curve": "ratchet",
        })
        result = apply_budget_constraints(chapters, policy)
        emotions = [ch.get("emotion_target", "") for ch in result]
        assert "curiosity" in emotions
        assert "catharsis" in emotions

    def test_resonance_curve(self):
        """resonance 曲线产生 connection→pain→acceptance 弧。"""
        chapters = [{"chapter": i, "intensity": 0.5} for i in range(1, 11)]
        policy = derive_policy({
            "primary_driver": "relationship",
            "emotion_curve": "resonance",
        })
        result = apply_budget_constraints(chapters, policy)
        emotions = [ch.get("emotion_target", "") for ch in result]
        unique = set(emotions)
        assert "warmth" in unique or "pain" in unique or "acceptance" in unique


class TestChapterIntensity:
    """章节基础 intensity 计算。"""

    def test_setup_phase(self):
        assert _chapter_base_intensity(0.1, {"default_intensity": 0.5}) == 0.4

    def test_climax_phase(self):
        assert _chapter_base_intensity(0.85, {"default_intensity": 0.5}) == 0.75

    def test_resolution_phase(self):
        assert _chapter_base_intensity(0.95, {"default_intensity": 0.5}) == 0.5
