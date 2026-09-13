"""P1-1 G4: WorldView → Thinking Consumption 只读消费层。

回答: "W1 形成后，OCOS 的 Thinking 如何合法读取它？"

边界（FROZEN，G4 Implementation Plan ×2）:
  - G4 是**读取**，不是认知增强：本模块只把 committed S2 worldview 投影为
    结构化 Thinking Input Context 块，不推理、不判断、不修改、不生成新 W1。
  - G4 是 **Thinking input**，不是 Decision behavior：消费链止于 Thinking
    Input Context，不接入 context_builder / decision_pipeline / agent_runtime /
    bridge 任何生产决策执行（真实行为影响留给 P1-1D）。
  - G4 **消费** W1，不重新生成 W1：数据源唯一 =
    SelfProjectionAccessor.get_committed_worldview()（已 Govern 的 committed 态）；
    禁止访问 WorldViewRecognitionRule / WorldViewExperienceGate / Claim 生成层。

明确 NOT:
  - ✗ 修改 Self / update worldview（反向影响 → Thinking→Self 自我污染，G4-H 守卫）
  - ✗ fallback 生成 worldview 内容（无 W1 → 空块，Thinking input 不变化）
  - ✗ 自然语言"我的世界观认为…"（防 prompt 假消费；只产出结构化块）
"""

from __future__ import annotations

from typing import Any

# WorldViewContextBlock 版本（结构化块 schema 版本，I2 溯源）。
_WV_BLOCK_VERSION = 1

# 允许消费的结构化字段白名单（消费即投影，禁止 interpretation 字段）。
_BLOCK_FIELDS = (
    "type",
    "version",
    "domain",
    "judgment",
    "frame",
    "stance_type",
    "confidence",
    "continuity",
    "claim_id",
    "evidence_ids",
    "source",
)


class WorldViewContextBlock:
    """结构化 worldview 消费块（数据载体，非自然语言）。

    字段 = committed W1 的原样结构化投影 + 溯源锚（claim_id / evidence_ids /
    source，I2）。禁止 recommended_action / strategy / decision 等 interpretation
    字段（属 P1-1D）。immutable 语义：只读消费。
    """

    __slots__ = tuple(_BLOCK_FIELDS)

    # 结构化字段白名单（供调用方/测试做 schema 断言）。
    FIELDS: tuple[str, ...] = _BLOCK_FIELDS

    def __init__(self, **kwargs: Any) -> None:
        for field_name in _BLOCK_FIELDS:
            setattr(self, field_name, kwargs.get(field_name))
        self.type = "worldview"
        self.version = _WV_BLOCK_VERSION
        self.source = kwargs.get("source", "committed_self_projection")

    def to_dict(self) -> dict:
        """canonical 结构字典（I1 diff 采集用，字段顺序固定）。"""
        return {field_name: getattr(self, field_name) for field_name in _BLOCK_FIELDS}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WorldViewContextBlock):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"WorldViewContextBlock(domain={self.domain!r}, judgment={self.judgment!r})"


class WorldViewReadAdapter:
    """只读封装：把 committed S2 worldview 投影为 Thinking 可消费的结构化块。

    只读：无写路径、不推理不判断、不做 fallback 生成。
    数据源唯一 = SelfProjectionAccessor.get_committed_worldview()（committed，经 Govern）。
    禁止访问：WorldViewRecognitionRule / WorldViewExperienceGate / Claim 生成层。
    """

    def __init__(self, accessor: Any) -> None:
        self._acc = accessor

    def consume(self) -> list[dict]:
        """返回结构化 worldview 块列表（无 W1 → []）。

        adapter output == projection（仅把 committed W1 结构化搬移，不解释、
        不补默认值）。每块保留 claim_id / evidence_ids / source 溯源（I2）。
        """
        raw = self._acc.get_committed_worldview()
        return [WorldViewContextBlock(**item).to_dict() for item in raw]

    def has_worldview(self) -> bool:
        return bool(self.consume())


class ThinkingContextProvider:
    """把 base Self 上下文 + worldview 块组装成 Thinking Input Context（唯一消费入口）。

    原则：S2 committed worldview → Read Adapter → Thinking input。只追加结构化
    worldview 块，不改 base Self 自然语言段（G4-B 逐字节保 true）；CONFIRM
    （仅置信/证据变化）不改变块内容（G4-F）。本组件只产出 Thinking Input
    Context，不接入任何生产决策执行（G4 终止边界）。
    """

    def __init__(self, accessor: Any) -> None:
        self._adapter = WorldViewReadAdapter(accessor)

    def build(self, base_self_context: str = "") -> dict:
        return {
            "self": base_self_context,             # 逐字节转发，不改
            "worldview": self._adapter.consume(),  # 结构化块；无 W1 → []
        }

    def worldview_for(self, domain: str) -> dict | None:
        for block in self._adapter.consume():
            if block["domain"] == domain:
                return block
        return None


__all__ = ["WorldViewContextBlock", "WorldViewReadAdapter", "ThinkingContextProvider"]
