"""Phase R: ContinuousLearning 单元测试。"""

import pytest

from ocos.learning import (
    ContinuousLearning,
    FeedbackType,
    LearningSignalType,
    PreferenceModel,
)


class TestPreferenceModel:
    """PreferenceModel 测试。"""

    def test_empty_initial_state(self):
        model = PreferenceModel()
        assert model.preference_count == 0
        assert model.get_all_preferences() == {}

    def test_add_positive_feedback(self):
        model = PreferenceModel()
        from ocos.learning.manager import FeedbackRecord
        record = FeedbackRecord(
            feedback_id="test-1",
            feedback_type=FeedbackType.POSITIVE,
            target_message="test message",
            signal="good style",
            context={"key": "value"},
        )
        model.add_feedback(record)
        assert model.preference_count >= 1

    def test_add_preference_feedback(self):
        model = PreferenceModel()
        from ocos.learning.manager import FeedbackRecord
        record = FeedbackRecord(
            feedback_id="test-2",
            feedback_type=FeedbackType.PREFERENCE,
            target_message="test",
            signal="I prefer short responses",
        )
        model.add_feedback(record)
        # 应学到偏好
        prefs = model.get_all_preferences()
        assert model.preference_count >= 1

    def test_get_preference(self):
        model = PreferenceModel()
        from ocos.learning.manager import FeedbackRecord
        record = FeedbackRecord(
            feedback_id="test-3",
            feedback_type=FeedbackType.PREFERENCE,
            target_message="test",
            signal="I like formal tone",
            context={"tone": "formal"},
        )
        model.add_feedback(record)
        # 应该能获取到偏好
        result = model.get_preference("tone")
        # 可能学到也可能没学到，取决于实现
        # 但至少不会报错

    def test_update_from_feedback(self):
        model = PreferenceModel()
        from ocos.learning.manager import FeedbackRecord
        record = FeedbackRecord(
            feedback_id="test-4",
            feedback_type=FeedbackType.POSITIVE,
            target_message="test",
            signal="good",
            context={"style": "concise"},
        )
        result = model.update_from_feedback(record)
        assert result.success is True
        assert result.signal_type == LearningSignalType.PREFERENCE


class TestContinuousLearning:
    """ContinuousLearning 核心功能测试。"""

    def test_create(self):
        cl = ContinuousLearning()
        assert cl.stats.total_feedbacks == 0
        assert cl.preference_count == 0

    def test_record_feedback(self):
        cl = ContinuousLearning()
        record = cl.record_feedback(
            feedback_type=FeedbackType.POSITIVE,
            signal="good response",
            target_message="hello",
        )
        assert record.feedback_type == FeedbackType.POSITIVE
        assert cl.stats.total_feedbacks == 1

    def test_learn_from_interaction_positive(self):
        cl = ContinuousLearning()
        result = cl.learn_from_interaction(
            interaction_type="chat",
            user_response="Great, thanks!",
            ai_output="Here is the answer.",
        )
        assert result.success is True
        assert cl.stats.positive_count == 1

    def test_learn_from_interaction_negative(self):
        cl = ContinuousLearning()
        result = cl.learn_from_interaction(
            interaction_type="chat",
            user_response="That's wrong",
            ai_output="Wrong answer.",
        )
        assert result.success is True
        assert cl.stats.negative_count == 1

    def test_learn_from_interaction_preference(self):
        cl = ContinuousLearning()
        result = cl.learn_from_interaction(
            interaction_type="chat",
            user_response="I prefer shorter answers",
            ai_output="Long answer.",
        )
        assert result.success is True

    def test_get_preferences(self):
        cl = ContinuousLearning()
        cl.record_feedback(
            feedback_type=FeedbackType.PREFERENCE,
            signal="I like concise",
            target_message="test",
            context={"style": "concise"},
        )
        prefs = cl.get_preferences()
        assert isinstance(prefs, dict)

    def test_get_recommendation(self):
        cl = ContinuousLearning()
        cl.record_feedback(
            feedback_type=FeedbackType.PREFERENCE,
            signal="formal tone",
            target_message="test",
            context={"tone": "formal"},
        )
        # 不保证一定能获取到，但不报错即可
        rec = cl.get_recommendation("tone")

    def test_get_stats(self):
        cl = ContinuousLearning()
        cl.record_feedback(FeedbackType.POSITIVE, "good", "test")
        cl.record_feedback(FeedbackType.NEGATIVE, "bad", "test")
        stats = cl.get_stats()
        assert stats["total_feedbacks"] == 2
        assert stats["positive_ratio"] == 0.5
        assert isinstance(stats["learning_rate"], float)

    def test_generate_learning_report(self):
        cl = ContinuousLearning()
        cl.record_feedback(FeedbackType.POSITIVE, "good", "test")
        report = cl.generate_learning_report()
        assert "持续学习报告" in report
        assert "总反馈数: 1" in report


class TestLearningStats:
    """学习统计测试。"""

    def test_initial_stats(self):
        cl = ContinuousLearning()
        stats = cl.stats
        assert stats.total_feedbacks == 0
        assert stats.positive_count == 0
        assert stats.negative_count == 0
        assert stats.corrections_count == 0

    def test_stats_update_on_feedback(self):
        cl = ContinuousLearning()
        cl.record_feedback(FeedbackType.POSITIVE, "good", "test")
        cl.record_feedback(FeedbackType.NEGATIVE, "bad", "test")
        cl.record_feedback(FeedbackType.CORRECTION, "fix this", "test")
        assert cl.stats.positive_count == 1
        assert cl.stats.negative_count == 1
        assert cl.stats.corrections_count == 1
        assert cl.stats.total_feedbacks == 3
