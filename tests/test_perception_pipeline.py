"""GAP-P1-3: perception → world_model 感知链（PerceptionPipeline）测试。

覆盖:
  1. FileSensor 捕获文件变化 → WorldStore 落实体/事件（E2E）
  2. 相邻状态变更 → CausalityEngine 上下游可查
  3. 零传感器 → 零事件零写入（无噪音）
  4. fail-closed: 无实体归属 → WorldValidator 诚实拒绝
"""
import time

from ocos.perception.file_sensor import FileSensor
from ocos.perception.pipeline import PerceptionPipeline
from ocos.world_model.world_types import (
    EntityState,
    WorldEventType,
)


def _write(path, content):
    path.write_text(content)
    time.sleep(0.02)  # mtime 粒度


def _file_pipeline(tmp_path, resolve=True):
    """构造带 FileSensor 的感知管线（实体=文件名, 状态=文件 mtime/size）。"""
    target = tmp_path / "watch.txt"
    _write(target, "v1")

    sensor = FileSensor()
    sensor.watch(target)
    pipeline = PerceptionPipeline(
        entity_resolver=(lambda obs: f"entity:{target.name}") if resolve else None,
        state_resolver=(
            lambda obs: {
                "path": (obs.content or {}).get("path", ""),
                "change": (obs.content or {}).get("change", ""),
                "current": str((obs.content or {}).get("current", "")),
            }
        )
        if resolve
        else None,
    )
    pipeline.register_sensor(sensor)
    return pipeline, target


class TestFileSensorToWorldModel:
    def test_file_change_lands_in_world_store(self, tmp_path):
        pipeline, target = _file_pipeline(tmp_path)
        pipeline.tick()  # 基线轮（无变化 → 零事件）
        assert pipeline.accepted_count == 0

        _write(target, "v2")
        events = pipeline.tick()
        assert len(events) == 1
        assert pipeline.accepted_count == 1

        state = pipeline.world.get_entity_state(f"entity:{target.name}")
        assert state is not None
        assert state.entity_id == f"entity:{target.name}"

    def test_event_recorded_in_event_model(self, tmp_path):
        pipeline, target = _file_pipeline(tmp_path)
        _write(target, "v3")
        pipeline.tick()
        # WorldStore 事件模型记录 external observation 事件
        events = pipeline.world.events
        assert events is not None
        assert len(events.by_type(WorldEventType.OBSERVATION)) >= 1

    def test_causality_upstream_downstream_queryable(self, tmp_path):
        pipeline, target = _file_pipeline(tmp_path)
        entity = f"entity:{target.name}"

        pipeline.tick()  # 基线
        _write(target, "v2")
        pipeline.tick()  # 状态变更 1
        state1 = pipeline.world.get_entity_state(entity)
        assert state1 is not None
        _write(target, "v3")
        pipeline.tick()  # 状态变更 2 → 相邻变更 → CausalityLink
        state2 = pipeline.world.get_entity_state(entity)
        assert state2 is not None

        link = pipeline.world.causality.get(
            f"causal:{state1.state_id}->{state2.state_id}"
        )
        assert link is not None
        assert link.cause_event_id != link.effect_event_id
        # 上下游可查
        assert len(pipeline.world.causality.effects_of(state1.state_id)) >= 1
        assert len(pipeline.world.causality.causes_of(state2.state_id)) >= 1


class TestZeroSensorAndFailClosed:
    def test_zero_sensor_no_noise(self):
        pipeline = PerceptionPipeline()
        events = pipeline.tick()
        assert events == []
        assert pipeline.accepted_count == 0
        assert pipeline.rejected_count == 0

    def test_unresolved_entity_rejected_honestly(self, tmp_path):
        """无 resolver 且观察无 metadata.entity_id → 诚实拒绝，不伪造实体。"""
        pipeline, target = _file_pipeline(tmp_path, resolve=False)
        _write(target, "v2")
        events = pipeline.tick()
        assert len(events) == 1          # 感知到了
        assert pipeline.accepted_count == 0  # 但被 validator 拒绝
        assert pipeline.rejected_count == 1
        assert pipeline.world.get_entity_state(f"entity:{target.name}") is None

    def test_factory_builds_default_pipeline(self):
        from ocos.daemon.factory import build_perception_pipeline
        pipeline = build_perception_pipeline()
        assert pipeline.world is not None
        assert pipeline.tick() == []
