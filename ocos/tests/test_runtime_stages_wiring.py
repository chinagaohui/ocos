"""GAP-P2-2: runtime/stages 4 个占位接线测试。

覆盖:
  1. EventIngestionStage + EventBus → events 注入
  2. MemorySyncStage + MemoryHub → stats 快照转发
  3. ResultCollectionStage + ExecutionManager → history 转发
  4. ExecutionCheckStage + TaskDAG → resolve_ready 候选 + gateway 过滤保留
  5. 零注入降级（旧装配兼容）
"""

import pytest

from ocos.agent.execution_manager import ExecutionManager
from ocos.event import EventBus
from ocos.memory.hub import MemoryHub
from ocos.runtime.stages.event_ingestion import EventIngestionStage
from ocos.runtime.stages.execution_check import ExecutionCheckStage
from ocos.runtime.stages.memory_sync import MemorySyncStage
from ocos.runtime.stages.result_collection import ResultCollectionStage
from ocos.runtime.tick_context import create_tick_context
from ocos.task import TaskDAG, TaskStatus


@pytest.fixture
def ctx():
    return create_tick_context(tick_id=1, runtime_state="running")


class TestEventIngestion:
    def test_drains_event_bus(self, ctx):
        bus = EventBus()
        bus.push_file_change("/tmp/a.txt")
        bus.push_file_change("/tmp/b.txt")
        stage = EventIngestionStage(event_bus=bus, max_events=10)
        out = stage.execute(ctx)
        assert len(out.events) == 2
        assert out.events[0].source.name == "FILE_CHANGE"
        assert "EVENT_INGESTION" in out.stage_traces

    def test_drain_cap(self, ctx):
        bus = EventBus()
        for i in range(5):
            bus.push_file_change(f"/tmp/{i}.txt")
        stage = EventIngestionStage(event_bus=bus, max_events=2)
        out = stage.execute(ctx)
        assert len(out.events) == 2


class TestMemorySync:
    def test_forwards_hub_stats(self, ctx):
        hub = MemoryHub()
        hub.initialize()
        stage = MemorySyncStage(memory_hub=hub)
        out = stage.execute(ctx)
        assert len(out.memory_changes) == 1
        stats = out.memory_changes[0]
        assert isinstance(stats, dict) and "episode_count" in stats
        assert "MEMORY_SYNC" in out.stage_traces

    def test_uninitialized_hub_empty(self, ctx):
        hub = MemoryHub()  # 未 initialize
        stage = MemorySyncStage(memory_hub=hub)
        out = stage.execute(ctx)
        assert out.memory_changes == ()


class TestResultCollection:
    def test_forwards_history(self, ctx):
        mgr = ExecutionManager()
        mgr.begin("write", {"path": "/tmp/x"})
        mgr.complete(result={"ok": True})
        stage = ResultCollectionStage(execution_manager=mgr)
        out = stage.execute(ctx)
        assert len(out.execution_results) == 1
        assert out.execution_results[0]["type"] == "write"
        assert out.execution_results[0]["status"] == "completed"
        assert "RESULT_COLLECTION" in out.stage_traces


class TestExecutionCheck:
    def test_resolves_ready_tasks(self, ctx):
        dag = TaskDAG()
        dag.add_task("t1")
        dag.add_task("t2", depends_on="t1")
        dag.set_status("t1", TaskStatus.COMPLETED)
        dag.set_status("t2", TaskStatus.PENDING)
        stage = ExecutionCheckStage(task_dag=dag)
        out = stage.execute(ctx)
        assert len(out.execution_candidates) == 1
        assert out.execution_candidates[0].task_id == "t2"
        assert "EXECUTION_CHECK" in out.stage_traces

    def test_no_dag_no_candidates(self, ctx):
        stage = ExecutionCheckStage()
        out = stage.execute(ctx)
        assert out.execution_candidates == ()


class TestZeroInjectionDegrade:
    """零注入 = 旧装配行为（全空，不崩）。"""

    def test_all_stages_without_deps(self, ctx):
        out = ctx
        for stage in (
            EventIngestionStage(),
            MemorySyncStage(),
            ResultCollectionStage(),
            ExecutionCheckStage(),
        ):
            out = stage.execute(out)
        assert out.events == ()
        assert out.memory_changes == ()
        assert out.execution_results == ()
        assert out.execution_candidates == ()
