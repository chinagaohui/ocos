"""ocos/events/ — 宪法事件总线 (pub/sub)。

职责分工(GAP-P3-5 裁决): 本包 = 宪法 Rule 2 模块间通信总线
(基于 kernel.abi.Event, topic pub/sub, 生产: health_check/
engine_bridge/governance_engine/process_runtime/policy_engine/
scheduler); ocos/event/ = 感知神经系统 (Phase 34A, 外部事件
归一化 → Attention candidate_score, 生产: agent_runtime)。
两包职责不同、并存不合并。event_store.py 内存版由
test_event_bus 契约锁定, 保留。
"""
