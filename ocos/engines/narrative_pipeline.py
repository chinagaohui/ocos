"""NarrativePipeline — Narrative Contract → Policy → Budget 推导。

将 Narrative Contract 的参数转化为 WriterEngine 可消费的章节规划约束。
独立于 opentale 包，纯规则推导。

三种覆盖模式（参见 override-strategy.md）:
  - Blend:   强度混合（50/50）
  - Override:直接覆盖
  - Inject:  追加约束文本
"""

from __future__ import annotations

from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 默认策略配置 ────────────────────────────────────────────────

_DEFAULT_PACING_TYPES = {
    "survival": "rising_action",
    "relationship": "character_moment",
    "truth": "revelation",
    "power": "rising_action",
    "mystery": "oscillating",
}

_DEFAULT_INTENSITY = 0.5
_DEFAULT_DIALOGUE_WEIGHT = 0.35
_DEFAULT_DESCRIPTION_WEIGHT = 0.25

# 非线性（oscillation / delayed 需要更高 intensity 实现)
_INTENSITY_FACTOR = {
    "gradual": 1.0,
    "oscillation": 1.3,
    "delayed": 1.5,
    "simultaneous": 0.8,
}


def derive_policy(contract: dict[str, Any]) -> dict[str, Any]:
    """Contract → Policy 推导。

    输入：Narrative Contract 参数（来自 narrative_contract.json）
    输出：Policy 字典（包含 pacing_profile, voice_profile, emotion_profile, ending）
    """
    logger.info("derive_policy", extra=dict(
        primary_driver=contract.get("primary_driver"),
        genre=contract.get("genre"),
    ))
    primary_driver = contract.get("primary_driver", "general")

    # ── Pacing Profile ───────────────────────────────────────
    pacing_type = _DEFAULT_PACING_TYPES.get(primary_driver, "balanced")
    reveal = contract.get("reveal_strategy", "gradual")
    intensity_base = contract.get("pacing_profile", {}).get(
        "default_intensity", _DEFAULT_INTENSITY
    )
    intensity = round(intensity_base * _INTENSITY_FACTOR.get(reveal, 1.0), 2)

    chapter_focus = contract.get("chapter_focus", {})
    total = sum(chapter_focus.values())
    if total > 0:
        dialogue_weight = round(
            chapter_focus.get("relationship", 0) / total * 0.5 + _DEFAULT_DIALOGUE_WEIGHT,
            2,
        )
    else:
        dialogue_weight = _DEFAULT_DIALOGUE_WEIGHT
    description_weight = round(1.0 - dialogue_weight - 0.4, 2)  # 40% 基础动作/叙事

    # ── Voice Profile ────────────────────────────────────────
    emotion_curve = contract.get("emotion_curve", "oscillation")
    reader_expectation = contract.get("reader_expectation", {})
    chapter_ending_type = _derive_ending_type(
        reveal, emotion_curve, reader_expectation
    )

    # ── POV Profile ──────────────────────────────────────────
    pov_type = _derive_pov_type(contract)

    # ── Emotion Profile ──────────────────────────────────────
    emotion_profile = _derive_emotion_profile(
        primary_driver, emotion_curve, contract
    )

    policy = {
        "pacing_profile": {
            "default_pacing_type": pacing_type,
            "default_intensity": intensity,
            "dialogue_weight": dialogue_weight,
            "description_weight": description_weight,
        },
        "voice_profile": {
            "pov_type": pov_type,
        },
        "emotion_profile": emotion_profile,
        "chapter_ending": {
            "rule": chapter_ending_type,
        },
        "_primary_driver": primary_driver,
    }
    return policy


def apply_budget_constraints(
    chapters: list[dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """将 Policy 约束应用到章节规划。

    三种覆盖模式:
      - Blend:   intensity → mix with existing
      - Override: pacing_type, dialogue_ratio, description_ratio
      - Inject:   pov_block, chapter_ending_rule
    """
    pacing = policy.get("pacing_profile", {})
    voice = policy.get("voice_profile", {})
    ending = policy.get("chapter_ending", {})
    emotion_profile = policy.get("emotion_profile", {})

    total = len(chapters)

    for i, ch in enumerate(chapters):
        progress = (i + 1) / total  # 0.0 → 1.0

        # ── Blend: intensity ─────────────────────────────────
        base_intensity = _chapter_base_intensity(progress, pacing)
        existing_intensity = ch.get("intensity", 0.5)
        ch["intensity"] = round(
            existing_intensity * 0.5 + base_intensity * 0.5, 2
        )

        # ── Override: pacing_type ────────────────────────────
        default_pacing = _chapter_pacing_by_progress(
            progress, pacing.get("default_pacing_type", "balanced")
        )
        ch["pacing_type"] = default_pacing
        ch["dialogue_ratio"] = round(pacing.get("dialogue_weight", 0.35), 2)
        ch["description_ratio"] = round(pacing.get("description_weight", 0.25), 2)

        # ── Inject: emotion target ───────────────────────────
        emotion_target = _chapter_emotion_target(progress, emotion_profile)
        if emotion_target:
            ch["emotion_target"] = emotion_target["emotion"]
            ch["emotion_type"] = emotion_target["type"]

        # ── Inject: chapter ending ───────────────────────────
        ch["chapter_ending_rule"] = ending.get("rule", "cliffhanger")

        # ── Inject: POV ──────────────────────────────────────
        ch["pov_type"] = voice.get("pov_type", "single")

    return chapters


# ── 辅助函数 ────────────────────────────────────────────────────


def _chapter_base_intensity(progress: float, pacing: dict) -> float:
    """基于章节进度计算 base intensity。"""
    base = pacing.get("default_intensity", _DEFAULT_INTENSITY)
    # 开场略低，高潮最高，结尾回落
    if progress < 0.2:
        return round(base * 0.8, 2)
    elif progress < 0.5:
        return round(base * 1.0, 2)
    elif progress < 0.8:
        return round(base * 1.3, 2)
    elif progress < 0.95:
        return round(base * 1.5, 2)
    else:
        return round(base * 1.0, 2)


def _chapter_pacing_by_progress(progress: float, default: str) -> str:
    """基于进度选择 pacing 子类型。"""
    if progress < 0.2:
        return "exposition"
    elif progress < 0.4:
        return "rising_action"
    elif progress < 0.7:
        return default
    elif progress < 0.9:
        return "climax"
    else:
        return "resolution"


def _chapter_emotion_target(
    progress: float,
    emotion_profile: dict[str, Any],
) -> dict[str, str] | None:
    """基于进度和 emotion_curve 返回情感目标。"""
    curve = emotion_profile.get("curve", "oscillation")
    stages = emotion_profile.get("stages", {})
    if not stages:
        return None

    # 找到当前进度对应的阶段
    stage_names = sorted(stages.keys(), key=lambda k: stages[k]["start"])
    current_stage = stage_names[-1]
    for s in stage_names:
        stage = stages[s]
        if stage["start"] <= progress <= stage["end"]:
            current_stage = s
            break

    stage_data = stages.get(current_stage, {})
    return {
        "emotion": stage_data.get("emotion", "neutral"),
        "type": stage_data.get("type", "build"),
    }


def _derive_ending_type(
    reveal: str,
    emotion_curve: str,
    reader_expectation: dict[str, float],
) -> str:
    """推导章节结尾类型。"""
    closure = reader_expectation.get("closure", 0.5)
    if closure < 0.3:
        return "cliffhanger"
    elif reveal == "delayed":
        return "revelation"
    elif emotion_curve == "catharsis":
        return "emotional_release"
    elif emotion_curve == "oscillation":
        return "emotional_cliffhanger"
    return "resolution"


def _derive_pov_type(contract: dict[str, Any]) -> str:
    """从 contract 中推导 POV 类型。"""
    pov_policy = contract.get("pov_policy", {})
    if pov_policy:
        pov_type = pov_policy.get("type", "single")
        if pov_type == "dual":
            return f"dual_{pov_policy.get('switching_rule', 'chapter_boundary')}"
        return pov_type
    # 基于 primary_driver 的默认：情感驱动默认单女主
    primary = contract.get("primary_driver", "relationship")
    return "single" if primary in ("relationship",) else "omniscient"


def _derive_emotion_profile(
    primary_driver: str,
    emotion_curve: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """推导情感轮廓。"""
    if emotion_curve == "ratchet":
        stages = {
            "setup": {"start": 0.0, "end": 0.2, "emotion": "curiosity", "type": "build"},
            "escalation": {"start": 0.2, "end": 0.7, "emotion": "tension", "type": "rise"},
            "peak": {"start": 0.7, "end": 0.9, "emotion": "catharsis", "type": "climax"},
            "aftermath": {"start": 0.9, "end": 1.0, "emotion": "resonance", "type": "fall"},
        }
    elif emotion_curve == "oscillation":
        stages = {
            "upbeat": {"start": 0.0, "end": 0.15, "emotion": "hope", "type": "rise"},
            "setback": {"start": 0.15, "end": 0.3, "emotion": "anxiety", "type": "fall"},
            "recovery": {"start": 0.3, "end": 0.5, "emotion": "warmth", "type": "rise"},
            "crisis": {"start": 0.5, "end": 0.7, "emotion": "despair", "type": "fall"},
            "resolution": {"start": 0.7, "end": 0.9, "emotion": "catharsis", "type": "climax"},
            "calm": {"start": 0.9, "end": 1.0, "emotion": "peace", "type": "fall"},
        }
    elif emotion_curve == "catharsis":
        stages = {
            "pressure": {"start": 0.0, "end": 0.7, "emotion": "tension", "type": "build"},
            "release": {"start": 0.7, "end": 0.85, "emotion": "catharsis", "type": "climax"},
            "reflection": {"start": 0.85, "end": 1.0, "emotion": "melancholy", "type": "fall"},
        }
    else:  # resonance
        stages = {
            "intro": {"start": 0.0, "end": 0.15, "emotion": "curiosity", "type": "build"},
            "connection": {"start": 0.15, "end": 0.5, "emotion": "warmth", "type": "rise"},
            "conflict": {"start": 0.5, "end": 0.75, "emotion": "pain", "type": "fall"},
            "reconciliation": {"start": 0.75, "end": 0.9, "emotion": "acceptance", "type": "climax"},
            "resonance": {"start": 0.9, "end": 1.0, "emotion": "peace", "type": "fall"},
        }

    return {
        "curve": emotion_curve,
        "stages": stages,
        "primary_driver": primary_driver,
    }
