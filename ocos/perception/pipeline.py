"""GAP-P1-3: perception → world_model 感知链 — PerceptionPipeline。

真实链路（方案草稿的 API 名与现状不符，以本文件为准）:
  FileSensor/TextSensor.poll() → sensor_types.Observation（感知层）
  → PerceptionEngine.tick() → PerceptionEvent（感知验证已内建）
  → 桥接: 感知 Observation → world_types.Observation（世界层，唯一写入入口所需形态）
  → WorldStore.update_from_observation()（WorldValidator 治理后落库）
  → （可选）CausalityEngine 状态链因果推断（相邻状态变更 → CausalityLink）

默认零传感器 — factory 注入；无环境变化时 tick() 零噪音、零写入。

注意: 感知层 Observation（id/content/source_sensor）与世界层 Observation
（observation_id/entity_id/claimed_state）是**两个同名不同类**——本 pipeline
是它们之间的唯一适配点，不允许旁路。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ocos.perception.perception_engine import PerceptionEngine
from ocos.perception.sensor_types import (
    Observation as PerceptionObservation,
    PerceptionEvent,
    SensorModality,
)
from ocos.perception_bus import EventBus, EventSource, RawEvent
from ocos.world_model.world_store import WorldStore
from ocos.world_model.world_types import (
    CausalityLink,
    CausalityType,
    EntityState,
    Observation as WorldObservation,
)
from ocos.world_model.world_validator import ValidationResult

logger = logging.getLogger(__name__)


class PerceptionPipeline:
    """感知 → 世界模型 + 认知事件 全链路 — 生产入口（daemon factory 注入）。

    GAP-P1-4 (2026-09-11): 同时 publish 到 perception_bus（此前只写 WorldStore，
    Observation → CognitiveEvent 断链）。
    """

    def __init__(
        self,
        engine: Optional[PerceptionEngine] = None,
        world: Optional[WorldStore] = None,
        infer_causality: bool = True,
        entity_resolver: Optional[Any] = None,
        state_resolver: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        """entity_resolver: callable(感知 Observation) -> entity_id（领域语义归属）。
        state_resolver: callable(感知 Observation) -> dict（实体状态属性）。
        event_bus: perception_bus.EventBus 实例（可选；不传时只写 WorldStore）。

        传感器本身不带实体/状态语义（FileSensor 只报"文件变了"）——实体与
        状态归属是感知管线的职责。无 resolver 且观察无 metadata 携带 →
        观察被 WorldValidator 诚实拒绝（fail-closed），绝不伪造实体/状态。
        """
        self._engine = engine or PerceptionEngine()
        self._world = world or WorldStore()
        self._infer_causality = infer_causality
        self._entity_resolver = entity_resolver
        self._state_resolver = state_resolver
        self._event_bus = event_bus
        self._last_states: dict[str, EntityState] = {}
        self._accepted: int = 0
        self._rejected: int = 0
        self._published: int = 0

    # ── EventBus 注入（GAP-P1-4） ──

    def set_event_bus(self, event_bus: Any) -> None:
        """注入 perception_bus.EventBus 实例（装配后注入用）。"""
        self._event_bus = event_bus

    @property
    def published_count(self) -> int:
        """已 publish 到 EventBus 的事件数（GAP-P1-4 统计）。"""
        return self._published

    # ── 对外只读视图 ──

    @property
    def engine(self) -> PerceptionEngine:
        return self._engine

    @property
    def world(self) -> WorldStore:
        return self._world

    @property
    def accepted_count(self) -> int:
        """被 WorldValidator 接受并落库的观察数。"""
        return self._accepted

    @property
    def rejected_count(self) -> int:
        """被拒绝的观察数（fail-closed 可见）。"""
        return self._rejected

    # ── 装配 ──

    def register_sensor(self, sensor: Any) -> None:
        """注册传感器（须有 poll() 方法）。"""
        self._engine.register_sensor(sensor)

    # ── 感知周期 ──

    def tick(self) -> list[PerceptionEvent]:
        """执行一次感知周期: 感知 → 验证 → 落世界模型 → 因果推断 → publish EventBus.

        GAP-P1-4 (2026-09-11): 同时 publish PerceptionEvent 到 perception_bus.
        这是唯一的 publish 点——所有经过本 Pipeline 的 Sensor 自动受益。
        """
        events = self._engine.tick()
        for ev in events:
            obs = ev.observation
            if obs is None:
                continue
            result = self._bridge_to_world(obs)
            if result.accepted:
                self._accepted += 1
            else:
                self._rejected += 1

            # GAP-P1-4: 同时 publish 到 perception_bus（Observation → CognitiveEvent 断链修复）
            if self._event_bus is not None:
                try:
                    raw = self._convert_to_raw_event(ev)
                    if raw is not None:
                        self._event_bus.push(raw)
                        self._published += 1
                except Exception as e:
                    logger.debug("EventBus publish failed for %s: %s",
                                 ev.sensor_name, e, exc_info=True)
        return events

    # ── 桥接: 感知 Observation → 世界 Observation ──

    def _bridge_to_world(self, obs: PerceptionObservation) -> ValidationResult:
        """把感知层观察转换为世界层观察并写入 WorldStore（唯一写入路径）。

        感知层字段映射:
          obs.id            → observation_id
          obs.source_sensor → source（WorldValidator 来源信誉依据）
          obs.metadata["entity_id"]   → entity_id
          obs.metadata["entity_state"]→ claimed_state（属性 dict → EntityState）
        """
        entity_id = self._entity_id_from(obs)
        world_obs = WorldObservation(
            observation_id=getattr(obs, "id", "") or f"obs-{id(obs)}",
            source=getattr(obs, "source_sensor", "") or "perception",
            entity_id=entity_id,
            claimed_state=self._claimed_state_from(obs, entity_id),
            raw_data=str(obs.content) if obs.content is not None else "",
            tick_id=getattr(obs, "tick_id", 0),
        )
        result = self._world.update_from_observation(world_obs)
        if result.accepted and self._infer_causality:
            self._infer_causality_links(world_obs)
        return result

    def _entity_id_from(self, obs: PerceptionObservation) -> str:
        if self._entity_resolver is not None:
            try:
                resolved = self._entity_resolver(obs)
                if resolved:
                    return str(resolved)
            except Exception:
                logger.debug("entity_resolver failed for %s", obs, exc_info=True)
        metadata = obs.metadata
        if isinstance(metadata, dict):
            return str(metadata.get("entity_id", "") or "")
        return ""

    def _claimed_state_from(
        self, obs: PerceptionObservation, entity_id: str
    ) -> Optional[EntityState]:
        attrs: Optional[dict] = None
        if self._state_resolver is not None:
            try:
                attrs = self._state_resolver(obs)
            except Exception:
                logger.debug("state_resolver failed for %s", obs, exc_info=True)
        if not attrs and isinstance(obs.metadata, dict):
            attrs = obs.metadata.get("entity_state")
        if not attrs or not isinstance(attrs, dict):
            return None
        return EntityState(
            state_id=f"st:{obs.id}",
            entity_id=entity_id,
            attributes=dict(attrs),
            tick_id=getattr(obs, "tick_id", 0),
        )

    # ── 因果推断: 同实体相邻状态变更 → CausalityLink ──

    def _infer_causality_links(self, world_obs: WorldObservation) -> None:
        state = self._world.get_entity_state(world_obs.entity_id)
        if state is None:
            return
        prev = self._last_states.get(world_obs.entity_id)
        if prev is not None and prev.attributes != state.attributes:
            link = CausalityLink(
                link_id=f"causal:{prev.state_id}->{state.state_id}",
                cause_event_id=prev.state_id,
                effect_event_id=state.state_id,
                causality_type=CausalityType.CONTRIBUTES,
                confidence=0.6,
                evidence_ids=(f"obs:{world_obs.observation_id}",),
                discovery_source="inference",
                tick_id=world_obs.tick_id,
            )
            try:
                self._world.causality.add_link(link)
            except ValueError:
                logger.debug("duplicate causality link skipped: %s", link.link_id)
        self._last_states[world_obs.entity_id] = state

    # ── GAP-P1-4: PerceptionEvent → RawEvent 转换 ──

    # SensorModality → EventSource 映射（确定性，无 LLM）
    _MODALITY_TO_SOURCE: dict[SensorModality, EventSource] = {
        SensorModality.FILE: EventSource.FILE_CHANGE,
        SensorModality.ENV: EventSource.SYSTEM,
        SensorModality.TEXT: EventSource.USER_INPUT,
        SensorModality.API: EventSource.WEBHOOK,
        SensorModality.VISION: EventSource.VISUAL,
        SensorModality.AUDIO: EventSource.AUDIO,
    }

    def _convert_to_raw_event(self, ev: PerceptionEvent) -> Optional[RawEvent]:
        """PerceptionEvent → RawEvent（确定性转换，不做语义判断）。

        EventNormalizer 后续会根据 source 自动归一化:
          FILE_CHANGE → _classify 提取 operation → file_created/file_modified 等
          SYSTEM     → fallback "system_event"
        """
        obs = ev.observation
        if obs is None:
            return None

        # modality → EventSource
        source = self._MODALITY_TO_SOURCE.get(obs.modality, EventSource.SYSTEM)

        # payload: content (dict) + metadata + 来源信息
        payload: dict[str, Any] = {}
        if isinstance(obs.content, dict):
            payload.update(obs.content)
        if isinstance(obs.metadata, dict):
            payload.update(obs.metadata)
        payload.setdefault("source_sensor", obs.source_sensor)
        payload.setdefault("confidence", obs.confidence)
        payload.setdefault("observation_type", obs.type.value)

        return RawEvent(source=source, payload=payload)
