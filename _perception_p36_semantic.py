#!/usr/bin/env python3
"""P3.6 SEMANTIC FIDELITY — 验证 created/modified/deleted 事件类型正确

验证目标:
  Reality create → CognitiveEvent.event_type = "file_created"   ✅
  Reality modify → CognitiveEvent.event_type = "file_modified"  ✅
  Reality delete → CognitiveEvent.event_type = "file_deleted"   ✅ (之前会被误分类为 file_modified)

通过标准:
  每个操作的 event_type 与 Reality 语义严格一致
  从 PerceptionPipeline → EventNormalizer → CognitiveEvent 生产路径验证
"""

import sys, os, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P3.6 SEMANTIC FIDELITY — created/modified/deleted event_type correctness")
print("=" * 70)

wd = Path(tempfile.mkdtemp(prefix="ocos-p36-"))
watch_dir = wd / "watch"
watch_dir.mkdir()

from ocos.perception.file_sensor import FileSensor
from ocos.daemon.factory import build_perception_pipeline
from ocos.perception_bus import EventBus

fs = FileSensor()
fs.watch_directory(watch_dir)
pipe = build_perception_pipeline(sensors=[fs], file_semantics=True)
eb = EventBus()
pipe.set_event_bus(eb)

results = {}

# ── Test 1: DELETE (先创建再删除) ──
print("\n[TEST 1] DELETE")
f = watch_dir / "to_delete.txt"
f.write_text("initial", encoding="utf-8")
time.sleep(0.1)
pipe.tick()  # baseline → snapshot

f.unlink()
time.sleep(0.1)
pipe.tick()  # should detect deleted

delete_events = [ce for ce in eb._pending if ce.source.name == "FILE_CHANGE"]
print(f"  _pending 中 FILE_CHANGE events: {len(delete_events)}")
for ev in delete_events:
    print(f"    event_type={ev.event_type}  summary={ev.summary}")

# 直接看 EventNormalizer 会怎么分类
# 从 _pending 里看就是最终分类结果
delete_type = delete_events[-1].event_type if delete_events else "NO_EVENT"
results["delete"] = delete_type

eb._pending.clear()  # reset for next test

# ── Test 2: MODIFY ──
print("\n[TEST 2] MODIFY")
m = watch_dir / "to_modify.txt"
m.write_text("v1", encoding="utf-8")
time.sleep(0.1)
pipe.tick()  # baseline

time.sleep(0.12)  # mtime 精度
m.write_text("v2", encoding="utf-8")
time.sleep(0.1)
pipe.tick()

modify_events = [ce for ce in eb._pending if ce.source.name == "FILE_CHANGE"]
print(f"  _pending 中 FILE_CHANGE events: {len(modify_events)}")
for ev in modify_events:
    print(f"    event_type={ev.event_type}  summary={ev.summary}")

modify_type = modify_events[-1].event_type if modify_events else "NO_EVENT"
results["modify"] = modify_type

eb._pending.clear()

# ── Test 3: CREATE (新文件) ──
print("\n[TEST 3] CREATE")
c = watch_dir / "to_create.txt"
c.write_text("brand new", encoding="utf-8")
time.sleep(0.1)
pipe.tick()

create_events = [ce for ce in eb._pending if ce.source.name == "FILE_CHANGE"]
print(f"  _pending 中 FILE_CHANGE events: {len(create_events)}")
for ev in create_events:
    print(f"    event_type={ev.event_type}  summary={ev.summary}")

create_type = create_events[-1].event_type if create_events else "NO_EVENT"
results["create"] = create_type

# ── FINAL VERDICT ──
print("\n" + "=" * 70)
print("P3.6 FINAL VERDICT")
print("=" * 70)

expected = {"create": "file_created", "modify": "file_modified", "delete": "file_deleted"}
for op, exp in expected.items():
    got = results.get(op, "NO_EVENT")
    mark = "✅" if got == exp else "❌"
    print(f"  {mark}  {op}: expected={exp}, got={got}")

all_pass = all(results.get(op) == exp for op, exp in expected.items())
print(f"\nP3.6 SEMANTIC FIDELITY: {'✅ ALL PASS — 语义无变形' if all_pass else '❌ FAIL — 存在语义变形'}")

import shutil
shutil.rmtree(wd, ignore_errors=True)
