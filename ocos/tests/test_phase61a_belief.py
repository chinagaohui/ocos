"""Phase 61-a: Belief Module tests."""
import time
import pytest
from ocos.belief import (
    Belief,
    BeliefManager,
    BeliefDimension,
    BeliefQuadrant,
    EvidenceSource,
    Evidence,
    SOURCE_WEIGHTS,
)


class TestBeliefModel:
    """Belief dataclass 基本行为。"""

    def test_create_belief(self):
        b = Belief(statement="Python is great", probability=0.7)
        assert b.statement == "Python is great"
        assert b.probability == 0.7
        assert b.belief_id.startswith("bel-")
        assert b.quadrant in (BeliefQuadrant.ASSUMPTION, BeliefQuadrant.SPECULATION)

    def test_quadrant_classification(self):
        # Conviction: high prob + many evidence
        b1 = Belief(probability=0.85)
        for _ in range(5):
            b1.evidence_chain.append(Evidence(belief_id=b1.belief_id))
        assert b1.quadrant == BeliefQuadrant.CONVICTION

        # Assumption: high prob + few evidence
        b2 = Belief(probability=0.85)
        b2.evidence_chain.append(Evidence(belief_id=b2.belief_id))
        assert b2.quadrant == BeliefQuadrant.ASSUMPTION

        # Suspicion: low prob + many evidence
        b3 = Belief(probability=0.3)
        for _ in range(5):
            b3.evidence_chain.append(Evidence(belief_id=b3.belief_id))
        assert b3.quadrant == BeliefQuadrant.SUSPICION

        # Speculation: low prob + few evidence
        b4 = Belief(probability=0.3)
        assert b4.quadrant == BeliefQuadrant.SPECULATION

    def test_to_dict(self):
        b = Belief(statement="test", probability=0.75)
        d = b.to_dict()
        assert d["statement"] == "test"
        assert d["probability"] == 0.75
        assert "quadrant" in d
        assert "strength" in d

    def test_evidence_weight(self):
        e = Evidence(source=EvidenceSource.USER_STATED)
        assert e.get_weight() == pytest.approx(0.9, 0.01)
        e2 = Evidence(source=EvidenceSource.INFERRED)
        assert e2.get_weight() == pytest.approx(0.4, 0.01)

    def test_max_probability_capped(self):
        b = Belief(probability=0.999)
        mgr = BeliefManager()
        mgr._beliefs[b.belief_id] = b
        mgr.update_with_evidence(b.belief_id, "super strong", "positive", EvidenceSource.USER_STATED)
        assert b.probability <= BeliefManager.MAX_PROBABILITY

    def test_min_probability_floor(self):
        b = Belief(probability=0.005)
        mgr = BeliefManager()
        mgr._beliefs[b.belief_id] = b
        mgr.update_with_evidence(b.belief_id, "super negative", "negative", EvidenceSource.USER_STATED)
        assert b.probability >= BeliefManager.MIN_PROBABILITY


class TestBeliefManager:
    """BeliefManager 核心操作。"""

    def test_add_belief(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Test belief", BeliefDimension.WORLD_KNOWLEDGE, 0.6)
        assert b.belief_id in mgr._beliefs
        assert len(b.evidence_chain) >= 1  # must have at least one evidence

    def test_add_belief_without_explicit_evidence_gets_auto(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Auto evidence test", BeliefDimension.WORLD_KNOWLEDGE, 0.5)
        assert len(b.evidence_chain) >= 1

    def test_remove_belief(self):
        mgr = BeliefManager()
        b = mgr.add_belief("To be removed")
        assert mgr.remove(b.belief_id)
        assert mgr.get(b.belief_id) is None

    def test_remove_nonexistent(self):
        mgr = BeliefManager()
        assert not mgr.remove("nonexistent")

    def test_get(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Target")
        assert mgr.get(b.belief_id) is b
        assert mgr.get("not-there") is None


class TestEvidenceUpdate:
    """证据驱动更新逻辑。"""

    def test_positive_evidence_increases_probability(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Test", probability=0.5, source=EvidenceSource.DEFAULT_ASSUMPTION)
        old_prob = b.probability
        mgr.update_with_evidence(b.belief_id, "good evidence", "positive", EvidenceSource.USER_STATED)
        assert b.probability > old_prob

    def test_negative_evidence_decreases_probability(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Test", probability=0.8, source=EvidenceSource.DEFAULT_ASSUMPTION)
        old_prob = b.probability
        mgr.update_with_evidence(b.belief_id, "bad evidence", "negative", EvidenceSource.USER_STATED)
        assert b.probability < old_prob

    def test_neutral_evidence_minimal_change(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Test", probability=0.7, source=EvidenceSource.DEFAULT_ASSUMPTION)
        old_prob = b.probability
        mgr.update_with_evidence(b.belief_id, "neutral", "neutral", EvidenceSource.INFERRED)
        # neutral should not change much
        assert abs(b.probability - old_prob) < 0.15

    def test_evidence_adds_to_chain(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Chain test")
        initial_count = len(b.evidence_chain)
        mgr.update_with_evidence(b.belief_id, "e1", "positive")
        mgr.update_with_evidence(b.belief_id, "e2", "negative")
        assert len(b.evidence_chain) == initial_count + 2

    def test_user_stated_has_more_weight(self):
        mgr = BeliefManager()
        b1 = mgr.add_belief("B1", probability=0.5)
        b2 = mgr.add_belief("B2", probability=0.5)

        mgr.update_with_evidence(b1.belief_id, "weak", "positive", EvidenceSource.DEFAULT_ASSUMPTION)
        mgr.update_with_evidence(b2.belief_id, "strong", "positive", EvidenceSource.USER_STATED)

        # USER_STATED should push prob higher than DEFAULT_ASSUMPTION
        assert b2.probability > b1.probability

    def test_update_nonexistent_belief(self):
        mgr = BeliefManager()
        result = mgr.update_with_evidence("nonexistent", "test", "positive")
        assert result is None

    def test_confirmation_bias_reset(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Bias test", probability=0.5)
        events_before = len(mgr._event_log)

        # Add 3 positive evidences in a row → should trigger alert
        for i in range(3):
            mgr.update_with_evidence(b.belief_id, f"positive {i}", "positive")

        # After 3 positives, positive_count resets but we logged an alert
        new_events = [e for e in mgr._event_log[events_before:] if e["event"] == "confirmation_bias_alert"]
        assert len(new_events) >= 1


class TestDecay:
    """时间衰减逻辑。"""

    def test_decay_reduces_probability(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Decay test", probability=0.8, decay_rate=0.1)
        b.last_updated = time.time() - 86400 * 2  # 2 days ago

        old_prob = b.probability
        mgr.decay_check()
        assert b.probability < old_prob

    def test_decay_floor_marks_dormant(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Weak belief", probability=0.1, decay_rate=0.3)
        b.last_updated = time.time() - 86400 * 10  # 10 days ago

        decayed = mgr.decay_check()
        assert len(decayed) >= 1
        assert b.belief_id in [d.belief_id for d in decayed]

    def test_fresh_belief_not_decayed(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Fresh", probability=0.8)
        b.last_updated = time.time()  # just now

        decayed = mgr.decay_check()
        assert len(decayed) == 0

    def test_prune_dormant(self):
        mgr = BeliefManager()
        total_before = len(mgr._beliefs)

        b = mgr.add_belief("To be pruned", probability=0.03, decay_rate=0.3)
        b.last_updated = time.time() - 86400 * 35  # 35 days ago, well past 30-day max

        removed = mgr.prune_dormant(max_age_days=30)
        assert removed >= 1
        assert total_before + 1 - removed <= len(mgr._beliefs)


class TestQuery:
    """检索功能。"""

    def setup_method(self):
        self.mgr = BeliefManager()
        self.mgr.add_belief("Python is great", BeliefDimension.WORLD_KNOWLEDGE, 0.9,
                            evidence_description="many users like it")
        self.mgr.add_belief("User prefers bash", BeliefDimension.USER_MODEL, 0.85,
                            evidence_description="observed multiple times")
        self.mgr.add_belief("Vim is hard", BeliefDimension.TOOL_MODEL, 0.3,
                            evidence_description="steep learning curve")

    def test_query_by_dimension(self):
        results = self.mgr.query(dimension=BeliefDimension.USER_MODEL)
        assert len(results) >= 1
        assert all(r.dimension == BeliefDimension.USER_MODEL for r in results)

    def test_query_by_quadrant(self):
        results = self.mgr.query(quadrant=BeliefQuadrant.ASSUMPTION)
        assert all(r.quadrant == BeliefQuadrant.ASSUMPTION for r in results)

    def test_query_min_probability(self):
        results = self.mgr.query(min_probability=0.8)
        assert all(r.probability >= 0.8 for r in results)

    def test_get_strongest(self):
        top = self.mgr.get_strongest(2)
        assert len(top) <= 2
        if len(top) >= 2:
            assert top[0].strength >= top[1].strength

    def test_get_convictions(self):
        conv = self.mgr.get_convictions()
        for c in conv:
            assert c.quadrant == BeliefQuadrant.CONVICTION

    def test_find_by_statement(self):
        b = self.mgr.find_by_statement("Python is great")
        assert b is not None
        assert b.statement == "Python is great"

        not_found = self.mgr.find_by_statement("Rust is awesome")
        assert not_found is None

    def test_query_limit(self):
        results = self.mgr.query(limit=1)
        assert len(results) <= 1


class TestMerge:
    """信念合并。"""

    def test_merge_two_identical_statements(self):
        mgr = BeliefManager()
        b1 = mgr.add_belief("Same statement", probability=0.6)
        b2 = mgr.add_belief("Same statement", probability=0.9)

        # Add some evidence to both
        mgr.update_with_evidence(b1.belief_id, "e1", "positive")
        mgr.update_with_evidence(b2.belief_id, "e2", "positive")
        mgr.update_with_evidence(b2.belief_id, "e3", "positive")

        count_before = len(mgr._beliefs)
        merged = mgr.merge_beliefs(b1.belief_id, b2.belief_id)
        assert merged is not None
        assert merged.belief_id == b1.belief_id
        assert len(mgr._beliefs) == count_before - 1

    def test_merge_different_statements_fails(self):
        mgr = BeliefManager()
        b1 = mgr.add_belief("Statement A")
        b2 = mgr.add_belief("Statement B")
        result = mgr.merge_beliefs(b1.belief_id, b2.belief_id)
        assert result is None

    def test_merge_with_nonexistent_ids(self):
        mgr = BeliefManager()
        result = mgr.merge_beliefs("nonexistent1", "nonexistent2")
        assert result is None


class TestStatsAndEvents:
    """统计和事件日志。"""

    def test_stats_returns_expected_keys(self):
        mgr = BeliefManager()
        mgr.add_belief("Test 1", BeliefDimension.WORLD_KNOWLEDGE, 0.8)
        mgr.add_belief("Test 2", BeliefDimension.USER_MODEL, 0.3)

        s = mgr.stats()
        assert s["total_beliefs"] == 2
        assert "by_dimension" in s
        assert "by_quadrant" in s
        assert "conviction_count" in s

    def test_drain_events(self):
        mgr = BeliefManager()
        mgr.add_belief("Event test")
        events = mgr.drain_events()
        assert len(events) >= 2  # evidence_added + belief_added
        event_names = [e["event"] for e in events]
        assert "belief_added" in event_names

        # Events should be cleared after drain
        events2 = mgr.drain_events()
        assert len(events2) == 0


class TestGarbageCollection:
    """MAX_BELIEFS 上限处理。"""

    def test_gc_trims_excess(self):
        mgr = BeliefManager()
        # Add many beliefs
        for i in range(50):
            mgr.add_belief(f"Belief #{i}", probability=0.1 + i * 0.001)
        # Should not crash, still at manageable count
        assert len(mgr._beliefs) <= BeliefManager.MAX_BELIEFS


class TestEdgeCases:
    """边界条件。"""

    def test_probability_clamp_on_add(self):
        mgr = BeliefManager()
        b = mgr.add_belief("Clamp test", probability=1.5)
        assert b.probability <= 0.99

    def test_zero_evidence_belief_handled(self):
        """empty evidence chain still has valid quadrant."""
        b = Belief(probability=0.7)
        # No evidence added yet
        assert b.quadrant in (BeliefQuadrant.ASSUMPTION, BeliefQuadrant.SPECULATION)

    def test_many_updates_converge(self):
        """Repeated positive updates should converge toward max, not exceed."""
        mgr = BeliefManager()
        b = mgr.add_belief("Convergence", probability=0.5)
        for i in range(20):
            mgr.update_with_evidence(b.belief_id, f"positive {i}", "positive", EvidenceSource.USER_STATED)
        assert b.probability <= BeliefManager.MAX_PROBABILITY
        assert b.probability > 0.9  # Should be very high after 20 strong positives
