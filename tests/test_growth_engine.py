"""Deep tests for ocos.growth.engine."""
import pytest


class TestGrowthEngine:
    def test_import(self):
        from ocos.growth.engine import GrowthEngine
        assert GrowthEngine is not None

    def test_create(self):
        from ocos.growth.engine import GrowthEngine
        engine = GrowthEngine()
        assert engine is not None

    def test_analyze_pending(self):
        from ocos.growth.engine import GrowthEngine
        engine = GrowthEngine()
        result = engine.analyze_pending()
        assert isinstance(result, list)

    def test_execute_proposal_with_mock(self):
        """Test execute_proposal with a proper GrowthProposal."""
        from ocos.growth.engine import GrowthEngine, GrowthProposal
        engine = GrowthEngine()
        # GrowthProposal needs signal_topic, rationale, file_path
        proposal = GrowthProposal(
            signal_topic="test_topic",
            rationale="test rationale for this proposal",
            file_path="/tmp/test.py"
        )
        result = engine.execute_proposal(proposal)
        assert result is not None
