#!/usr/bin/env python3
"""P5.1 HOST PERCEPTION — EnvironmentSensor → SYSTEM fine-grained → Attention → Brain

验证:
  EnvironmentSensor (memory_high / memory_spike)
    → PerceptionPipeline → EventBus
    → EventNormalizer 细粒度 system_memory_high / system_memory_spike
    → TickPipeline.peek → AgentRuntime.ingest → Attention
    → AttentionReport with system events
    → DecisionBridge._attention_decision_context
    → Brain prompt 有 Host reality 信息
"""

import sys, os, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P5.1 HOST PERCEPTION — EnvironmentSensor → SYSTEM → Attention → Brain")
print("=" * 70)

wd = Path(tempfile.mkdtemp(prefix="ocos-p51-"))
db_path = tempfile.mktemp(prefix="ocos-p51-", suffix=".db")

from ocos.daemon import ResidentRuntime
from ocos.perception.environment_sensor import EnvironmentSensor
from ocos.daemon.factory import build_perception_pipeline

# 手动调低阈值来强制触发环境事件
es = EnvironmentSensor()
es._memory_high_mb = 10       # 10MB 就触发 high
es._memory_critical_mb = 15    # 15MB 就触发 critical

pipe = build_perception_pipeline(sensors=[es], file_semantics=False)

class _DummyCortex:
    def activate(self): pass

class _DummyAgent:
    agent_id = "p51-test"
    cortex = _DummyCortex()
    def boot(self): pass
    def set_engine_bridge(self, eb): pass
    def world_context(self): return {"available": False, "entities": []}

rt = ResidentRuntime(agent=_DummyAgent(), db_path=db_path)
rt.attach_perception_pipeline(pipe)

ar = rt._runtime
ar.boot()
ar._event_bus = rt._event_bus

bridge = __import__('ocos.execution.bridge', fromlist=['DecisionBridge']).DecisionBridge()
bridge.attach_attention_source(lambda: ar._attention_report)
ar.attach_decision_bridge(bridge)

kernel = rt._kernel
kernel.start()
kernel.attach_agent_driver(lambda tick_id: ar.tick())

# Reality: memory spike!
print(f"\n[REALITY] 强制 EnvironmentSensor 检测 (阈值 memory_high={es._memory_high_mb}MB)")
# 让快照存在过 → 触发 spike 检测
es._last_snapshot = __import__('ocos.perception.environment_sensor', fromlist=['EnvironmentSnapshot']).EnvironmentSnapshot(
    timestamp=time.time() - 2,
    memory_used_mb=2.0,
    memory_total_mb=8192.0,
    cpu_percent=5.0,
    disk_used_gb=50.0,
    uptime_seconds=120.0,
)

# 实际 poll (会检测到当前内存 vs 上次 2MB 的跳变)
pipe.tick()  # 触发 EnvironmentSensor

eb = rt._event_bus
sys_events = [ce for ce in eb._pending if ce.source.name == "SYSTEM"]
print(f"  _pending SYSTEM events = {len(sys_events)}")
for ev in sys_events:
    print(f"    event_type={ev.event_type} severity={ev.severity.name}")
    print(f"    summary={ev.summary}")

# 关键验证: event_type 是 system_memory_high / system_memory_spike 不是 system_event
p51_ok = all(ev.event_type != "system_event" for ev in sys_events)
print(f"\n  ✅ SYSTEM 事件细粒度分类: {p51_ok}")

# AgentRuntime 消费
print(f"\n[PRODUCTION] RuntimeKernel.tick_loop → SYSTEM → Attention → Brain")
kernel.tick_loop(max_ticks=1)

print(f"  _pending after tick = {len(eb._pending)}")
print(f"  _last_ingestion_events = {len(ar._last_ingestion_events) if ar._last_ingestion_events else 0}")
if ar._last_ingestion_events:
    for e in ar._last_ingestion_events:
        print(f"    📋 {e['event_type']}: {e['summary'][:70]}")

# Attention context in prompt
ctx = bridge._memory_decision_context("分析宿主机状态")
if "感知焦点状态" in (ctx or "") and "memory" in (ctx or "").lower():
    print(f"\n  ✅ Attention context 里有 Host reality 信息!")
    print(f"\n{ctx}")
else:
    attn = bridge._attention_decision_context()
    print(f"\n  Attention context: {attn}")
    print(f"  _attention_report: {ar._attention_report}")

print("\n" + "=" * 70)
print("P5.1 HOST PERCEPTION VERDICT")
print("=" * 70)

v = {
    "① EnvironmentSensor 触发 SYSTEM 事件": len(sys_events) > 0,
    "② SYSTEM 事件细粒度分类 (非单纯 system_event)": p51_ok,
    "③ AgentRuntime 消费 SYSTEM 事件 (step 1)": len(ar._last_ingestion_events or []) > 0,
    "④ Attention context → Brain prompt": "memory" in (ctx or "").lower() if ctx else False,
}

for desc, result in v.items():
    mark = "✅" if result else "❌"
    print(f"  {mark}  {desc}")

all_pass = all(v.values())
print(f"\nP5.1 HOST: {'✅ ALL PASS — Host reality → SYSTEM → Attention → Brain 闭合' if all_pass else '❌ FAIL'}")

import shutil
shutil.rmtree(wd, ignore_errors=True)
os.unlink(db_path)
