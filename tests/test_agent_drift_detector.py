"""Tests for ocos.agent.drift_detector - Drift detection."""
import pytest
from unittest.mock import MagicMock


class TestDriftDetector:
    def test_import(self):
        from ocos.agent.drift_detector import DriftDetector
        assert DriftDetector is not None

    def test_create(self):
        from ocos.agent.drift_detector import DriftDetector
        detector = DriftDetector()
        assert detector is not None

    def test_check_all(self):
        from ocos.agent.drift_detector import DriftDetector
        detector = DriftDetector()
        result = detector.check_all()
        assert isinstance(result, list)

    def test_get_status(self):
        from ocos.agent.drift_detector import DriftDetector
        detector = DriftDetector()
        status = detector.get_status()
        assert isinstance(status, dict)

    def test_record_capability_usage(self):
        from ocos.agent.drift_detector import DriftDetector
        detector = DriftDetector()
        detector.record_capability_usage("test_capability")
