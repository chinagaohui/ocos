"""Tests for ocos.perception.pipeline - Perception pipeline."""
import pytest
from unittest.mock import MagicMock


class TestPerceptionPipeline:
    def test_import(self):
        from ocos.perception.pipeline import PerceptionPipeline
        assert PerceptionPipeline is not None

    def test_create(self):
        from ocos.perception.pipeline import PerceptionPipeline
        pipeline = PerceptionPipeline()
        assert pipeline is not None

    def test_register_sensor(self):
        from ocos.perception.pipeline import PerceptionPipeline
        pipeline = PerceptionPipeline()
        sensor = MagicMock()
        pipeline.register_sensor(sensor)

    def test_tick(self):
        from ocos.perception.pipeline import PerceptionPipeline
        pipeline = PerceptionPipeline()
        result = pipeline.tick()
        assert isinstance(result, list)
