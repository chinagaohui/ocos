"""Phase T: MultiModalPerception 单元测试。"""

import pytest

from ocos.perception.multi_modal import (
    MultiModalPerception,
    AudioSensor,
    VisionSensor,
    ApiSensor,
    EventSensor,
)
from ocos.perception.cross_modal_fusion import (
    CrossModalFusion,
    ModalObservation,
    FusionStrategy,
)
from ocos.perception.sensor_types import SensorModality


class TestAudioSensor:
    def test_feed_and_poll(self):
        sensor = AudioSensor()
        sensor.feed(None, transcription="hello world")
        obs = sensor.poll()
        assert len(obs) == 1
        assert "[audio]" in obs[0].content

    def test_empty_poll(self):
        sensor = AudioSensor()
        obs = sensor.poll()
        assert obs == []


class TestVisionSensor:
    def test_feed_and_poll(self):
        sensor = VisionSensor()
        sensor.feed(None, description="a cat sitting on mat")
        obs = sensor.poll()
        assert len(obs) == 1
        assert "[vision]" in obs[0].content

    def test_empty_poll(self):
        sensor = VisionSensor()
        obs = sensor.poll()
        assert obs == []


class TestApiSensor:
    def test_feed_and_poll(self):
        sensor = ApiSensor()
        sensor.feed({"status": "ok", "data": [1, 2, 3]})
        obs = sensor.poll()
        assert len(obs) == 1
        assert obs[0].modality == SensorModality.API

    def test_multiple_polls(self):
        sensor = ApiSensor()
        sensor.feed({"id": 1})
        sensor.feed({"id": 2})
        sensor.feed({"id": 3})
        obs = sensor.poll()
        assert len(obs) == 3


class TestEventSensor:
    def test_emit_and_poll(self):
        sensor = EventSensor()
        sensor.emit("user_login", {"user_id": "alice"})
        obs = sensor.poll()
        assert len(obs) == 1
        assert "user_login" in obs[0].content

    def test_empty_poll(self):
        sensor = EventSensor()
        obs = sensor.poll()
        assert obs == []


class TestCrossModalFusion:
    def test_empty_fusion(self):
        fusion = CrossModalFusion()
        result = fusion.fuse([])
        assert result.fused_confidence == 0.0
        assert result.contributing_modalities == []

    def test_single_modality(self):
        fusion = CrossModalFusion()
        obs = ModalObservation(modality="text", content="hello", confidence=0.9)
        result = fusion.fuse([obs])
        assert result.fused_confidence == 0.9
        assert result.contributing_modalities == ["text"]

    def test_weighted_vote(self):
        fusion = CrossModalFusion(strategy=FusionStrategy.WEIGHTED_VOTE)
        fusion.set_weight("text", 0.8)
        fusion.set_weight("audio", 0.6)
        observations = [
            ModalObservation("text", "hello", 0.9),
            ModalObservation("audio", "hello", 0.7),
        ]
        result = fusion.fuse(observations)
        assert result.fused_confidence > 0
        assert len(result.contributing_modalities) == 2

    def test_max_confidence(self):
        fusion = CrossModalFusion(strategy=FusionStrategy.MAX_CONFIDENCE)
        observations = [
            ModalObservation("text", "hello", 0.9),
            ModalObservation("audio", "hello", 0.6),
        ]
        result = fusion.fuse(observations)
        assert result.fused_confidence == 0.9

    def test_conflict_detection(self):
        fusion = CrossModalFusion()
        observations = [
            ModalObservation("text", "hello world", 0.9),
            ModalObservation("audio", "goodbye world", 0.9),
        ]
        result = fusion.fuse(observations)
        assert result.conflicts_detected is True
        assert result.conflict_count > 0


class TestMultiModalPerception:
    def test_create(self):
        mmp = MultiModalPerception()
        assert mmp.engine is not None
        assert len(mmp.engine.sensors) >= 3  # 至少有3个基础传感器

    def test_feed_text(self):
        mmp = MultiModalPerception()
        mmp.feed_text("Hello, OCOS!")
        events = mmp.tick()
        assert len(events) > 0

    def test_feed_audio(self):
        mmp = MultiModalPerception()
        mmp.feed_audio(None, transcription="Hello")
        events = mmp.tick()
        assert any("[audio]" in str(e.observation.content) for e in events if e.observation)

    def test_feed_vision(self):
        mmp = MultiModalPerception()
        mmp.feed_vision(None, description="a cat")
        events = mmp.tick()
        assert any("[vision]" in str(e.observation.content) for e in events if e.observation)

    def test_emit_event(self):
        mmp = MultiModalPerception()
        mmp.emit_event("test_event", {"key": "value"})
        events = mmp.tick()
        assert any("test_event" in str(e.observation.content) for e in events if e.observation)

    def test_get_stats(self):
        mmp = MultiModalPerception()
        mmp.feed_text("test")
        mmp.tick()
        stats = mmp.get_stats()
        assert "total_observations" in stats
        assert "sensor_count" in stats

    def test_get_status_report(self):
        mmp = MultiModalPerception()
        report = mmp.get_status_report()
        assert "多模态感知状态报告" in report

    def test_sensor_health(self):
        mmp = MultiModalPerception()
        health = mmp.get_sensor_health()
        assert "text_sensor" in health
        # engine has registered sensors
        assert len(mmp.engine.sensors) >= 3
