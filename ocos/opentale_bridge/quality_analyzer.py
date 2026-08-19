"""Phase 59: QualityAnalyzer — OCOS 自主分析 OpenTale 产出的文学质量。

不依赖外部评分。OCOS 自己读文本、自己判断、自己形成意见。
这才是"大脑"在阅读自己的"器官"写出来的东西。

5维度分析:
  1. 叙事密度 — 场景切换/对白比/段落节奏
  2. 角色一致性 — 命名实体出现/对话归属/弧光进展
  3. 情感曲线 — 情感词密度/高峰/波动
  4. 类型合规 — 言情/悬疑/权谋 各类型的结构约束
  5. 语言质量 — 句长方差/段落密度/可读性
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import re
from collections import Counter


# ═══ 数据模型 ═══

@dataclass
class DimensionScore:
    """单维度分析结果。"""
    dimension: str = ""           # "narrative_density" | "character_coherence" | ...
    score: float = 0.0            # 0.0 - 1.0
    confidence: float = 0.0       # 0.0 - 1.0（分析本身的置信度，取决于数据量）
    findings: list[str] = field(default_factory=list)    # 发现
    concerns: list[str] = field(default_factory=list)    # 问题
    raw_metrics: dict[str, Any] = field(default_factory=dict)  # 底层指标


@dataclass
class QualityReport:
    """OCOS 自己对章节质量的完整判断。"""
    chapter_number: int
    chapter_title: str = ""
    analyzed_at: str = ""

    # 5维度
    narrative_density: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="narrative_density"))
    character_coherence: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="character_coherence"))
    emotional_curve: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="emotional_curve"))
    genre_compliance: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="genre_compliance"))
    language_quality: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="language_quality"))

    # 综合
    overall_score: float = 0.0        # 加权综合分
    summary: str = ""                 # 一句话总结
    recommendations: list[str] = field(default_factory=list)

    # 参考：外部评分（从 OpenTale 传过来的，仅供参考）
    external_quality: Optional[float] = None
    external_narrative: Optional[float] = None

    def to_ocos_feedback(self) -> dict:
        """转为 OCOS 可消化的反馈格式。"""
        return {
            "type": "quality_analysis",
            "chapter": self.chapter_number,
            "ocos_overall": self.overall_score,
            "ocos_dimensions": {
                d.dimension: {"score": d.score, "concerns": d.concerns}
                for d in [self.narrative_density, self.character_coherence,
                          self.emotional_curve, self.genre_compliance,
                          self.language_quality]
            },
            "summary": self.summary,
            "recommendations": self.recommendations,
            "reference_external": self.external_quality,
            "analysis_divergence": (
                abs(self.overall_score - self.external_quality)
                if self.external_quality is not None else None
            ),
        }

    # ═══ Repair Loop (Phase 59-i) ═══

    # 触发重写的阈值
    REPAIR_OVERALL_THRESHOLD = 0.6      # 综合分低于此值 → 重写
    REPAIR_DIMENSION_THRESHOLD = 0.3    # 任一维度低于此值 → 重写
    MAX_REPAIR_ATTEMPTS = 3             # 最多重写 3 次

    def needs_repair(self,
                     overall_threshold: float | None = None,
                     dimension_threshold: float | None = None) -> bool:
        """OCOS 判断这章是否需要重写。"""
        overall_t = overall_threshold if overall_threshold is not None else self.REPAIR_OVERALL_THRESHOLD
        dim_t = dimension_threshold if dimension_threshold is not None else self.REPAIR_DIMENSION_THRESHOLD

        if self.overall_score < overall_t:
            return True

        dims = [self.narrative_density, self.character_coherence,
                self.emotional_curve, self.genre_compliance, self.language_quality]
        if any(d.score < dim_t for d in dims):
            return True

        return False

    def failing_dimensions(self, threshold: float | None = None) -> list[str]:
        """返回不达标的维度名列表。"""
        t = threshold if threshold is not None else self.REPAIR_DIMENSION_THRESHOLD
        dims = [self.narrative_density, self.character_coherence,
                self.emotional_curve, self.genre_compliance, self.language_quality]
        return [d.dimension for d in dims if d.score < t]

    def repair_guidance(self) -> dict:
        """为 OpenTale 生成重写指导：
        - 哪些维度出了问题
        - 每个维度的具体建议
        - 哪些内容可以保留
        """
        failing = self.failing_dimensions()
        guidance: dict[str, Any] = {
            "repair_reason": "quality_below_threshold",
            "overall_score": self.overall_score,
            "threshold": self.REPAIR_OVERALL_THRESHOLD,
            "failing_dimensions": failing,
            "dimension_guidance": {},
            "preserve": [],
        }

        for dim_name in failing:
            d = getattr(self, dim_name)
            guidance["dimension_guidance"][dim_name] = {
                "current_score": d.score,
                "threshold": self.REPAIR_DIMENSION_THRESHOLD,
                "concerns": d.concerns,
                "suggestions": self._repair_suggestions_for(dim_name),
            }

        # 保留项：哪些东西不用改
        if self.character_coherence.score >= 0.7:
            guidance["preserve"].append("character_profiles")
        if self.narrative_density.score >= 0.5:
            guidance["preserve"].append("scene_structure")
        if self.emotional_curve.score >= 0.5 and "emotional_curve" not in failing:
            guidance["preserve"].append("emotional_beats")

        return guidance

    @staticmethod
    def _repair_suggestions_for(dimension: str) -> list[str]:
        """针对不达标维度的具体修复建议。"""
        suggestions = {
            "narrative_density": [
                "增加对白比例至 20%-50% 之间",
                "加入至少 1 次场景切换（时间或地点变化）",
                "变化句子长度，避免单一节奏",
            ],
            "character_coherence": [
                "确保主角在章节中至少有 3 次出场",
                "检查角色对话是否符合人设",
                "确保至少两个主要角色有互动场景",
            ],
            "emotional_curve": [
                "增加情感词密度至 3% 以上",
                "加入至少 1 个情感高峰场景",
                "确保情绪有起伏（不要全程同一情感基调）",
            ],
            "genre_compliance": [
                "按类型要求调整内容结构",
                "言情: 增加双人互动场景和情感描写",
                "悬疑: 增加信息释放节点和悬念设置",
                "动作: 增加动作描写密度",
            ],
            "language_quality": [
                "减少超长句（>40词），拆分复杂句子",
                "避免同一词语的过度重复",
                "确保段落长度有变化，避免全部长段或全部碎片",
            ],
        }
        return suggestions.get(dimension, ["重新审视该维度的内容质量"])


# ═══ 情感词典 ═══

EMOTION_LEXICON = {
    "love": 1.0, "hate": -1.0, "anger": -0.8, "fear": -0.7,
    "joy": 0.9, "sadness": -0.6, "hope": 0.7, "despair": -0.9,
    "tenderness": 0.8, "longing": 0.6, "jealousy": -0.5, "regret": -0.4,
    "passion": 0.9, "rage": -0.8, "grief": -0.9, "ecstasy": 1.0,
    "anxiety": -0.6, "relief": 0.7, "resentment": -0.7, "gratitude": 0.8,
    "desire": 0.7, "shame": -0.5, "pride": 0.5, "disgust": -0.7,
    "admiration": 0.8, "contempt": -0.6, "sympathy": 0.6, "pity": -0.3,
    "warmth": 0.7, "coldness": -0.5, "excitement": 0.8, "dread": -0.8,
    "trust": 0.6, "betrayal": -0.9, "devotion": 0.9, "obsession": -0.4,
    "courage": 0.7, "cowardice": -0.6, "wonder": 0.8, "horror": -0.9,
    "peace": 0.6, "turmoil": -0.7, "contentment": 0.7, "frustration": -0.5,
    "attraction": 0.8, "rejection": -0.7, "intimacy": 0.8, "loneliness": -0.6,
    "protectiveness": 0.7, "vulnerability": -0.2,
}

# 言情类型专用情感词（中文 + 英文）
ROMANCE_EMOTIONS = {
    "心动": 0.9, "心疼": 0.7, "吃醋": -0.4, "撒娇": 0.5,
    "宠溺": 0.9, "暗恋": 0.5, "表白": 0.9, "分手": -0.8,
    "复合": 0.7, "误会": -0.6, "误会解开": 0.8, "考验": -0.3,
    "心跳加速": 0.9, "脸红": 0.6, "眼神交汇": 0.7, "牵手": 0.8,
    "接吻": 0.9, "拥抱": 0.8, "守护": 0.8, "等待": 0.4,
    "相思": 0.6, "纠缠": -0.4, "霸道": 0.3, "温柔": 0.7,
    "深情": 0.8, "绝情": -0.9, "虐心": -0.7, "甜": 0.8,
}

# 动作/权谋类型关键词
ACTION_KEYWORDS = [
    "sword", "blade", "strike", "attack", "defend", "kill", "fight",
    "battle", "war", "strategy", "scheme", "plot", "conspiracy",
    "betray", "assassinate", "ambush", "siege", "charge", "retreat",
    "剑", "刀", "杀", "战", "攻", "守", "谋", "计",
    "暗算", "伏击", "围城", "突围", "列阵", "厮杀",
]

# 对话标记
DIALOGUE_MARKERS_CN = ['"', '"', '"', '"', '「', '」', '『', '』', '：', '“', '”']
DIALOGUE_MARKERS_EN = ['"', "'", '"', '"']


# ═══ QualityAnalyzer ═══

class QualityAnalyzer:
    """OCOS 自主文学质量分析器。

    读文本 → 5维度分析 → 出报告。这是 OCOS 自己的"文学品味"。
    """

    def __init__(self):
        self._analysis_count: int = 0

    def analyze(self, chapter_text: str, genre: str = "romance",
                chapter_number: int = 1, chapter_title: str = "",
                expected_arcs: Optional[dict[str, float]] = None,
                external_quality: Optional[float] = None,
                external_narrative: Optional[float] = None) -> QualityReport:
        """读一章文本，出 OCOS 自己的质量报告。

        Args:
            chapter_text: 完整章节文本
            genre: 类型 (romance/suspense/wuxia/political)
            chapter_number: 章节号
            chapter_title: 章节标题
            expected_arcs: 预期的角色弧光进度 {char_name: expected_progress}
            external_quality: 外部评分（参考值，不是 OCOS 自己的判断）
            external_narrative: 外部叙事评分
        """
        from datetime import datetime, timezone

        self._analysis_count += 1
        text = chapter_text.strip()
        if not text:
            return QualityReport(
                chapter_number=chapter_number,
                overall_score=0.0,
                summary="No text to analyze",
            )

        sentences = self._split_sentences(text)
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        words = text.split()

        report = QualityReport(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            external_quality=external_quality,
            external_narrative=external_narrative,
        )

        # ── 1. 叙事密度 ──
        report.narrative_density = self._analyze_narrative_density(
            text, sentences, paragraphs, words)

        # ── 2. 角色一致性 ──
        report.character_coherence = self._analyze_character_coherence(
            text, sentences, expected_arcs)

        # ── 3. 情感曲线 ──
        report.emotional_curve = self._analyze_emotional_curve(
            text, sentences, genre)

        # ── 4. 类型合规 ──
        report.genre_compliance = self._analyze_genre_compliance(
            text, genre, sentences, paragraphs)

        # ── 5. 语言质量 ──
        report.language_quality = self._analyze_language_quality(
            text, sentences, paragraphs, words)

        # ── 综合评分 ──
        dims = [
            report.narrative_density,
            report.character_coherence,
            report.emotional_curve,
            report.genre_compliance,
            report.language_quality,
        ]
        # Weighted: genre compliance + emotional curve are most important for fiction
        weights = [0.15, 0.20, 0.25, 0.25, 0.15]
        report.overall_score = round(
            sum(d.score * w for d, w in zip(dims, weights)), 3)

        # ── 总结 ──
        concerns = []
        for d in dims:
            concerns.extend(d.concerns)
        if not concerns:
            report.summary = f"OCOS quality assessment: {report.overall_score:.2f} — solid chapter, no major concerns."
        elif report.overall_score >= 0.7:
            report.summary = f"OCOS quality assessment: {report.overall_score:.2f} — good but needs attention: {'; '.join(concerns[:2])}"
        else:
            report.summary = f"OCOS quality assessment: {report.overall_score:.2f} — significant issues: {'; '.join(concerns[:3])}"

        report.recommendations = [f"[{d.dimension}] {c}" for d in dims for c in d.concerns]

        return report

    # ═══ 维度1: 叙事密度 ═══

    def _analyze_narrative_density(self, text: str, sentences: list[str],
                                    paragraphs: list[str], words: list[str]) -> DimensionScore:
        """分析叙事密度：场景变化、对白/叙述比、段落节奏。"""
        findings = []
        concerns = []

        # 对白比例
        dialogue_ratio = self._dialogue_ratio(text)

        # 段落平均长度
        avg_para_len = len(sentences) / max(len(paragraphs), 1)

        # 句子长度方差 (节奏变化)
        sent_lens = [len(s.split()) for s in sentences]
        sent_var = self._variance(sent_lens) if len(sent_lens) > 1 else 0

        # 场景切换检测 (空行间隔 + 时间/地点转折词)
        scene_break_count = self._count_scene_breaks(text, paragraphs)

        raw = {
            "dialogue_ratio": round(dialogue_ratio, 3),
            "avg_paragraph_sentences": round(avg_para_len, 1),
            "sentence_length_variance": round(sent_var, 1),
            "scene_breaks": scene_break_count,
            "total_sentences": len(sentences),
            "total_paragraphs": len(paragraphs),
        }

        if dialogue_ratio < 0.1 and len(paragraphs) > 10:
            concerns.append(f"对白比例极低 ({dialogue_ratio:.1%})，叙事可能过于陈述性")
            findings.append(f"对白比={dialogue_ratio:.1%}，偏叙述")
        elif dialogue_ratio > 0.6:
            concerns.append(f"对白比例过高 ({dialogue_ratio:.1%})，可能缺乏叙述支撑")
            findings.append(f"对白比={dialogue_ratio:.1%}，对话驱动")
        elif 0.2 <= dialogue_ratio <= 0.5:
            findings.append(f"对白比={dialogue_ratio:.1%}，均衡")

        if sent_var > 100:
            findings.append(f"句长变化大 (var={sent_var:.0f})，节奏丰富")
        elif sent_var < 20:
            concerns.append(f"句长变化小 (var={sent_var:.0f})，节奏单调")

        if scene_break_count == 0 and len(paragraphs) > 20:
            concerns.append(f"{len(paragraphs)}段但零场景切换，缺乏空间/时间推进")

        # Score
        score = 0.7  # base
        score += 0.15 if 0.2 <= dialogue_ratio <= 0.5 else (-0.1 if dialogue_ratio < 0.1 or dialogue_ratio > 0.6 else 0)
        score += 0.1 if sent_var > 50 else 0
        score += 0.05 if scene_break_count > 0 else 0
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension="narrative_density",
            score=round(score, 3),
            confidence=min(1.0, len(sentences) / 50),
            findings=findings,
            concerns=concerns,
            raw_metrics=raw,
        )

    # ═══ 维度2: 角色一致性 ═══

    def _analyze_character_coherence(self, text: str, sentences: list[str],
                                      expected_arcs: Optional[dict] = None) -> DimensionScore:
        """分析角色一致性：命名实体出现、对话归属、弧光进展。"""
        findings = []
        concerns = []

        # 提取可能的角色名（大写开头非句首的词 + 中文名检测）
        char_mentions = self._extract_character_mentions(text)

        raw = {
            "characters_detected": list(char_mentions.keys()),
            "mention_counts": dict(char_mentions.most_common(5)),
        }

        if not char_mentions:
            concerns.append("未检测到明确角色名，角色标签可能缺失")
            return DimensionScore(
                dimension="character_coherence",
                score=0.3, confidence=0.2,
                findings=["角色检测为空"],
                concerns=concerns,
                raw_metrics=raw,
            )

        # 角色出现频率分布
        total_mentions = sum(char_mentions.values())
        if len(char_mentions) >= 2:
            top_char = char_mentions.most_common(2)
            focus_ratio = top_char[0][1] / max(total_mentions, 1)
            findings.append(f"主角聚焦度={focus_ratio:.1%} (主角={top_char[0][0]})")
            if focus_ratio < 0.2:
                concerns.append(f"主角 ({top_char[0][0]}) 出场占比仅 {focus_ratio:.1%}，焦点分散")

        # 至少有两个角色
        if len(char_mentions) >= 2:
            findings.append(f"识别到 {len(char_mentions)} 个角色: {', '.join(list(char_mentions.keys())[:5])}")
        else:
            concerns.append(f"仅检测到 {len(char_mentions)} 个角色，双人互动场景可能不足")

        # 弧光预期
        if expected_arcs:
            for char, expected in expected_arcs.items():
                actual_ratio = char_mentions.get(char, 0) / max(total_mentions, 1)
                findings.append(f"{char}: 预计弧光 {expected:.1%}, 实际出场比 {actual_ratio:.1%}")

        score = 0.6  # base
        score += 0.2 if len(char_mentions) >= 2 else 0
        score += 0.1 if total_mentions > 5 else 0
        score += 0.1 if len(char_mentions) >= 3 else 0
        score = max(0.0, min(1.0, score))
        confidence = min(1.0, total_mentions / 20)

        return DimensionScore(
            dimension="character_coherence",
            score=round(score, 3),
            confidence=confidence,
            findings=findings,
            concerns=concerns,
            raw_metrics=raw,
        )

    # ═══ 维度3: 情感曲线 ═══

    def _analyze_emotional_curve(self, text: str, sentences: list[str],
                                  genre: str) -> DimensionScore:
        """分析情感曲线：情感词密度、高峰、波动。"""
        findings = []
        concerns = []

        text_lower = text.lower()
        emotions_found: list[tuple[str, float, int]] = []  # (word, valence, position)

        # 英文情感词
        for word, valence in EMOTION_LEXICON.items():
            for m in re.finditer(r'' + word + r'', text_lower):
                emotions_found.append((word, valence, m.start()))

        # 中文情感词
        for word, valence in ROMANCE_EMOTIONS.items():
            for m in re.finditer(re.escape(word), text):
                emotions_found.append((word, valence, m.start()))

        total_words = len(text.split())
        emotion_density = len(emotions_found) / max(total_words, 1)

        valence_values = [v for _, v, _ in emotions_found] if emotions_found else [0]
        avg_valence = sum(valence_values) / len(valence_values)
        valence_variance = self._variance(valence_values) if len(valence_values) > 1 else 0

        # 检测情感高峰（连续高valence或密度区域）
        peaks = self._detect_emotional_peaks(emotions_found, sentences)

        raw = {
            "emotion_words_found": len(emotions_found),
            "emotion_density": round(emotion_density, 4),
            "avg_valence": round(avg_valence, 3),
            "valence_variance": round(valence_variance, 3),
            "emotional_peaks": len(peaks),
            "top_emotions": [w for w, _ in Counter([e[0] for e in emotions_found]).most_common(5)],
        }

        if emotion_density < 0.02:
            concerns.append(f"情感词密度极低 ({emotion_density:.1%})，文本可能情感平淡")
        elif emotion_density > 0.15:
            findings.append(f"情感词密度高 ({emotion_density:.1%})，情感饱满")
        else:
            findings.append(f"情感词密度={emotion_density:.1%}")

        if len(peaks) == 0 and len(sentences) > 20:
            concerns.append("未检测到明确情感高峰，情感曲线可能平坦")
        elif len(peaks) >= 2:
            findings.append(f"检测到 {len(peaks)} 个情感高峰，曲线有起伏")

        if valence_variance < 0.1 and len(emotions_found) > 5:
            concerns.append(f"情感值方差低 ({valence_variance:.2f})，情绪缺乏变化")
        elif valence_variance > 0.5:
            findings.append(f"情感波动大 (var={valence_variance:.2f})，情绪有张力")

        # Score
        score = 0.5
        score += 0.15 if emotion_density > 0.03 else 0
        score += 0.15 if len(peaks) >= 1 else 0
        score += 0.1 if valence_variance > 0.3 else 0
        score += 0.1 if len(emotions_found) > 5 else 0
        score = max(0.0, min(1.0, score))
        confidence = min(1.0, len(emotions_found) / 10)

        return DimensionScore(
            dimension="emotional_curve",
            score=round(score, 3),
            confidence=confidence,
            findings=findings,
            concerns=concerns,
            raw_metrics=raw,
        )

    # ═══ 维度4: 类型合规 ═══

    def _analyze_genre_compliance(self, text: str, genre: str,
                                   sentences: list[str], paragraphs: list[str]) -> DimensionScore:
        """分析类型合规性：各类型有不同的结构约束。"""
        findings = []
        concerns = []

        text_lower = text.lower()
        total_words = len(text.split())

        if genre == "romance":
            # 言情: 情感词密度 > 3%, 双人互动场景, 情感转折
            romance_count = 0
            for word in ROMANCE_EMOTIONS:
                romance_count += len(re.findall(re.escape(word), text))
            romance_density = romance_count / max(total_words, 1)

            # 双人场景 (两个角色名出现在同一段)
            chars = list(self._extract_character_mentions(text).keys())
            duo_scenes = 0
            if len(chars) >= 2:
                for para in paragraphs:
                    if all(c in para for c in chars[:2]):
                        duo_scenes += 1

            raw = {
                "romance_emotion_count": romance_count,
                "romance_emotion_density": round(romance_density, 4),
                "duo_scenes": duo_scenes,
                "detected_characters": chars[:2],
            }

            if romance_density >= 0.05:
                findings.append(f"言情情感密度={romance_density:.1%} ✓ (>5%)")
            elif romance_density >= 0.03:
                findings.append(f"言情情感密度={romance_density:.1%} (可接受)")
            else:
                concerns.append(f"言情情感密度={romance_density:.1%}，低于类型要求 (需>3%)")

            if duo_scenes >= 2:
                findings.append(f"双人互动场景: {duo_scenes} 个 ✓")
            elif duo_scenes == 1:
                findings.append(f"双人互动场景: 1 个 (建议增加)")
            else:
                concerns.append(f"未检测到双人互动场景，言情类型缺失核心互动")

            score = 0.5
            score += 0.25 if romance_density >= 0.05 else (0.1 if romance_density >= 0.03 else 0)
            score += 0.25 if duo_scenes >= 2 else (0.1 if duo_scenes >= 1 else 0)
            score = max(0.0, min(1.0, score))

        elif genre in ("suspense", "mystery"):
            # 悬疑: 信息释放节奏（疑问句密度、cliffhanger）
            question_count = sum(1 for s in sentences if '?' in s or '？' in s)
            info_beats = self._count_info_beats(text)
            raw = {
                "questions": question_count,
                "info_beats": info_beats,
            }
            if info_beats >= 3:
                findings.append(f"信息释放节点: {info_beats} 个 ✓")
            else:
                concerns.append(f"信息释放节点仅 {info_beats} 个，悬疑节奏不足")
            score = 0.5 + min(0.5, info_beats * 0.1)

        elif genre in ("wuxia", "action"):
            # 武侠/动作: 动作词密度
            action_count = sum(len(re.findall(re.escape(kw), text_lower)) for kw in ACTION_KEYWORDS)
            action_density = action_count / max(total_words, 1)
            raw = {"action_density": round(action_density, 4)}
            if action_density >= 0.03:
                findings.append(f"动作密度={action_density:.1%} ✓")
            else:
                concerns.append(f"动作密度={action_density:.1%}，低于动作类型要求")
            score = min(1.0, 0.5 + action_density * 10)

        elif genre in ("political", "palace"):
            # 权谋/宫斗: 对话密度(暗流) + 策略词
            dialogue_ratio = self._dialogue_ratio(text)
            strategy_count = sum(1 for s in sentences if any(
                kw in s for kw in ["计", "谋", "局", "算", "利用", "试探", "暗"]))
            raw = {
                "dialogue_ratio": round(dialogue_ratio, 3),
                "strategy_hints": strategy_count,
            }
            if dialogue_ratio >= 0.3:
                findings.append(f"对话密度={dialogue_ratio:.1%}，暗流涌动 ✓")
            else:
                concerns.append(f"对话密度={dialogue_ratio:.1%}，权谋需更多暗线对话")
            score = 0.5 + min(0.5, dialogue_ratio * 0.8)

        else:
            raw = {}
            findings.append(f"类型 '{genre}' 无特定合规检查，使用通用标准")
            score = 0.7

        score = max(0.0, min(1.0, score))
        return DimensionScore(
            dimension="genre_compliance",
            score=round(score, 3),
            confidence=min(1.0, total_words / 500),
            findings=findings,
            concerns=concerns,
            raw_metrics=raw,
        )

    # ═══ 维度5: 语言质量 ═══

    def _analyze_language_quality(self, text: str, sentences: list[str],
                                   paragraphs: list[str], words: list[str]) -> DimensionScore:
        """分析语言质量：句长分布、段落密度、可读性。"""
        findings = []
        concerns = []

        # 句子长度统计
        sent_lens = [len(s.split()) for s in sentences if s.split()]
        if not sent_lens:
            return DimensionScore(
                dimension="language_quality",
                score=0.0, confidence=0.0,
                findings=["无可分析句子"],
                raw_metrics={},
            )

        avg_sent_len = sum(sent_lens) / len(sent_lens)
        sent_var = self._variance(sent_lens)
        min_sent, max_sent = min(sent_lens), max(sent_lens)

        # 段落密度 (每段的句子数分布)
        para_sent_counts = []
        for para in paragraphs:
            para_sents = [s for s in self._split_sentences(para) if s.strip()]
            para_sent_counts.append(len(para_sents))
        avg_para_sents = sum(para_sent_counts) / max(len(para_sent_counts), 1)

        # 超长/超短句占比
        long_sents = sum(1 for l in sent_lens if l > 40)
        short_sents = sum(1 for l in sent_lens if l < 5)
        long_ratio = long_sents / len(sent_lens)
        short_ratio = short_sents / len(sent_lens)

        # 重复词检测
        word_freq = Counter(w.lower().strip('.,!?;:""''（）()[]{}《》') for w in words if len(w) > 2)
        top_repeated = word_freq.most_common(5)

        raw = {
            "total_words": len(words),
            "avg_sentence_length": round(avg_sent_len, 1),
            "sentence_length_variance": round(sent_var, 1),
            "min_sentence": min_sent,
            "max_sentence": max_sent,
            "avg_paragraph_sentences": round(avg_para_sents, 1),
            "long_sentence_ratio": round(long_ratio, 3),
            "short_sentence_ratio": round(short_ratio, 3),
            "top_repeated_words": top_repeated,
        }

        if 15 <= avg_sent_len <= 30:
            findings.append(f"平均句长 {avg_sent_len:.0f} 词，可读性好")
        elif avg_sent_len > 40:
            concerns.append(f"平均句长 {avg_sent_len:.0f} 词，偏长，可能影响可读性")
        elif avg_sent_len < 8:
            concerns.append(f"平均句长 {avg_sent_len:.0f} 词，偏短，可能过于碎片化")

        if sent_var > 60:
            findings.append(f"句长变化大，节奏有层次")
        elif sent_var < 15:
            concerns.append(f"句长变化 ({sent_var:.0f}) 小，节奏单一")

        if long_ratio > 0.2:
            concerns.append(f"超长句 ({long_ratio:.0%}) 占比过高")

        if short_ratio > 0.3:
            concerns.append(f"超短句 ({short_ratio:.0%}) 占比过高，可能碎片化")

        if top_repeated and top_repeated[0][1] > len(words) * 0.05:
            word, count = top_repeated[0]
            concerns.append(f"高频重复词 '{word}' ({count}次)，建议替换")

        # Score
        score = 0.7
        score += 0.1 if 12 <= avg_sent_len <= 35 else (-0.1 if avg_sent_len > 50 or avg_sent_len < 6 else 0)
        score += 0.1 if sent_var > 40 else 0
        score += 0.05 if long_ratio < 0.15 else (-0.05 if long_ratio > 0.25 else 0)
        score += 0.05 if short_ratio < 0.25 else 0
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension="language_quality",
            score=round(score, 3),
            confidence=min(1.0, len(words) / 200),
            findings=findings,
            concerns=concerns,
            raw_metrics=raw,
        )

    # ═══ 辅助方法 ═══

    def _dialogue_ratio(self, text: str) -> float:
        """估算对白比例。"""
        all_markers = DIALOGUE_MARKERS_CN + DIALOGUE_MARKERS_EN
        dialogue_chars = sum(text.count(m) for m in all_markers)
        return dialogue_chars / max(len(text), 1) / 2  # 每段对话有开闭两个引号

    def _count_scene_breaks(self, text: str, paragraphs: list[str]) -> int:
        """检测场景切换次数。"""
        breaks = 0
        # 空行分隔
        breaks += len(paragraphs) - 1 if len(paragraphs) > 1 else 0
        # 明确的场景分隔符
        breaks += len(re.findall(r'[*]{3,}|[─]{3,}|[—]{3,}', text))
        # 时间/地点转折
        time_breaks = len(re.findall(
            r'(?:次日|第二天|几天后|数日后|Meanwhile|Later|Earlier|The next day)',
            text, re.IGNORECASE))
        place_breaks = len(re.findall(
            r'(?:回到|来到|进入|离开|Meanwhile,? in|Back at)',
            text, re.IGNORECASE))
        breaks += time_breaks + place_breaks
        return breaks

    def _extract_character_mentions(self, text: str) -> Counter:
        """提取文本中的角色名提及。"""
        mentions = Counter()

        # 英文大写开头名 — use simple pattern without look-behind
        # Match (start | after period-comma-space) followed by a Capitalized name
        words_list = text.split()
        for i, w in enumerate(words_list):
            clean = w.strip('.,!?;:""''（）()[]{}《》')
            if (len(clean) >= 3 and clean[0].isupper() and clean[1:].islower()
                    and clean.lower() not in {'the', 'this', 'that', 'there', 'when',
                                              'where', 'which', 'what', 'with', 'from',
                                              'then', 'they', 'their', 'these', 'those',
                                              'after', 'before', 'into', 'upon', 'over',
                                              'under', 'through', 'while', 'still', 'again'}):
                mentions[clean] += 1

        # 中文角色名 (姓氏+名 或 双字名)
        cn_names = set()
        for m in re.finditer(r'(?:[沈赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张][\u4e00-\u9fff]{2,3})', text):
            cn_names.add(m.group())
        # 常见古言角色称呼
        title_patterns = [r'(?:王爷|将军|公主|郡主|太子|丞相|皇上|陛下|娘娘|公子|小姐)']
        for pat in title_patterns:
            for m in re.finditer(pat, text):
                cn_names.add(m.group())
        for name in cn_names:
            mentions[name] += text.count(name)

        return mentions

    def _detect_emotional_peaks(self, emotions: list[tuple[str, float, int]],
                                 sentences: list[str]) -> list[int]:
        """检测情感高峰位置。"""
        if not emotions or len(sentences) < 3:
            return []

        # 将情感词按句子位置分组
        sent_len_total = sum(len(s.split()) for s in sentences)
        if sent_len_total == 0:
            return []

        # 将文本分为10个区域
        zones = 10
        zone_valence = [0.0] * zones
        zone_count = [0] * zones

        text_len = sent_len_total
        for _, valence, pos in emotions:
            # pos is char position, approximate to zone
            zone = min(zones - 1, int(pos / max(text_len, 1) * zones))
            zone_valence[zone] += valence
            zone_count[zone] += 1

        # Find peaks: zone with high absolute valence and surrounded by lower
        peaks = []
        for i in range(1, zones - 1):
            if zone_count[i] >= 1 and abs(zone_valence[i]) > abs(zone_valence[i-1]) and                abs(zone_valence[i]) > abs(zone_valence[i+1]):
                peaks.append(i)

        return peaks

    def _count_info_beats(self, text: str) -> int:
        """统计信息释放节点（悬疑/推理）。"""
        beats = 0
        # 发现/揭示标记
        beats += len(re.findall(
            r'(?:发现|原来|竟然是|突然|猛然|意识到|终于|揭开了|真相|秘密)',
            text))
        # 疑问句
        beats += len(re.findall(r'[？?]', text))
        return min(beats, 20)  # cap

    def _split_sentences(self, text: str) -> list[str]:
        """分句。"""
        raw = re.split(r'(?<=[.!?。！？])\s+', text)
        return [s.strip() for s in raw if s.strip()]

    @staticmethod
    def _variance(values: list[float]) -> float:
        """计算方差。"""
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)


def quick_analyze() -> QualityReport:
    """快速验证 QualityAnalyzer。"""
    sample = """
Chapter 20: 雨夜告白

暴雨如注。沈昭宁站在王府朱门前，雨水顺着她的甲胄滴落。
她已经站了一个时辰。手心里的玉佩被握得发烫——那是他三年前亲手为她系上的。

"将军，请回吧。"门房第三次出来劝说。

她摇头。心跳加速。吃醋的苦涩还在喉间翻涌——今天早朝他身边站了另一个女人。
她不能等了。她守护了三年，等待了三年，今天必须表白。

突然，门开了。

不是门房。是他。

顾衍之站在雨中，没撑伞，眼神像要将她看穿。"你疯了？"

"对。"她抬头，雨水和泪水混在一起，"我疯了。疯到在这等了你一个时辰，疯到——"

他上前一步，霸道地将她拉进怀里。"别说了。"

他抱得很紧，紧到她能听见他的心跳。雨声隔绝了整个世界，只剩下彼此的温度。

温柔而深情地，他低头吻了她的额头。

"我等这句话，也等了三年。"
    """
    analyzer = QualityAnalyzer()
    return analyzer.analyze(
        chapter_text=sample,
        genre="romance",
        chapter_number=20,
        chapter_title="雨夜告白",
        expected_arcs={"heroine": 0.35, "antihero": 0.30},
    )
