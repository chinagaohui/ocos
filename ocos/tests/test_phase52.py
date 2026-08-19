"""Phase 52: Perception System — Tests.

验证:
    PS52-01: Perception ≠ Truth — Observation 是假设
    PS52-02: Sensor Isolation — 传感器崩溃不影响其他
    PS52-03: Confidence Required — 每条观察有置信度
    PS52-04: Validation Before Belief — 验证门控
    Full pipeline: Sensor → Extract → Validate → Event
"""

import tempfile, time
from pathlib import Path
import pytest

from ocos.perception.sensor_types import (
    SensorModality, SensorStatus, SensorConfig, SensorHealth,
    ObservationType, Observation, SemanticFragment,
    PerceptionEventType, PerceptionEvent,
    ValidationVerdict, ValidationResult,
)
from ocos.perception.text_sensor import TextSensor
from ocos.perception.file_sensor import FileSensor
from ocos.perception.environment_sensor import EnvironmentSensor
from ocos.perception.perception_engine import PerceptionEngine
from ocos.perception.semantic_extractor import SemanticExtractor, ObservationBuilder
from ocos.perception.perception_validator import PerceptionValidator


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Types
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypes:
    def test_observation_ps52_01(self):
        """PS52-01: Observation 是假设，不是事实。"""
        obs = Observation(
            modality=SensorModality.TEXT,
            content="用户说要做股票分析",
            confidence=0.7,
        )
        assert obs.modality == SensorModality.TEXT
        assert obs.confidence == 0.7
        assert obs.is_reliable

    def test_observation_low_confidence(self):
        """低置信度不可靠。"""
        obs = Observation(content="模糊输入", confidence=0.2)
        assert not obs.is_reliable

    def test_observation_timestamp(self):
        obs = Observation(content="test")
        assert obs.timestamp > 0
        assert obs.age_seconds < 1

    def test_sensor_config(self):
        cfg = SensorConfig(
            sensor_name="test",
            modalities=[SensorModality.TEXT, SensorModality.FILE],
        )
        assert cfg.supports(SensorModality.TEXT)
        assert not cfg.supports(SensorModality.API)

    def test_semantic_fragment(self):
        sf = SemanticFragment(
            text="开发股票分析系统",
            intent="develop",
            domain="software_engineering",
            entities=["股票", "分析"],
            sentiment="positive",
            priority_hint="normal",
        )
        assert sf.intent == "develop"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TextSensor
# ═══════════════════════════════════════════════════════════════════════════════


class TestTextSensor:
    def test_feed_and_poll(self):
        sensor = TextSensor()
        sensor.feed("你好")
        sensor.feed("需要开发股票系统")
        sensor.feed("   ")  # blank → skipped

        observations = sensor.poll()
        assert len(observations) == 2
        assert observations[0].content == "你好"
        assert observations[1].content == "需要开发股票系统"

    def test_confidence_estimation(self):
        sensor = TextSensor()
        sensor.feed("短")
        sensor.feed("中等长度的文本输入")
        sensor.feed("很长的文本" * 20)

        obs = sensor.poll()
        assert len(obs) == 3
        assert obs[0].confidence < 0.5   # 太短
        assert obs[1].confidence > 0.7   # 正常
        assert obs[2].confidence > 0.9   # 长

    def test_empty_poll(self):
        sensor = TextSensor()
        assert sensor.poll() == []
        assert not sensor.has_pending()

    def test_has_pending(self):
        sensor = TextSensor()
        sensor.feed("test")
        assert sensor.has_pending()

    def test_feed_batch(self):
        sensor = TextSensor()
        sensor.feed_batch(["a", "b", "c"])
        obs = sensor.poll()
        assert len(obs) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 3. FileSensor
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileSensor:
    def test_watch_and_detect_creation(self):
        sensor = FileSensor()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            path = f.name

        sensor.watch(path)
        observations = sensor.poll()
        # Initially no change
        assert len(observations) == 0

        # Modify the file
        with open(path, "a") as f2:
            f2.write(" world")

        observations2 = sensor.poll()
        assert len(observations2) >= 1
        assert observations2[0].content["change"] == "modified"

        Path(path).unlink()

    def test_file_deletion_detection(self):
        sensor = FileSensor()
        with tempfile.NamedTemporaryFile(delete=True, suffix=".txt") as f:
            path = f.name
        sensor.watch(path)  # file doesn't exist but was watched

        # Create it after watching
        with open(path, "w") as f2:
            f2.write("data")
        sensor.watch(path)

        observations = sensor.poll()
        assert len(observations) == 0  # first poll is baseline

        Path(path).unlink()
        observations2 = sensor.poll()
        assert len(observations2) >= 1
        assert observations2[0].content["change"] == "deleted"

    def test_disable_poll(self):
        sensor = FileSensor()
        sensor.config.enabled = False
        assert sensor.poll() == []


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EnvironmentSensor
# ═══════════════════════════════════════════════════════════════════════════════


# 2026-08-17 健康化：psutil 缺失时环境传感器降级——依赖真实采集的测试跳过。
try:
    import psutil  # noqa: F401
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


class TestEnvironmentSensor:
    def test_basic_poll(self):
        sensor = EnvironmentSensor()
        observations = sensor.poll()
        # Should produce at least no errors
        assert isinstance(observations, list)

    @pytest.mark.skipif(not _PSUTIL_OK, reason="psutil 缺失（环境传感器降级）")
    def test_memory_anomaly_thresholds(self):
        """设置极低阈值触发告警。"""
        sensor = EnvironmentSensor()
        sensor._memory_high_mb = 0.001  # 几乎立即触发
        sensor._memory_critical_mb = 0.001

        observations = sensor.poll()
        # 至少有一个内存告警
        assert any(o.type == ObservationType.ANOMALY for o in observations)

    @pytest.mark.skipif(not _PSUTIL_OK, reason="psutil 缺失（环境传感器降级）")
    def test_snapshot_available(self):
        sensor = EnvironmentSensor()
        sensor.poll()
        assert sensor.last_snapshot is not None
        assert sensor.last_snapshot.memory_used_mb > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SemanticExtractor
# ═══════════════════════════════════════════════════════════════════════════════


class TestSemanticExtractor:
    def test_intent_detection_develop(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content="帮我开发一个股票分析系统",
            confidence=0.9,
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert sf.intent == "develop"

    def test_intent_detection_fix(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content="修复数据库连接问题",
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert sf.intent == "fix"

    def test_domain_detection(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content="检查系统架构中的API设计和缓存策略",
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert sf.domain == "software_engineering"

    def test_entity_extraction(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content='使用 "Redis" 作为缓存，参考 `cache_config.py`',
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert "Redis" in sf.entities
        assert "cache_config.py" in sf.entities

    def test_sentiment(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content="系统部署成功了，非常好",
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert sf.sentiment == "positive"

    def test_urgent_priority(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.TEXT,
            content="紧急：数据库已经宕机，立即修复",
        )
        sf = extractor.extract(obs)
        assert sf is not None
        assert sf.priority_hint == "urgent"

    def test_non_text_skipped(self):
        extractor = SemanticExtractor()
        obs = Observation(
            modality=SensorModality.FILE,
            content="file change",
        )
        sf = extractor.extract(obs)
        assert sf is None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PerceptionValidator
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerceptionValidator:
    def test_accept_high_confidence(self):
        validator = PerceptionValidator()
        obs = Observation(content="可信输入", confidence=0.9)
        result = validator.validate(obs)
        assert result.verdict == ValidationVerdict.ACCEPTED

    def test_reject_low_confidence_ps52_04(self):
        """PS52-04: 低置信度被拒绝。"""
        validator = PerceptionValidator()
        obs = Observation(content="不可靠输入", confidence=0.1)
        result = validator.validate(obs)
        assert result.verdict == ValidationVerdict.REJECTED

    def test_needs_confirmation(self):
        validator = PerceptionValidator()
        obs = Observation(content="中间", confidence=0.5)
        result = validator.validate(obs)
        assert result.verdict == ValidationVerdict.NEEDS_CONFIRMATION

    def test_duplicate_rejected(self):
        validator = PerceptionValidator()
        obs = Observation(content="重复", confidence=0.9)
        validator.validate(obs)
        result2 = validator.validate(obs)
        assert result2.verdict == ValidationVerdict.REJECTED

    def test_source_reputation(self):
        validator = PerceptionValidator()
        validator.set_source_reputation("untrusted", 0.3)
        obs = Observation(content="test", confidence=0.8, source_sensor="untrusted")
        result = validator.validate(obs)
        # effective = 0.8 * 0.3 = 0.24 < 0.3 → rejected
        assert result.verdict == ValidationVerdict.REJECTED


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ObservationBuilder
# ═══════════════════════════════════════════════════════════════════════════════


class TestObservationBuilder:
    def test_from_raw(self):
        builder = ObservationBuilder()
        obs = builder.from_raw("hello", SensorModality.TEXT)
        assert obs.content == "hello"
        assert obs.type == ObservationType.RAW

    def test_from_anomaly(self):
        builder = ObservationBuilder()
        obs = builder.from_anomaly("memory_spike", {"delta_mb": 200})
        assert obs.type == ObservationType.ANOMALY

    def test_merge(self):
        builder = ObservationBuilder()
        o1 = Observation(content="a", confidence=0.9)
        o2 = Observation(content="b", confidence=0.7)
        merged = builder.merge([o1, o2])
        assert merged.type == ObservationType.STRUCTURED
        assert merged.confidence == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PerceptionEngine
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerceptionEngine:
    def test_full_pipeline(self):
        """完整管线: Sensor → Extract → Validate → Events。"""
        engine = PerceptionEngine()
        text_sensor = TextSensor()
        engine.register_sensor(text_sensor)

        # 设置语义提取和验证
        engine.semantic_extractor = SemanticExtractor().extract
        engine.validator = PerceptionValidator().validate

        # 注入输入
        text_sensor.feed("开发股票分析系统")
        text_sensor.feed("修复数据库缓存 bug")

        # 执行 tick
        events = engine.tick()
        assert len(events) >= 2
        assert engine.total_observations >= 2
        assert engine.tick_count == 1

    def test_empty_tick(self):
        engine = PerceptionEngine()
        events = engine.tick()
        assert events == []

    def test_sensor_isolation_ps52_02(self):
        """PS52-02: 一个传感器崩溃不影响其他。"""
        engine = PerceptionEngine()

        class BrokenSensor:
            config = SensorConfig(sensor_name="broken")
            def poll(self):
                raise RuntimeError("boom")
            def get_health(self):
                return SensorHealth(sensor_name="broken", status=SensorStatus.ERROR)

        good_sensor = TextSensor()
        good_sensor.feed("正常输入")
        engine.register_sensor(BrokenSensor())
        engine.register_sensor(good_sensor)

        events = engine.tick()
        # 正常传感器的输出仍在
        assert len(events) >= 1
        assert engine.total_observations >= 1

    def test_event_callback(self):
        captured = []
        engine = PerceptionEngine()
        engine.event_callback = lambda e: captured.append(e)
        sensor = TextSensor()
        engine.register_sensor(sensor)
        sensor.feed("test")

        engine.tick()
        assert len(captured) >= 1
        assert captured[0].type == PerceptionEventType.OBSERVATION_READY

    def test_sensor_health(self):
        engine = PerceptionEngine()
        sensor = TextSensor()
        engine.register_sensor(sensor)
        sensor.feed("test")
        engine.tick()

        health_report = engine.sensor_health()
        assert "text_sensor" in health_report
        assert health_report["text_sensor"]["status"] == "active"

    def test_get_set_state(self):
        engine = PerceptionEngine()
        sensor = TextSensor()
        engine.register_sensor(sensor)
        sensor.feed("test")
        engine.tick()

        state = engine.get_state()
        assert state["total_observations"] >= 1

        e2 = PerceptionEngine()
        e2.set_state(state)
        assert e2.total_observations == state["total_observations"]


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Integration: PS52-04 full flow with validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerceptionValidationFlow:
    def test_perception_not_truth_ps52_01_04(self):
        """PS52-01+04: 感知产生 Observation，验证决定是否进入世界。

        模拟: 传感器看到东西 → 验证器判断可信度 → 低置信度被拒绝。
        """
        engine = PerceptionEngine()
        sensor = TextSensor()
        engine.register_sensor(sensor)

        validator = PerceptionValidator()
        validator.min_confidence = 0.6
        # Track rejected observations via validator itself
        engine.validator = validator.validate

        # 低可信输入
        sensor.feed("短")  # confidence ~0.3 from TextSensor
        events = engine.tick()

        # Verify: engine processed the observation but validator rejected it
        assert engine.total_observations == 1
        stats = validator.get_stats()
        # The text_sensor source should have rejected count
        assert stats["text_sensor"]["rejected"] >= 1

    def test_high_confidence_enters_world(self):
        """高置信度观察进入世界模型。"""
        validator = PerceptionValidator()
        obs = Observation(
            content="这条信息来自可信来源",
            confidence=0.95,
            source_sensor="trusted",
        )
        result = validator.validate(obs)
        assert result.verdict == ValidationVerdict.ACCEPTED
