"""Re-export from store/ontology.py (Knowledge Plane v1.0 split)."""
from __future__ import annotations

from ocos.knowledge.store.ontology import (
    ELEVATION_MATRIX,
    ElevationRecord,
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    STATUS_TRANSITIONS,
    can_elevate,
    can_transition,
    get_elevation_targets,
    get_level_index,
    get_next_statuses,
    is_higher_level,
    validate_elevation,
)
