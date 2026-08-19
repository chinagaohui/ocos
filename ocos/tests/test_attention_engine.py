"""
B2 Attention Engine — 完整测试套件。

覆盖：
- AttentionScore 冻结性 & 默认值
- DefaultContentAnalyzer 三指标计算
- FrequencyAnalyzer 去重衰减
- AttentionEngine 单条/批量评分
- 阈值过滤 & 排序
- 缓存 & 重置
- 权重动态调节
- 边界条件
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from ocos.kernel.abi import Observation, Goal, SCHEMA_VERSION
from ocos.runtime.attention_engine import (
    AttentionScore,
    AttentionEngine,
    DefaultContentAnalyzer,
    FrequencyAnalyzer,
)


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_observation() -> Observation:
    return Observation(
        observation_id="obs-1",
        content="系统状态正常，CPU 负载 45%",
        source="monitor",
    )


@pytest.fixture
def urgent_observation() -> Observation:
    return Observation(
        observation_id="obs-urgent",
        content="错误：内存溢出！内存使用率 99%，系统异常！",
        source="monitor",
    )


@pytest.fixture
def info_observation() -> Observation:
    return Observation(
        observation_id="obs-info",
        content="info: heartbeat 每 5 秒发送一次，状态正常",
        source="monitor",
    )


@pytest.fixture
def goal_related_observation() -> Observation:
    return Observation(
        observation_id="obs-goal",
        content="用户输入：请写一封关于项目的邮件，主题是工作总结",
        source="user",
    )


@pytest.fixture
def sample_goals() -> list[Goal]:
    return [
        Goal(goal_id="g1", description="分析用户输入并进行回复", priority=2, status="active"),
        Goal(goal_id="g2", description="监控系统资源，确保正常运行", priority=1, status="active"),
    ]


@pytest.fixture
def engine() -> AttentionEngine:
    return AttentionEngine()


@pytest.fixture
def engine_with_history(sample_observation, engine) -> AttentionEngine:
    # 添加几条历史记录让新颖性计算有意义
    obs1 = Observation(observation_id="h1", content="CPU 负载 45%，内存正常")
    obs2 = Observation(observation_id="h2", content="CPU 负载 50%，内存正常")
    engine.score(obs1)
    engine.score(obs2)
    return engine


# ══════════════════════════════════════════════════════════════════════════
# AttentionScore 冻结性测试
# ══════════════════════════════════════════════════════════════════════════

class TestAttentionScore:

    def test_is_frozen(self):
        s = AttentionScore()
        with pytest.raises(FrozenInstanceError):
            s.composite = 0.5  # type: ignore[misc]

    def test_default_values(self):
        s = AttentionScore()
        assert s.novelty == 0.0
        assert s.goal_relevance == 0.0
        assert s.urgency == 0.0
        assert s.composite == 0.0
        assert s.schema_version == SCHEMA_VERSION
        assert len(s.score_id) == 32  # uuid hex

    def test_custom_values(self):
        s = AttentionScore(
            observation_id="obs-1",
            novelty=0.8,
            goal_relevance=0.5,
            urgency=0.2,
            composite=0.55,
        )
        assert s.observation_id == "obs-1"
        assert s.novelty == 0.8
        assert s.composite == 0.55


# ══════════════════════════════════════════════════════════════════════════
# DefaultContentAnalyzer 测试
# ══════════════════════════════════════════════════════════════════════════

class TestDefaultContentAnalyzer:

    def test_novelty_first_observation(self, sample_observation):
        """第一条观察总是 1.0 新颖性。"""
        analyzer = DefaultContentAnalyzer()
        score = analyzer.score_novelty(sample_observation, history=[])
        assert score == 1.0

    def test_novelty_same_content_returns_low(self):
        """重复内容返回低新颖性。"""
        analyzer = DefaultContentAnalyzer()
        obs1 = Observation(observation_id="o1", content="相同的内容")
        obs2 = Observation(observation_id="o2", content="相同的内容")
        # 先处理 obs1
        score1 = analyzer.score_novelty(obs1, history=[])
        assert score1 == 1.0  # 首次 1.0
        # obs2 vs history=[obs1]
        score2 = analyzer.score_novelty(obs2, history=[obs1])
        assert score2 < 0.5  # 重叠导致低新颖性

    def test_novelty_different_content_returns_high(self):
        """完全不同内容返回高新颖性。"""
        analyzer = DefaultContentAnalyzer()
        obs1 = Observation(observation_id="o1", content="CPU 负载 45%")
        obs2 = Observation(observation_id="o2", content="用户输入：写一封邮件")
        score1 = analyzer.score_novelty(obs1, history=[])
        score2 = analyzer.score_novelty(obs2, history=[obs1])
        assert score2 > 0.8  # 几乎无重叠

    def test_novelty_dict_content(self):
        """dict 类型 content 正确处理。"""
        analyzer = DefaultContentAnalyzer()
        obs = Observation(
            observation_id="od1",
            content={"event": "login", "user": "alice", "ip": "10.0.0.1"},
        )
        score = analyzer.score_novelty(obs, history=[])
        assert score == 1.0

    def test_relevance_with_active_goals(self, goal_related_observation, sample_goals):
        """相关度应与目标描述匹配。"""
        analyzer = DefaultContentAnalyzer()
        # 去除 g2（系统监控），只看 g1（用户输入）
        score = analyzer.score_relevance(
            goal_related_observation,
            [sample_goals[0]],  # "分析用户输入并进行回复"
        )
        assert score > 0.0  # 有关键词重叠

    def test_relevance_with_irrelevant_observation(self, sample_observation):
        """无关观察应返回低相关度。"""
        analyzer = DefaultContentAnalyzer()
        goals = [
            Goal(goal_id="g-writing", description="写一篇关于量子物理的文章", priority=3),
        ]
        score = analyzer.score_relevance(
            sample_observation,  # "CPU 负载 45%"
            goals,
        )
        assert score < 0.3  # 低重叠

    def test_relevance_empty_goals_returns_zero(self, sample_observation):
        """无目标时返回 0。"""
        analyzer = DefaultContentAnalyzer()
        score = analyzer.score_relevance(sample_observation, goals=[])
        assert score == 0.0

    def test_relevance_high_priority_boosts_score(self):
        """高优先级目标提高相关性分数。"""
        analyzer = DefaultContentAnalyzer()
        text = "user input: help me analyze this request"
        obs = Observation(observation_id="o-p", content=text)

        low_goal = Goal(goal_id="g1", description="analyze user request", priority=0, status="active")
        high_goal = Goal(goal_id="g2", description="analyze user request", priority=3, status="active")

        low_score = analyzer.score_relevance(obs, [low_goal])
        high_score = analyzer.score_relevance(obs, [high_goal])
        assert high_score >= low_score

    def test_relevance_skips_non_active_goals(self, sample_observation):
        """非活跃目标不参与评分。"""
        analyzer = DefaultContentAnalyzer()
        goals = [
            Goal(goal_id="g1", description="CPU 负载监控", priority=2, status="completed"),
        ]
        score = analyzer.score_relevance(sample_observation, goals)
        assert score == 0.0  # completed 目标被跳过

    def test_urgency_urgent_keywords(self, urgent_observation):
        """包含紧急关键词应返回高紧急度。"""
        analyzer = DefaultContentAnalyzer()
        score = analyzer.score_urgency(urgent_observation)
        assert score > 0.5

    def test_urgency_info_keywords(self, info_observation):
        """包含 info/heartbeat 应返回低紧急度。"""
        analyzer = DefaultContentAnalyzer()
        score = analyzer.score_urgency(info_observation)
        assert score < 0.5

    def test_urgency_normal_text(self, sample_observation):
        """普通文本返回低紧急度。"""
        analyzer = DefaultContentAnalyzer()
        score = analyzer.score_urgency(sample_observation)
        assert score == 0.0

    def test_urgency_empty_content(self):
        """空内容返回 0。"""
        analyzer = DefaultContentAnalyzer()
        obs = Observation(observation_id="o-empty", content="")
        assert analyzer.score_urgency(obs) == 0.0

    def test_reset_history(self):
        """reset_history 清空记忆，新观察重新算作高新颖性。"""
        analyzer = DefaultContentAnalyzer()
        obs1 = Observation(observation_id="o1", content="重复内容")
        obs2 = Observation(observation_id="o2", content="重复内容")

        analyzer.score_novelty(obs1, history=[])
        score_before = analyzer.score_novelty(obs2, history=[obs1])
        assert score_before < 0.5  # 低新颖性

        analyzer.reset_history()
        score_after = analyzer.score_novelty(obs2, history=[])
        assert score_after == 1.0  # 重置后重新算作新颖

    def test_max_history_eviction(self):
        """超过 max_history 时旧内容被淘汰。"""
        analyzer = DefaultContentAnalyzer(max_history=3)
        for i in range(5):
            obs = Observation(observation_id=f"o{i}", content=f"unique content {i}")
            analyzer.score_novelty(obs, history=[])
        assert len(analyzer._last_observations) == 3  # 只保留最近 3 条

    def test_extract_text_from_dict_content(self):
        """dict 类型 content 正确提取文本。"""
        analyzer = DefaultContentAnalyzer()
        obs = Observation(
            observation_id="o-dict",
            content={"msg": "hello world", "count": 42, "tags": ["a", "b"]},
        )
        text = analyzer._extract_text(obs)
        assert "hello" in text.lower()


# ══════════════════════════════════════════════════════════════════════════
# FrequencyAnalyzer 测试
# ══════════════════════════════════════════════════════════════════════════

class TestFrequencyAnalyzer:

    def test_novelty_decreases_with_repetition(self):
        """重复相同内容时新颖性递减。"""
        analyzer = FrequencyAnalyzer()
        obs = Observation(observation_id="o-rep", content="重复信息")

        s1 = analyzer.score_novelty(obs, history=[])
        assert s1 == 1.0

        s2 = analyzer.score_novelty(obs, history=[])
        assert s2 == 0.5  # 1/2

        s3 = analyzer.score_novelty(obs, history=[])
        assert s3 == pytest.approx(0.333, abs=0.001)  # 1/3

    def test_different_content_always_1(self):
        """不同内容始终为 1。"""
        analyzer = FrequencyAnalyzer()
        for i in range(5):
            obs = Observation(observation_id=f"o{i}", content=f"内容{i}")
            assert analyzer.score_novelty(obs, history=[]) == 1.0

    def test_reset(self):
        """reset 后重复计数归零。"""
        analyzer = FrequencyAnalyzer()
        obs = Observation(observation_id="o1", content="相同内容")

        analyzer.score_novelty(obs, history=[])
        analyzer.score_novelty(obs, history=[])
        assert analyzer.score_novelty(obs, history=[]) < 0.4

        analyzer.reset()
        assert analyzer.score_novelty(obs, history=[]) == 1.0  # 重新计数

    def test_default_scores_are_zero(self):
        """频率分析器默认返回 0 相关性和紧急度。"""
        analyzer = FrequencyAnalyzer()
        obs = Observation(observation_id="o1", content="任何内容")
        assert analyzer.score_relevance(obs, goals=[]) == 0.0
        assert analyzer.score_urgency(obs) == 0.0


# ══════════════════════════════════════════════════════════════════════════
# AttentionEngine 集成测试
# ══════════════════════════════════════════════════════════════════════════

class TestAttentionEngine:

    def test_single_score_no_goals(self, engine, sample_observation):
        """无目标时只计算新颖性和紧急度。"""
        score = engine.score(sample_observation)
        assert score.observation_id == "obs-1"
        assert score.novelty >= 0.0
        assert score.goal_relevance == 0.0  # 无目标
        assert score.composite >= 0.0

    def test_single_score_with_goals(self, engine, sample_observation, sample_goals):
        """有目标时计算三指标。"""
        score = engine.score(sample_observation, goals=sample_goals)
        assert score.goal_relevance >= 0.0
        # composite = 0.3*n + 0.4*r + 0.3*u
        expected = (
            0.3 * score.novelty
            + 0.4 * score.goal_relevance
            + 0.3 * score.urgency
        )
        assert score.composite == pytest.approx(expected, abs=0.001)

    def test_filter_below_threshold(self, engine, sample_observation, sample_goals):
        """低于阈值的观察被过滤。"""
        # 先填充历史使新颖性变低
        for i in range(3):
            engine.score(
                Observation(observation_id=f"h{i}", content="CPU 负载 45%"),
            )

        obs_low = Observation(observation_id="low", content="CPU 负载 45%")
        obs_high = Observation(observation_id="high", content="全新重要内容 error 紧急")

        results = engine.filter(
            [obs_low, obs_high],
            goals=sample_goals,
            threshold=0.3,
        )
        assert len(results) >= 1  # 至少保留一条
        obs_ids = {obs.observation_id for obs, _ in results}
        # obs_high 应该入选
        assert "high" in obs_ids

    def test_filter_returns_sorted_by_composite(self, engine, sample_goals):
        """结果按 composite 降序排列。"""
        obs_list = [
            Observation(observation_id="f1", content="普通信息一条"),
            Observation(observation_id="f2", content="error 紧急！critical 系统崩溃！"),
            Observation(observation_id="f3", content="info: 心跳正常 status ok"),
        ]
        results = engine.filter(obs_list, goals=sample_goals, threshold=0.0)
        assert len(results) == 3
        # 确认降序
        for i in range(len(results) - 1):
            assert results[i][1].composite >= results[i + 1][1].composite

    def test_filter_max_results(self, engine, sample_goals):
        """max_results 限制返回数量。"""
        obs_list = [
            Observation(observation_id=f"m{i}", content=f"内容{i}") for i in range(10)
        ]
        results = engine.filter(obs_list, goals=sample_goals, threshold=0.0, max_results=3)
        assert len(results) == 3

    def test_get_score_from_cache(self, engine, sample_observation):
        """评分后可通过 observation_id 获取缓存的 AttentionScore。"""
        engine.score(sample_observation)
        cached = engine.get_score("obs-1")
        assert cached is not None
        assert cached.observation_id == "obs-1"

    def test_get_score_nonexistent(self, engine):
        """不存在的 observation_id 返回 None。"""
        assert engine.get_score("nonexistent") is None

    def test_reset_clears_state(self, engine, sample_observation):
        """reset 清除历史、缓存和分析器状态。"""
        engine.score(sample_observation)
        assert len(engine.history) == 1
        assert engine.get_score("obs-1") is not None

        engine.reset()
        assert len(engine.history) == 0
        assert engine.get_score("obs-1") is None

    def test_reset_novelty_recalculates(self, engine):
        """reset 后相同内容重新计算为高新颖性。"""
        obs = Observation(observation_id="r1", content="重复内容")
        score1 = engine.score(obs)
        score2 = engine.score(obs)  # 第二次，新颖性低
        assert score2.novelty < score1.novelty

        engine.reset()
        score3 = engine.score(obs)  # 重置后重新计算
        assert score3.novelty >= 0.8  # 重置后高新颖性

    def test_set_weights_updates_composite(self, engine, sample_observation, sample_goals):
        """调整权重后 composite 应反映新权重。"""
        score_default = engine.score(sample_observation, goals=sample_goals)
        engine.set_weights(novelty_weight=1.0, relevance_weight=0.0, urgency_weight=0.0)
        # 重置引擎以确保新颖性重新计算时的公平比较（但实际上不 reset 也行）
        engine.reset()
        score_high_novelty = engine.score(sample_observation, goals=sample_goals)
        # composite 现在是 novelty 的唯一权重，应更低或相等（后续相同观察，novelty 相同或略低）
        # 重新评分时第二项可能不同，所以这有模糊性。
        # 更好的测试：确认新权重下 composite == novelty
        assert score_high_novelty.composite == pytest.approx(
            score_high_novelty.novelty, abs=0.001
        )

    def test_default_weights(self):
        """默认权重配置。"""
        engine = AttentionEngine()
        assert engine._novelty_weight == 0.3
        assert engine._relevance_weight == 0.4
        assert engine._urgency_weight == 0.3

    def test_custom_weights_on_init(self):
        """自定义初始化权重。"""
        engine = AttentionEngine(
            novelty_weight=0.5,
            relevance_weight=0.3,
            urgency_weight=0.2,
        )
        assert engine._novelty_weight == 0.5

    def test_history_property(self, engine, sample_observation):
        """history 属性返回历史快照。"""
        engine.score(sample_observation)
        hist = engine.history
        assert len(hist) == 1
        assert hist[0].observation_id == "obs-1"
        # 验证是副本（修改不影响内部）
        hist.append(
            Observation(observation_id="fake", content="evil")
        )
        assert len(engine.history) == 1  # 不受外部修改影响

    def test_empty_filter_returns_empty(self, engine):
        """空输入返回空结果。"""
        assert engine.filter([], threshold=0.0) == []

    def test_score_with_context(self, engine, sample_observation, sample_goals):
        """score_with_context 从 Context 提取 goals。"""
        from ocos.runtime.context_manager import Context

        context = Context(goals=sample_goals)
        score = engine.score_with_context(sample_observation, context)
        assert score.goal_relevance >= 0.0

    def test_score_with_context_none(self, engine, sample_observation):
        """score_with_context(None) 等同无目标评分。"""
        score = engine.score_with_context(sample_observation, None)
        assert score.goal_relevance == 0.0

    def test_urgency_fires_on_urgent_observation(self, engine, urgent_observation):
        """紧急观察触发高紧急度。"""
        score = engine.score(urgent_observation)
        assert score.urgency > 0.5

    def test_urgency_low_on_info_observation(self, engine, info_observation):
        """信息性观察触发低紧急度。"""
        score = engine.score(info_observation)
        assert score.urgency < 0.5
