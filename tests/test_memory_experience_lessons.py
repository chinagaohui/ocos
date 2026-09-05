"""Tests for ocos.memory.experience.lessons - 经验课程。"""
import pytest


class TestExperienceLessons:
    def test_import_episode(self):
        from ocos.memory.experience.lessons import Episode
        assert Episode is not None

    def test_import_lessons_synthesizer(self):
        from ocos.memory.experience.lessons import LessonsSynthesizer
        assert LessonsSynthesizer is not None

    def test_import_lessons_learned(self):
        from ocos.memory.experience.lessons import LessonsLearned
        assert LessonsLearned is not None

    def test_import_episode_status(self):
        from ocos.memory.experience.lessons import EpisodeStatus
        assert EpisodeStatus is not None
