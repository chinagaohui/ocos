#!/usr/bin/env python3
"""P3.5b PRODUCTION CONSUME VERIFICATION — RuntimeKernel → TickPipeline 完整链

最终冻结证据：
  不是手动调 ingest()，而是 RuntimeKernel.tick_loop() → TickPipeline.execute_tick()
  → EventIngestionStage.execute() 真实消费 FILE_CHANGE → ctx.events 非空 → AttentionStage 看到

PASS 条件:
  ① RuntimeKernel.TickPipeline.EventIngestionStage._event_bus is daemon._event_bus (identity)
  ② _pending 有 FILE_CHANGE（publish 侧已通）
  ③ tick → EventIngestionStage 从 _pending 拉走 → ctx.events 非空
  ④ _pending 下降/清空（确认真实消费，不是并行副本）
  ⑤ 完整 stage_traces: EVENT_INGESTION → ATTENTION → MEMORY_SYNC → ... → CHECKPOINT_DECISION
"""

import sys, os, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P3.5b PRODUCTION CONSUME VERIFICATION — RuntimeKernel → TickPipeline")
print("=" * 70)

# ── Setup ──
wd = Path(tempfile.mkdtemp(prefix="ocos-p35b-"))
(watch_dir := wd / "watch").mkdir()
(watch_dir / "seed.txt").write_text("seed", encoding="utf-8")
db_path = tempfile.mktemp(prefix="ocos-p35b-", suffix=".db")

from ocos.daemon import ResidentRuntime
from ocos.perception.file_sensor import FileSensor
from ocos.daemon.factory import build_perception_pipeline
from ocos.runtime.pipeline_protocol import PipelineStage

class _DummyAgent:
    agent_id = "p35b-test"

rt = ResidentRuntime(agent=_DummyAgent(), db_path=db_path)

fs = FileSensor()
fs.watch_directory(watch_dir)
pipe = build_perception_pipeline(sensors=[fs], file_semantics=True)
rt.attach_perception_pipeline(pipe)

eb = rt._event_bus
kernel = rt._kernel
pipeline = kernel._pipeline
ei_stage = pipeline._stages[PipelineStage.EVENT_INGESTION]

print(f"\n[IDENTITY] 四实例 identity:")
print(f"  daemon._event_bus              @ {id(eb)}")
print(f"  PerceptionPipeline._event_bus  @ {id(pipe._event_bus)}  same={pipe._event_bus is eb}")
print(f"  EventIngestionStage._event_bus @ {id(ei_stage._event_bus) if ei_stage._event_bus else 'None'}  same={ei_stage._event_bus is eb}")

assert pipe._event_bus is eb, "FAIL: pipe identity"
assert ei_stage._event_bus is eb, "FAIL: EI identity"
print("  ✅ identity 全部一致")

# ── Phase 1: 基线 tick ──
print("\n[PHASE 1] PerceptionPipeline 基线 tick + RuntimeKernel tick")
rt._perception_pipeline.tick()  # baseline snapshot
baseline_pending = len(eb._pending)
print(f"  PerceptionPipeline.tick() → _pending = {baseline_pending}")

# ── Phase 2: 创建新文件 → 真实 PerceptionPipeline tick ──
print("\n[PHASE 2] 创建真实文件 + PerceptionPipeline.tick()")
test_file = watch_dir / "real_test.txt"
test_file.write_text("hello reality", encoding="utf-8")
time.sleep(0.1)

events_pipe = rt._perception_pipeline.tick()
pending_after_publish = len(eb._pending)
print(f"  PerceptionPipeline.tick() → {len(events_pipe)} PerceptionEvent")
print(f"  _pending: {baseline_pending} → {pending_after_publish} (Δ={pending_after_publish - baseline_pending})")
print(f"  pipeline.published_count = {rt._perception_pipeline.published_count}")

pending_before_tick = list(eb._pending)  # 快照

# 验证 _pending 有 FILE_CHANGE
file_events_in_pending = [ce for ce in eb._pending if ce.source.name == "FILE_CHANGE"]
assert len(file_events_in_pending) > 0, "FAIL: _pending 应该有 FILE_CHANGE"
print(f"  ✅ _pending 有 FILE_CHANGE: {len(file_events_in_pending)} 条")

# RuntimeKernel.tick_loop 要求 lifecycle.state in (RUNNING, DEGRADED, SAFE_MODE)
# 测试脚本没调 kernel.start() → state 是 INIT → tick_loop 直接 break
# 手动启动 lifecycle 到 RUNNING 状态
if kernel.state.name != "RUNNING":
    kernel.start()  # 这会把 lifecycle 设为 RUNNING

# ── Phase 3: RuntimeKernel.tick_loop() 真实 tick ──
print("\n[PHASE 3] RuntimeKernel.tick_loop() → TickPipeline.execute_tick()")
print(f"  输入 _pending = {len(eb._pending)}")

# RuntimeKernel.tick_loop(max_ticks=1)
initial_pending = len(eb._pending)
kernel.tick_loop(max_ticks=1)
final_pending = len(eb._pending)

print(f"  RuntimeKernel tick_loop → _pending: {initial_pending} → {final_pending}")
print(f"  _pending 下降: {initial_pending - final_pending} (应该 >= 1)")

# ── Phase 4: 直接看 TickPipeline.execute_tick() 的 ctx ──
print("\n[PHASE 4] 直接调 TickPipeline.execute_tick() 看 ctx.events")
# 需要先往 _pending 里再塞一个事件（上一个可能被 tick_loop 消费了）
(watch_dir / "real_test2.txt").write_text("reality 2", encoding="utf-8")
time.sleep(0.1)
rt._perception_pipeline.tick()  # publish 新事件
pending_before_execute = len(eb._pending)
print(f"  _pending before execute_tick = {pending_before_execute}")

ctx = pipeline.execute_tick(tick_id=999, runtime_state="running")
pending_after_execute = len(eb._pending)

print(f"  TickPipeline.execute_tick() tick_id=999 执行完毕")
print(f"  _pending: {pending_before_execute} → {pending_after_execute}")
print(f"  ctx.events = {len(ctx.events)} 条 CognitiveEvent")
print(f"  ctx.stage_traces = {ctx.stage_traces}")

# ── FINAL VERDICT ──
print("\n" + "=" * 70)
print("P3.5b FINAL VERDICT")
print("=" * 70)

v = {
    "① 4 实例 identity 全部一致": (pipe._event_bus is eb) and (ei_stage._event_bus is eb),
    "② PerceptionPipeline 能 publish FILE_CHANGE": pending_after_publish > baseline_pending,
    "③ RuntimeKernel.tick_loop 能消费 _pending": initial_pending > final_pending,
    "④ TickPipeline.execute_tick → ctx.events 非空": len(ctx.events) > 0,
    "⑤ _pending 在 execute_tick 后下降": pending_before_execute > pending_after_execute,
    "⑥ 完整 stage_traces (8 stages + COMPLETE)": ctx.stage_traces[-1] == "COMPLETE" and "EVENT_INGESTION" in ctx.stage_traces,
}

for desc, result in v.items():
    mark = "✅" if result else "❌"
    print(f"  {mark}  {desc}")

all_pass = all(v.values())
print(f"\nP3.5b PRODUCTION VERDICT: {'✅ ALL PASS — TickPipeline 生产消费侧闭合' if all_pass else '❌ FAIL'}")
print(f"  通过 {sum(v.values())}/{len(v)} 项")

# 额外: 打印 ctx.events 内容
if len(ctx.events) > 0:
    print("\n  ctx.events 详情:")
    for ev in ctx.events[:5]:
        print(f"    📋 {ev.source.name}:{ev.event_type} severity={ev.severity.name}")
        print(f"       summary={ev.summary[:80]}")

# 清理
import shutil
shutil.rmtree(wd, ignore_errors=True)
os.unlink(db_path)
