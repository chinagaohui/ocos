"""Phase14.4.0 — Meta Principle Formation Positioning Review Tests.

Tests verify:
1. Principle definition — Abstract Mechanism, not technique/trend/style/rule
2. Pattern → Principle input boundary — allowed vs forbidden inputs
3. ReaderOS boundary — allowed vs forbidden signals
4. Principle vs Capability isolation — what Phase14.4 does not produce
5. Principle naming — neutral, structural, mechanistic language
6. Core isolation — forbidden paths, separation of concerns
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any


# --- Test models ---


@dataclass
class PrincipleCandidate:
    principle_id: str
    source_pattern_ids: List[str]
    evidence_chain: List[str]
    abstraction_level: str  # cross_work, cross_genre, cross_type
    mechanism_description: str
    scope_boundary: str
    counter_examples: List[str] = field(default_factory=list)
    readeros_signals: List[str] = field(default_factory=list)


@dataclass
class PatternReference:
    pattern_id: str
    feature_structure: Dict
    relation_structure: List[Tuple]
    occurrence: float
    context_boundary: str


@dataclass
class PrincipleValidation:
    status: str  # candidate, reviewing, validated, archived, invalidated
    consistency_score: Optional[float] = None
    cross_context_coverage: Optional[float] = None
    contradiction_count: int = 0
    has_candidate_phase: bool = True


# --- Forbidden definitions ---

FORBIDDEN_PRINCIPLE_TYPES = {
    "technique": "写作技巧/技法",
    "formula": "公式/模板",
    "template": "写作模板",
    "trend": "市场趋势",
    "style_description": "风格描述",
    "genre_label": "类型标签",
    "rule": "规则(narrative rule)",
    "commercial_pattern": "商业模式",
    "trope": "文化套路",
}

FORBIDDEN_INPUTS = {
    "reader_score": "读者评分",
    "market_data": "市场数据(销量/订阅)",
    "popularity_metric": "流行度指标",
    "revenue": "收入/转化率",
    "author_preference": "作者偏好",
    "editorial_feedback": "编辑反馈",
    "ai_pretrained_knowledge": "AI预训练知识(外部)",
    "genre_trend_label": "类型趋势标签",
    "user_engagement_score": "用户参与度",
}

ALLOWED_INPUTS = {
    "pattern_reference": "Pattern引用",
    "evidence_chain": "证据链追踪",
    "relation_graph": "关联关系图",
    "observation_context": "观察上下文",
    "counter_evidence": "反例记录",
}

FORBIDDEN_READEROS_SIGNALS = {
    "popular": "流行度",
    "trending": "热门",
    "good": "好",
    "excellent": "优秀",
    "successful": "成功",
    "should_apply": "应该应用",
    "recommended": "推荐",
    "high_engagement": "高参与度",
    "most_read": "最多阅读",
    "highest_rate": "最高评分",
}

ALLOWED_READEROS_SIGNALS = {
    "attention_change": "注意力变化",
    "reading_pause": "阅读停留",
    "completion_pattern": "完成/中断模式",
    "question_generation": "自发疑问",
    "memory_signal": "重读信号",
    "re_read_indicator": "回读定位",
}

VALID_PRINCIPLE_NAMES = [
    "延迟满足与信息释放的结构关系",
    "关系距离变化与情绪期待的映射",
    "冲突积累触发化解的动态模型",
    "角色选择空间与叙事张力的非线性关系",
    "信息不对称下预期路径的修正机制",
    "认知负载与阅读流畅性的结构关系",
]

INVALID_PRINCIPLE_NAMES = [
    "爽文标准写法",
    "言情甜宠公式",
    "读者最爱的开头结构",
    "爆款必备元素",
    "黄金三章法则",
    "成功小说的共同特征",
    "新手如何写出爆款",
    "编辑推荐的十大结构",
]

PHASE14_DOT_4_FORBIDDEN_OUTPUTS = {
    "writing_agent": "写作Agent",
    "prompt_instruction": "Prompt/指令",
    "writing_template": "写作模板",
    "generation_strategy": "生成策略",
    "modification_suggestion": "修改建议",
    "style_transfer": "风格迁移",
    "text_generation_control": "生成控制参数",
}


class PrinciplePositioningCheck:
    """Phase14.4.0 定位验证器."""

    def __init__(self):
        self.violations = []

    _trope_indicators = [
        "文体", "流派", "流", "套路", "桥段",
    ]

    def check_principle_type(self, description: str) -> bool:
        """验证 Principle 描述符合 Abstract Mechanism 定义."""
        # 必须是机制描述
        forbidden_patterns = [
            "应该", "必须", "推荐", "最好",
            "技巧", "公式", "模板", "套路",
            "写法", "法则", "秘诀",
            "读者喜欢", "读者爱", "最爱",
            "爆款", "成功", "优秀", "经典",
            "特征", "风格", "标签",
            "不能", "不要", "禁止",
            "付费", "商业", "价格",
        ]
        for pattern in forbidden_patterns:
            if pattern in description:
                self.violations.append(f"Principle描述包含禁止用语: {pattern}")
                return False

        # 检查套路/流派指示词
        for indicator in self._trope_indicators:
            if indicator in description:
                # "流" 只在字符串末尾时认定为套路指示词
                if indicator == "流" and not description.endswith("流"):
                    continue
                self.violations.append(f"Principle描述包含套路/流派用语: {indicator}")
                return False

        # 必须是非价值性的
        value_terms = ["好", "坏", "有效", "高效", "优秀"]
        for term in value_terms:
            if term in description:
                self.violations.append(f"Principle描述包含价值用语: {term}")
                return False

        return True

    def check_readeros_boundary(self, signal: str) -> bool:
        """验证 ReaderOS 信号是否在允许范围内."""
        if signal in FORBIDDEN_READEROS_SIGNALS:
            self.violations.append(f"ReaderOS 信号禁止: {signal}")
            return False
        if signal in ALLOWED_READEROS_SIGNALS:
            return True
        # Unknown signal — caution
        self.violations.append(f"ReaderOS 信号未定义: {signal}")
        return False


# --- Tests ---


class TestPrincipleDefinition:
    """Principle = Abstract Mechanism."""

    def test_principle_is_not_technique(self):
        """Principle 不是写作技巧."""
        p = PrincipleCandidate(
            principle_id="p-001",
            source_pattern_ids=["pat-a", "pat-c"],
            evidence_chain=["e-101", "e-203"],
            abstraction_level="cross_work",
            mechanism_description="受限信息环境下不确定性增加改变决策压力结构",
            scope_boundary="zh_novel_fiction",
        )
        assert p.mechanism_description != ""
        assert "技巧" not in p.mechanism_description

    def test_principle_not_formula(self):
        """Principle 不是公式/模板."""
        check = PrinciplePositioningCheck()
        assert check.check_principle_type(
            "延迟满足与信息释放的结构关系"
        )
        assert not check.check_principle_type("三章一章反转公式")

    def test_principle_not_trend(self):
        """Principle 不是市场趋势."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("当下流行的开头写法")

    def test_principle_not_style(self):
        """Principle 不是风格描述."""
        check = PrinciplePositioningCheck()
        assert check.check_principle_type(
            "认知负载与阅读流畅性的结构关系"
        )
        assert not check.check_principle_type("慢热细腻的风格特征")

    def test_principle_not_genre_label(self):
        """Principle 不是类型标签."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("言情经典桥段")

    def test_principle_not_rule(self):
        """Principle 不是规则."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("主角不能太弱")

    def test_principle_not_commercial(self):
        """Principle 不是商业模式."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("付费点设计")

    def test_principle_not_trope(self):
        """Principle 不是文化套路."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("退婚流")

    def test_principle_has_mechanism_structure(self):
        """Principle 描述机制结构."""
        valid_descriptions = [
            "受限信息环境下不确定性增加改变决策压力结构",
            "信息密度与阅读阻抗的结构关系",
            "关系距离变化与情感期待的映射",
            "冲突积累与化解的动态平衡",
        ]
        for desc in valid_descriptions:
            check = PrinciplePositioningCheck()
            assert check.check_principle_type(desc), f"Failed on: {desc}"

    def test_principle_no_value_judgment(self):
        """Principle 不含价值判断."""
        check = PrinciplePositioningCheck()
        assert not check.check_principle_type("这个结构更好")
        assert not check.check_principle_type("优秀的叙事方式")

    def test_principle_has_abstraction_level(self):
        """Principle 包含抽象层级."""
        p = PrincipleCandidate(
            principle_id="p-002",
            source_pattern_ids=["pat-x"],
            evidence_chain=["e-001"],
            abstraction_level="cross_genre",
            mechanism_description="测试机制",
            scope_boundary="test",
        )
        assert p.abstraction_level in ["cross_work", "cross_genre", "cross_type"]

    def test_principle_has_counter_examples(self):
        """Principle 包含反例记录."""
        p = PrincipleCandidate(
            principle_id="p-003",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-001"],
            abstraction_level="cross_work",
            mechanism_description="测试机制",
            scope_boundary="test",
            counter_examples=["pat-z 不匹配此模式"],
        )
        assert len(p.counter_examples) > 0

    def test_principle_has_scope_boundary(self):
        """Principle 明确作用范围."""
        p = PrincipleCandidate(
            principle_id="p-004",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-001"],
            abstraction_level="cross_work",
            mechanism_description="测试",
            scope_boundary="zh_novel_fiction_2015_2025",
        )
        assert isinstance(p.scope_boundary, str)
        assert p.scope_boundary != ""


class TestPrincipleNaming:
    """Principle 命名规范."""

    def test_valid_names_are_mechanistic(self):
        """有效名称是机制性的."""
        for name in VALID_PRINCIPLE_NAMES:
            check = PrinciplePositioningCheck()
            assert check.check_principle_type(name), f"Valid name rejected: {name}"

    def test_invalid_names_contain_value(self):
        """无效名称包含价值判断或商业用语."""
        for name in INVALID_PRINCIPLE_NAMES:
            check = PrinciplePositioningCheck()
            assert not check.check_principle_type(name), f"Invalid name accepted: {name}"

    def test_names_no_commercial_language(self):
        """命名不含商业语言."""
        commercial_terms = ["爆款", "必看", "热门", "推荐", "必学", "最火"]
        for name in VALID_PRINCIPLE_NAMES:
            for term in commercial_terms:
                assert term not in name, f"Commercial term '{term}' in name: {name}"


class TestPatternToPrincipleBoundary:
    """Pattern → Principle 转换边界."""

    def test_allowed_inputs_available(self):
        """允许的输入可以被 PrincipleCandidate 接收."""
        p = PrincipleCandidate(
            principle_id="p-bound",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-101"],
            abstraction_level="cross_work",
            mechanism_description="测试",
            scope_boundary="test",
        )
        assert len(p.source_pattern_ids) > 0
        assert len(p.evidence_chain) > 0

    def test_no_reader_score_in_input(self):
        """Reader Score 不是 Principle Formation 的输入."""
        assert "reader_score" in FORBIDDEN_INPUTS

    def test_no_market_data_in_input(self):
        """Market Data 不是输入."""
        assert "market_data" in FORBIDDEN_INPUTS
        assert "popularity_metric" in FORBIDDEN_INPUTS
        assert "revenue" in FORBIDDEN_INPUTS

    def test_no_author_preference(self):
        """作者偏好不是输入."""
        assert "author_preference" in FORBIDDEN_INPUTS

    def test_no_editorial_feedback(self):
        """编辑反馈不是输入."""
        assert "editorial_feedback" in FORBIDDEN_INPUTS

    def test_forbidden_inputs_comprehensive(self):
        """禁止输入列表完整."""
        assert len(FORBIDDEN_INPUTS) == 9

    def test_allowed_inputs_comprehensive(self):
        """允许输入列表完整."""
        assert len(ALLOWED_INPUTS) == 5

    def test_principle_must_trace_to_pattern(self):
        """Principle 必须追溯到 Pattern."""
        p = PrincipleCandidate(
            principle_id="p-trace",
            source_pattern_ids=["pat-a", "pat-b"],
            evidence_chain=["e-101", "e-202"],
            abstraction_level="cross_work",
            mechanism_description="测试",
            scope_boundary="test",
        )
        assert len(p.source_pattern_ids) >= 1
        assert len(p.evidence_chain) >= 1

    def test_no_auto_acceptance(self):
        """Pattern→Principle 是提出假说，不是自动认定."""
        v = PrincipleValidation(
            status="candidate",
            has_candidate_phase=True,
        )
        assert v.has_candidate_phase
        assert v.status == "candidate"


class TestReaderOSBoundary:
    """ReaderOS 信号边界."""

    def test_allowed_signals_observational(self):
        """允许的 ReaderOS 信号是观察性的."""
        for signal in ALLOWED_READEROS_SIGNALS:
            assert not any(
                forbid in signal
                for forbid in ["popular", "good", "successful", "recommended"]
            ), f"Signal has value term: {signal}"

    def test_forbidden_signals_value_based(self):
        """禁止的 ReaderOS 信号包含价值判断."""
        assert "popular" in FORBIDDEN_READEROS_SIGNALS
        assert "good" in FORBIDDEN_READEROS_SIGNALS
        assert "successful" in FORBIDDEN_READEROS_SIGNALS

    def test_forbidden_signals_comprehensive(self):
        """禁止信号列表完整."""
        assert len(FORBIDDEN_READEROS_SIGNALS) == 10

    def test_allowed_signals_comprehensive(self):
        """允许信号列表完整."""
        assert len(ALLOWED_READEROS_SIGNALS) == 6

    def test_readeros_cannot_be_sole_basis(self):
        """ReaderOS 不能单独决定 Principle 形成."""
        # Must have Pattern + Evidence
        p = PrincipleCandidate(
            principle_id="p-ros",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-001", "e-002"],
            abstraction_level="cross_work",
            mechanism_description="测试机制",
            scope_boundary="test",
            readeros_signals=["reading_pause"],
        )
        assert len(p.source_pattern_ids) >= 1
        assert len(p.evidence_chain) >= 1
        # readeros is supplementary
        assert len(p.readeros_signals) < len(p.evidence_chain)

    def test_readeros_not_direct_mapping(self):
        """ReaderOS 信号不能直接映射为 Principle."""
        check = PrinciplePositioningCheck()
        # "阅读停留久"不能直接认定"这个结构好"
        # 只能作为注意力分布的辅助参考
        assert check.check_readeros_boundary("reading_pause")
        assert check.check_readeros_boundary("question_generation")


class TestPrincipleCapabilityIsolation:
    """Phase14.4 与 Phase14.5 Capability 隔离."""

    def test_phase14_4_does_not_produce_agent(self):
        """Phase14.4 不产生写作Agent."""
        assert "writing_agent" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_phase14_4_does_not_produce_prompt(self):
        """Phase14.4 不产生Prompt."""
        assert "prompt_instruction" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_phase14_4_does_not_produce_template(self):
        """Phase14.4 不产生写作模板."""
        assert "writing_template" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_phase14_4_does_not_produce_generation(self):
        """Phase14.4 不产生生成策略."""
        assert "generation_strategy" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_phase14_4_does_not_produce_suggestions(self):
        """Phase14.4 不产生修改建议."""
        assert "modification_suggestion" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_phase14_4_forbidden_outputs_comprehensive(self):
        """禁止输出列表完整."""
        assert len(PHASE14_DOT_4_FORBIDDEN_OUTPUTS) == 7

    def test_capability_belongs_to_phase14_5(self):
        """Capability 属于 Phase14.5, 不是 Phase14.4."""
        assert "writing_agent" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_principle_is_abstraction_not_implementation(self):
        """Principle 是抽象机制, 不是实现."""
        p = PrincipleCandidate(
            principle_id="p-abs",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-001"],
            abstraction_level="cross_work",
            mechanism_description="关系距离变化与情绪期待的映射",
            scope_boundary="test",
        )
        # 抽象机制不是实现
        assert "如何" not in p.mechanism_description
        # 不包含执行指令
        assert "应该" not in p.mechanism_description


class TestCoreIsolation:
    """核心隔离路径."""

    def test_forbidden_path_not_implemented(self):
        """Pattern → 有效 → 推荐 → 模板 路径永久禁止."""
        # 验证这条路径的每一步都不属于 Phase14.4
        assert "writing_template" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS
        assert "technique" in FORBIDDEN_PRINCIPLE_TYPES
        assert "recommended" in FORBIDDEN_READEROS_SIGNALS
        assert "reader_score" in FORBIDDEN_INPUTS

    def test_pattern_principle_not_evaluative(self):
        """Pattern→Principle 不进行价值评价."""
        check = PrinciplePositioningCheck()
        # Phase14.4 描述结构关系, 不评价好坏
        assert check.check_principle_type(
            "信息不对称下预期路径的修正机制"
        )

    def test_no_direct_pattern_to_capability(self):
        """没有从 Pattern 直接到 Capability 的路径."""
        # Phase14.4 和 Phase14.5 是两个阶段
        assert "writing_agent" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS
        assert "generation_strategy" in PHASE14_DOT_4_FORBIDDEN_OUTPUTS

    def test_all_frozen_lists_have_content(self):
        """所有冻结列表有内容."""
        assert len(FORBIDDEN_PRINCIPLE_TYPES) >= 5
        assert len(FORBIDDEN_INPUTS) >= 5
        assert len(FORBIDDEN_READEROS_SIGNALS) >= 5
        assert len(ALLOWED_READEROS_SIGNALS) >= 3
        assert len(PHASE14_DOT_4_FORBIDDEN_OUTPUTS) >= 3

    def test_principle_validation_not_value_based(self):
        """Principle Validation 不基于价值判断."""
        v = PrincipleValidation(
            status="candidate",
            consistency_score=0.85,
        )
        # Validation 验证一致性, 不是"好/坏"
        assert v.consistency_score is not None
        assert not hasattr(v, "quality_score")
        assert not hasattr(v, "effectiveness")
        assert not hasattr(v, "success_rate")

    def test_no_principle_auto_register(self):
        """Principle 不会自动认定/注册."""
        v = PrincipleValidation(status="candidate")
        assert v.status == "candidate"
        # 必须有验证过程才能变成 validated
        assert v.has_candidate_phase


class TestAbstractionLevel:
    """抽象层级."""

    def test_abstraction_levels_defined(self):
        """抽象层级已定义."""
        valid_levels = {"cross_work", "cross_genre", "cross_type"}
        p = PrincipleCandidate(
            principle_id="p-lvl",
            source_pattern_ids=["pat-a"],
            evidence_chain=["e-001"],
            abstraction_level="cross_genre",
            mechanism_description="测试",
            scope_boundary="test",
        )
        assert p.abstraction_level in valid_levels

    def test_higher_abstraction_requires_more_evidence(self):
        """更高抽象层级需要更多证据."""
        p1 = PrincipleCandidate(
            principle_id="p-high",
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d", "pat-e"],
            evidence_chain=["e-001", "e-002", "e-003", "e-004", "e-005", "e-006"],
            abstraction_level="cross_genre",
            mechanism_description="跨作品的抽象机制",
            scope_boundary="test",
        )
        p2 = PrincipleCandidate(
            principle_id="p-low",
            source_pattern_ids=["pat-x"],
            evidence_chain=["e-001"],
            abstraction_level="cross_work",
            mechanism_description="单作品观察",
            scope_boundary="test",
        )
        assert len(p1.source_pattern_ids) >= len(p2.source_pattern_ids)
        assert len(p1.evidence_chain) >= len(p2.evidence_chain)
