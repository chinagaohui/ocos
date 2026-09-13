#!/usr/bin/env python3
"""P4a SIMPLIFIED — 验证生产链每 step 的真实行为

简化版: 直接调 agent_runtime.tick() 看 10 steps 的输出
"""
import sys, os, tempfile, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P4a SIMPLIFIED — step-by-step trace")
print("=" * 70)

wd = Path(tempfile.mkdtemp(prefix="ocos-p4a-"))
watch_dir = wd / "watch"
watch_dir.mkdir()
db_path = tempfile.mktemp(prefix="ocos-p4a-", suffix=".db")

from ocos.daemon import ResidentRuntime
from ocos.perception.file_sensor import FileSensor
from ocos.daemon.factory import build_perception_pipeline

class _DummyCortex:
    def activate(self): pass

class _DummyAgent:
    agent_id = "p4a-test"
    cortex = _DummyCortex()
    def boot(self): pass
    def set_engine_bridge(self, eb): pass

rt = ResidentRuntime(agent=_DummyAgent(), db_path=db_path)
fs = FileSensor()
fs.watch_directory(watch_dir)
pipe = build_perception_pipeline(sensors=[fs], file_semantics=True)
rt.attach_perception_pipeline(pipe)

ar = rt._runtime
ar.boot()
ar._event_bus = rt._event_bus

# Reality: create 2 files
(watch_dir / "a.txt").write_text("A", encoding="utf-8")
(watch_dir / "b.txt").write_text("B", encoding="utf-8")
time.sleep(0.1)
pipe.tick()

eb = rt._event_bus
print(f"\n_pending before tick = {len(eb._pending)}")

# 直接调 AgentRuntime.tick() — 看 step 1 和 step 2
tick_result = ar.tick()

print(f"\nAgentRuntime.tick() returned: {json.dumps(tick_result, indent=2, default=str)[:1000]}")

# 关键内部状态
print(f"\n_last_ingestion_events = {len(ar._last_ingestion_events) if ar._last_ingestion_events else 0}")
print(f"  content types: {[e.get('event_type') for e in (ar._last_ingestion_events or [])]}")
print(f"\n_last_attention_decisions = {len(ar._last_attention_decisions) if ar._last_attention_decisions else 0}")
if ar._last_attention_decisions:
    for d in ar._last_attention_decisions:
        print(f"  decision={d.decision.value} focus={d.is_focus}")

print(f"\n_pending after tick = {len(eb._pending)}")

import shutil
shutil.rmtree(wd, ignore_errors=True)
