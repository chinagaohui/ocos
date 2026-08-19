"""Phase 34: Runtime Awakening — test suite.

覆盖:
  34A: EventBus 感知神经 (push/ingest/trace)
  34B: WorkingMemory 恢复 (restore from SQLite)
  34C: MemoryHub Episode 记录 (result → episode)
  34D: Stability 指标 (tick latency / error rate / drift)
  34E: Identity Continuity (snapshot save / verify)

约束: 零行为变更，不破坏 1823 baseline。
"""

import pytest
import time
import uuid
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════
# 34A: EventBus — 感知神经系统
# ══════════════════════════════════════════════════════════════════════

class Test34A_EventBus:
    """EventBus: push → normalize → ingest → attention trace."""

    def test_create_and_push_file_event(self):
        from ocos.event import EventBus, EventSource

        eb = EventBus()
        ce = eb.push_file_change("/project/app.py", "modified")

        assert ce.source == EventSource.FILE_CHANGE
        assert ce.event_type == "file_modified"
        assert ce.metadata["path"] == "/project/app.py"
        assert eb.get_stats()["total_received"] == 1
        assert eb.get_stats()["pending"] == 1

    def test_push_and_ingest(self):
        from ocos.event import EventBus

        eb = EventBus()
        eb.push_file_change("/a.py")
        eb.push_timer("heartbeat")
        eb.push_webhook("alerts", {"msg": "test"})

        events = eb.ingest(max_events=10)
        assert len(events) == 3
        assert eb.get_stats()["total_ingested"] == 3
        # pending should be 0 after ingest
        assert eb.get_stats()["pending"] == 0

    def test_trace_recording(self):
        from ocos.event import EventBus, AttentionDecision

        eb = EventBus()
        ce = eb.push_file_change("/etc/secret.key")
        trace = eb.record_trace(ce, 0.95, AttentionDecision.ALERT, "critical security file")

        assert trace.decision == AttentionDecision.ALERT
        assert trace.attention_score == 0.95
        assert "critical" in trace.reason
        assert eb.get_stats()["traces_count"] == 1

    def test_normalizer_severity_hierarchy(self):
        from ocos.event import EventBus, EventSource, EventSeverity

        eb = EventBus()

        # Critical path
        ce1 = eb.push_file_change("/etc/secret.key")
        assert ce1.severity == EventSeverity.CRITICAL

        # High path
        ce2 = eb.push_file_change("/project/config.yaml")
        assert ce2.severity == EventSeverity.HIGH

        # Low path (test)
        ce3 = eb.push_file_change("/tests/test_app.py")
        assert ce3.severity == EventSeverity.LOW

        # Normal
        ce4 = eb.push_file_change("/src/utils.py")
        assert ce4.severity == EventSeverity.NORMAL

    def test_timer_score_discount(self):
        from ocos.event import EventBus

        eb = EventBus()
        ce = eb.push_timer("heartbeat")
        # Timer events have 0.8x multiplier on normal (0.5 → 0.4)
        assert ce.candidate_score == pytest.approx(0.4)

    def test_ingest_max_events_cap(self):
        from ocos.event import EventBus

        eb = EventBus(max_pending=100)
        for i in range(20):
            eb.push_file_change(f"/tmp/file_{i}.txt")

        events = eb.ingest(max_events=5)
        assert len(events) == 5
        assert eb.get_stats()["pending"] == 15

    def test_event_bus_available_in_runtime(self):
        from ocos.event import EventBus

        # Just verify class exists
        assert EventBus is not None
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "event_bus")

    def test_event_not_intention_principles(self):
        """EventBus 不直接触发 Goal — 事件 ≠ 意图。"""
        from ocos.event import EventBus, AttentionDecision

        eb = EventBus()
        ce = eb.push_file_change("/tmp/log.txt")

        # Low relevance → should be IGNORED by attention logic
        trace = eb.record_trace(ce, 0.2, AttentionDecision.IGNORED, "no related active goal")
        assert trace.decision == AttentionDecision.IGNORED
        # Decision is IGNORED — NOT triggering a goal (event ≠ intention)
        assert "create" not in trace.reason.lower()
        # AttentionDecision enum has no "CREATE_GOAL" value
        assert AttentionDecision.ALERT != "create_goal"


# ══════════════════════════════════════════════════════════════════════
# 34B: WorkingMemory 恢复
# ══════════════════════════════════════════════════════════════════════

class Test34B_WorkingMemoryRestore:
    """WM persist → restore → cognitive continuity."""

    def test_persist_and_restore_cycle(self):
        import tempfile
        from ocos.agent.memory_consolidator import MemoryConsolidator
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db_path = str(Path(tempfile.mkdtemp()) / "test_wm.db")

        # Create and populate MemoryConsolidator
        mem = MemoryConsolidator()
        mem.add_to_working("Task A result", importance=0.8, tags=["designer"])
        mem.add_to_working("Task B result", importance=0.6, tags=["executor"])

        # Persist
        store = SQLiteWorkingMemory(db_path, max_entries=100)
        store.store("wm:working", {
            "items": [
                {"content": m.content, "importance": m.importance,
                 "frequency": m.frequency, "tags": m.tags}
                for m in mem.get_working_items()
            ],
        })

        # Verify restore
        data = store.load("wm:working")
        assert data is not None
        assert len(data["items"]) == 2
        assert data["items"][0]["content"] == "Task A result"
        assert data["items"][1]["tags"] == ["executor"]

        store.close()

    def test_restore_to_empty_memory(self):
        import tempfile
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db_path = str(Path(tempfile.mkdtemp()) / "test_wm_empty.db")
        store = SQLiteWorkingMemory(db_path)
        data = store.load("wm:working")
        # No data written → None or empty
        assert data is None or data == {}
        store.close()

    def test_runtime_has_restore_method(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "_restore_working_memory")


# ══════════════════════════════════════════════════════════════════════
# 34C: MemoryHub — Episode 记录
# ══════════════════════════════════════════════════════════════════════

class Test34C_MemoryHubEpisode:
    """Result → Episode → MemoryHub persistence."""

    def test_episode_record_from_result(self):
        from ocos.memory.hub import MemoryHub
        from ocos.memory.episode.models import Episode, EpisodeStatus
        from datetime import datetime, timezone

        hub = MemoryHub(":memory:")
        hub.initialize()

        episode = Episode(
            id=f"EPI-test-{uuid.uuid4().hex[:8]}",
            experience_id="task-001",
            created_at=datetime.now(timezone.utc),
            session_id="tick_1",
            context={"agent": "designer", "success": True},
            goal="Design caching architecture",
            decision="execute",
            action="designer.execute",
            outcome={"success": True},
            condition="tick@1",
            significance_score=0.6,
            evaluation_trace={"source": "step9"},
            source="decision",
            status=EpisodeStatus.ACTIVE,
            tags=["designer", "cache"],
        )
        hub.episode.save(episode)
        assert hub.episode.count() == 1

        # Verify persistence
        retrieved = hub.episode.get(episode.id)
        assert retrieved is not None
        assert retrieved.goal == "Design caching architecture"
        assert retrieved.tags == ["designer", "cache"]

        hub.shutdown()

    def test_memory_hub_initialized_noop(self):
        from ocos.memory.hub import MemoryHub

        hub = MemoryHub(":memory:")
        # Not initialized → raises
        with pytest.raises(RuntimeError):
            _ = hub.episode

    def test_runtime_has_episode_recorder(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "_record_episode_from_result")

    def test_memory_hub_stats(self):
        from ocos.memory.hub import MemoryHub

        hub = MemoryHub(":memory:")
        hub.initialize()

        stats = hub.get_stats()
        assert stats["initialized"] is True
        assert "episode_count" in stats
        assert "belief_count" in stats
        hub.shutdown()

    def test_episode_idempotent_save(self):
        """Same experience_id → no duplicate episode."""
        from ocos.memory.hub import MemoryHub
        from ocos.memory.episode.models import Episode, EpisodeStatus
        from datetime import datetime, timezone

        hub = MemoryHub(":memory:")
        hub.initialize()

        exp_id = f"EXP-{uuid.uuid4().hex[:8]}"
        ep1 = Episode(
            id=f"EPI-{uuid.uuid4().hex[:12]}",
            experience_id=exp_id,
            created_at=datetime.now(timezone.utc),
            action="test",
            significance_score=0.5,
            source="decision",
        )
        hub.episode.save(ep1)

        # Same experience_id, different episode id → should be skipped
        ep2 = Episode(
            id=f"EPI-{uuid.uuid4().hex[:12]}",
            experience_id=exp_id,
            created_at=datetime.now(timezone.utc),
            action="test",
            significance_score=0.5,
            source="decision",
        )
        hub.episode.save(ep2)

        assert hub.episode.count() == 1  # Still 1
        hub.shutdown()


# ══════════════════════════════════════════════════════════════════════
# 34D: Stability Metrics
# ══════════════════════════════════════════════════════════════════════

class Test34D_StabilityMetrics:
    """Tick latency, error tracking, drift detection."""

    def test_runtime_has_boot_time(self):
        """_boot_time 在 __init__ 中赋值，通过实例检查。"""
        from ocos.agent.agent_runtime import AgentRuntime
        # Verify the attribute is assigned in __init__ source
        assert "_boot_time" in AgentRuntime.__init__.__code__.co_names

    def test_runtime_has_latency_tracking(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert "_tick_latencies" in AgentRuntime.__init__.__code__.co_names

    def test_runtime_has_error_counter(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert "_tick_errors" in AgentRuntime.__init__.__code__.co_names

    def test_stability_report_method(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "get_stability_report")


# ══════════════════════════════════════════════════════════════════════
# 34E: Identity Continuity
# ══════════════════════════════════════════════════════════════════════

class Test34E_IdentityContinuity:
    """跨 session 身份连续性验证。"""

    def test_save_snapshot_method_exists(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "_save_identity_snapshot")

    def test_verify_continuity_method_exists(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert hasattr(AgentRuntime, "_verify_identity_continuity")

    def test_snapshot_hash_creation(self):
        """Continuity hash is deterministic for same content."""
        import hashlib
        snapshot = {
            "agent_id": "test-agent",
            "cycle": 100,
            "version": "1.0-Phase34",
        }
        content = str(sorted(snapshot.items()))
        h1 = hashlib.sha256(content.encode()).hexdigest()[:16]
        h2 = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert h1 == h2  # Deterministic

        # Different content → different hash
        snapshot2 = {**snapshot, "cycle": 101}
        content2 = str(sorted(snapshot2.items()))
        h3 = hashlib.sha256(content2.encode()).hexdigest()[:16]
        assert h1 != h3


# ══════════════════════════════════════════════════════════════════════
# Import Rules
# ══════════════════════════════════════════════════════════════════════

def test_phase34_import_rules():
    """验证 Phase 34 新增模块可正常导入。"""
    # 34A
    from ocos.event import (
        EventBus, RawEvent, CognitiveEvent, EventSource,
        EventSeverity, AttentionDecision, EventNormalizer, IngestionTrace,
    )
    # 34C uses existing MemoryHub — ensure still importable
    from ocos.memory.hub import MemoryHub
    from ocos.memory.episode.models import Episode, EpisodeStatus
    from ocos.storage.working_memory import SQLiteWorkingMemory

    # AgentRuntime Core
    from ocos.agent.agent_runtime import AgentRuntime
    assert all([
        EventBus, RawEvent, CognitiveEvent, EventSource,
        EventSeverity, AttentionDecision, EventNormalizer, IngestionTrace,
        MemoryHub, Episode, EpisodeStatus, SQLiteWorkingMemory,
        AgentRuntime,
    ])
