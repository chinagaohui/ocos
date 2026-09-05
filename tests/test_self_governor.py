"""Tests for ocos.self.governor."""
import pytest
from datetime import datetime
from ocos.self.identity_boundary import IdentityBoundary, BoundaryPrinciple, ForbiddenTransition


class TestSelfGovernor:
    def test_import(self):
        from ocos.self.governor import SelfGovernor
        assert SelfGovernor is not None

    def test_create_with_boundary(self):
        from ocos.self.governor import SelfGovernor
        boundary = IdentityBoundary(
            id='test', version=1,
            principles=(
                BoundaryPrinciple.NO_SELF_MODIFICATION,
                BoundaryPrinciple.CAPABILITY_BOUND,
                BoundaryPrinciple.EVOLUTION_GOVERNED,
            ),
            forbidden_transitions=(
                ForbiddenTransition('neutral', 'persona', 'Self must not evolve into a persona'),
                ForbiddenTransition('neutral', 'goal-owner', 'Self must not claim ownership of Goal Model'),
            ),
            authority_limits=('self-layer',),
            self_reference_constraints=('no-circular-proof',),
            evolution_constraints={
                'min_stability_days': 7,
                'min_evidence_beliefs': 3,
                'require_governance_approval': True,
                'max_evolution_frequency_days': 30,
            },
            created_at=datetime.now()
        )
        governor = SelfGovernor(boundary=boundary)
        assert governor is not None
