"""Deep tests for ocos.opentale_bridge.quality_analyzer."""
import pytest


class TestQualityAnalyzer:
    def test_import(self):
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        assert QualityAnalyzer is not None

    def test_create(self):
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        analyzer = QualityAnalyzer()
        assert analyzer is not None

    def test_analyze_simple(self):
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("test chapter content")
        assert result is not None

    def test_analyze_with_genre(self):
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("test content", genre="romance")
        assert result is not None

    def test_analyze_with_all_params(self):
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        analyzer = QualityAnalyzer()
        result = analyzer.analyze(
            "test content",
            genre="urban",
            chapter_number=5,
            chapter_title="Test Chapter",
            expected_arcs={"emotional": 0.8},
            external_quality=0.7,
            external_narrative=0.6
        )
        assert result is not None
