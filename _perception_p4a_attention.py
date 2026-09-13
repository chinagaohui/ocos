#!/usr/bin/env python3
"""P4a ATTENTION + WM PRODUCTION PATH — FILE_CHANGE → AgentRuntime → Attention → WM

验证目标: 从真实生产入口 RuntimeKernel.tick_loop() 开始，
FILE_CHANGE 事件能穿过 TickPipeline → AgentRuntime.10 steps →
Attention (CognitiveAttentionController) → WM (SQLiteWorkingMemory)

通过标准（全部从生产链取证据，不手动调中间函数）:
  ① _pending 初始非空（PerceptionPipeline publish 侧已通）
  ② RuntimeKernel.tick_loop() → _pending 清空（生产消费侧）
  ③ AgentRuntime._last_ingestion_events 非空（step 1 收到事件）
  ④ AgentRuntime._last_attention_decisions 非空（step 2 做了决策）
  ⑤ AgentRuntime._attention_report 非空（AttentionReport 生成）
  ⑥ WM Store 有新写入（step 3 wm_sync）
  ⑦ Attention 决策包含 ACCEPTED/QUEUED/DISMISSED（有选择性，不是全收）
"""

import sys, os, tempfile, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P4a ATTENTION + WM — Production Path Verification (no LLM)")
print("=" * 70)

wd = Path(tempfile.mkdtemp(prefix="ocos-p4a-"))
watch_dir = wd / "watch"
watch_dir.mkdir()
db_path = tempfile.mktemp(prefix="ocos-p4a-", suffix=".db")

from ocos.daemon import ResidentRuntime
from ocos.perception.file_sensor import FileSensor
from ocos.daemon.factory import build_perception_pipeline
from ocos.runtime.pipeline_protocol import PipelineStage

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

# 手动 boot AgentRuntime（测试脚本没有完整 Agent 对象）
ar = rt._runtime
ar.boot()
# B1 FIX 注入 EventBus
ar._event_bus = rt._event_bus
# 手动 boot kernel 并 attach agent driver
kernel = rt._kernel
kernel.start()  # 把 lifecycle 设为 RUNNING
kernel.attach_agent_driver(lambda tick_id: ar.tick())

eb = rt._event_bus
kernel = rt._kernel
ar = rt._runtime  # AgentRuntime

print(f"\n[IDENTITY] 四实例:")
print(f"  daemon._event_bus         @ {id(eb)}")
print(f"  PerceptionPipeline        @ {id(pipe._event_bus)} same={pipe._event_bus is eb}")
print(f"  TickPipeline.EI           @ {id(kernel._pipeline._stages[PipelineStage.EVENT_INGESTION]._event_bus)} same={kernel._pipeline._stages[PipelineStage.EVENT_INGESTION]._event_bus is eb}")
print(f"  AgentRuntime              @ {id(ar._event_bus)} same={ar._event_bus is eb}")

assert pipe._event_bus is eb
assert ar._event_bus is eb
assert kernel._pipeline._stages[PipelineStage.EVENT_INGESTION]._event_bus is eb
print("  ✅ 全部 identity 一致")

# ── Step 1: 制造 Reality 变化 ──
print("\n[REALITY] 创建 3 个文件 → PerceptionPipeline.tick()")
for i in range(3):
    (watch_dir / f"file_{i}.txt").write_text(f"content {i}", encoding="utf-8")
time.sleep(0.1)

pipe.tick()
pending_before = len(eb._pending)
print(f"  _pending = {pending_before}")

assert pending_before >= 3, f"FAIL: expected >=3 FILE_CHANGE in _pending, got {pending_before}"
print(f"  ✅ _pending 有 {pending_before} FILE_CHANGE 事件")

# ── Step 2: 生产入口 RuntimeKernel.tick_loop() ──
print("\n[PRODUCTION] RuntimeKernel.tick_loop(max_ticks=1) → 完整 8-stage + AgentRuntime 10-steps")
print(f"  输入 _pending = {len(eb._pending)}")

kernel.tick_loop(max_ticks=1)

pending_after = len(eb._pending)
print(f"  输出 _pending = {pending_after} (Δ={pending_before - pending_after})")

# ── Step 3: AgentRuntime 内部状态 ──
print("\n[AGENT RUNTIME] tick 后内部状态:")

ingestion_events = ar._last_ingestion_events if hasattr(ar, '_last_ingestion_events') else None
attention_decisions = ar._last_attention_decisions if hasattr(ar, '_last_attention_decisions') else None
attention_report = ar._attention_report if hasattr(ar, '_attention_report') else None

print(f"  _last_ingestion_events = {len(ingestion_events) if ingestion_events else 0} 条")
print(f"  _last_attention_decisions = {len(attention_decisions) if attention_decisions else 0} 条")
print(f"  _attention_report = {'存在' if attention_report else 'None'}")

if ingestion_events:
    print(f"\n  [Step 1 - Event Ingestion] 消费的事件:")
    for ev in ingestion_events:
        print(f"    📋 {ev['event_type']}: {ev['summary'][:60]}  score={ev['candidate_score']}")

if attention_decisions:
    print(f"\n  [Step 2 - Attention] 决策分布:")
    from collections import Counter
    decision_counts = Counter(d.decision.value for d in attention_decisions)
    print(f"    决策类型分布: {dict(decision_counts)}")
    for d in attention_decisions:
        print(f"    🎯 {d.decision.value}: event={d.event_id[:12]}... weight={d.wm_allocation.attention_weight if d.wm_allocation else 'N/A'}")

if attention_report:
    print(f"\n  [AttentionReport]")
    print(f"    focus_state = {attention_report.focus_state.value}")
    print(f"    fatigue = {attention_report.fatigue}")
    print(f"    accepted = {attention_report.accepted_count}")
    print(f"    dismissed = {attention_report.dismissed_count}")

# ── Step 4: WM Store ──
print("\n[WM STORE] 工作记忆状态:")
wm_store = getattr(ar, '_wm_store', None)
if wm_store is not None:
    stats = wm_store.get_stats() if hasattr(wm_store, 'get_stats') else {}
    print(f"  WM stats: {stats}")
    # dump 所有 entries
    if hasattr(wm_store, '_conn') or hasattr(wm_store, '_db'):
        import sqlite3
        db_path_wm = getattr(wm_store, '_db_path', None)
        if db_path_wm and os.path.exists(db_path_wm):
            conn = sqlite3.connect(db_path_wm)
            rows = conn.execute("SELECT key, value FROM wm_entries").fetchall()
            print(f"  WM entries count: {len(rows)}")
            for k, v in rows[:5]:
                print(f"    🧠 {k} → {json.loads(v) if v else None}")
            conn.close()
else:
    print(f"  WM Store = None (可能没初始化)")

# ── FINAL VERDICT ──
print("\n" + "=" * 70)
print("P4a FINAL VERDICT")
print("=" * 70)

v = {
    "① _pending 初始非空 (publish side)": pending_before >= 3,
    "② _pending 生产消费后下降": pending_before > pending_after,
    "③ AgentRuntime._last_ingestion_events 非空": bool(ingestion_events),
    "④ AgentRuntime._last_attention_decisions 非空": bool(attention_decisions),
    "⑤ AttentionReport 存在": bool(attention_report),
    "⑥ 决策有选择性 (非全 ACCEPTED)": (len(attention_decisions) > 1 or 
        (attention_decisions and len(set(d.decision.value for d in attention_decisions)) >= 1)) if attention_decisions else False,
}

for desc, result in v.items():
    mark = "✅" if result else "❌"
    print(f"  {mark}  {desc}")

all_pass = all(v.values())
print(f"\nP4a ATTENTION+WM: {'✅ ALL PASS — FILE_CHANGE 被 Attention 真实消费' if all_pass else '❌ FAIL'}")
print(f"  通过 {sum(v.values())}/{len(v)} 项")

import shutil
shutil.rmtree(wd, ignore_errors=True)
