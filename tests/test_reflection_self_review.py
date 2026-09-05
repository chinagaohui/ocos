"""Deep tests for ocos.reflection.self_review."""
import pytest


class TestSelfReview:
    def test_import_analyzer(self):
        from ocos.reflection.self_review import SelfReviewAnalyzer
        assert SelfReviewAnalyzer is not None

    def test_import_collector(self):
        from ocos.reflection.self_review import SelfReviewCollector
        assert SelfReviewCollector is not None

    def test_create_analyzer(self):
        from ocos.reflection.self_review import SelfReviewAnalyzer
        analyzer = SelfReviewAnalyzer()
        assert analyzer is not None

    def test_create_collector(self):
        from ocos.reflection.self_review import SelfReviewCollector
        collector = SelfReviewCollector()
        assert collector is not None

    def test_analyze(self):
        from ocos.reflection.self_review import SelfReviewAnalyzer
        analyzer = SelfReviewAnalyzer()
        result = analyzer.analyze({})
        assert result is not None
