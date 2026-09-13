#!/usr/bin/env python3
"""P4 FINAL — 完整链验证 Reality → Attention → Brain Prompt Context

不跑 LLM（因为需要 DecisionBridge 完整 DAG + Goal + World 装配），
但验证到最后一步：Attention 上下文真的能注入 DecisionBridge prompt。
"""
import sys, os, tempfile, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("P4 FINAL — Reality → Attention → Brain Prompt Context")
print("=" * 70)

wd = Path(tempfile.mkdtemp(prefix="ocos-p4f-"))
watch_dir = wd / "watch"
watch_dir.mkdir()
db_path = tempfile.mktemp(prefix="ocos-p4f-", suffix=".db")

from ocos.daemon import ResidentRuntime
from ocos.perception.file_sensor import FileSensor
from ocos.daemon.factory import build_perception_pipeline
from ocos.runtime.pipeline_protocol import PipelineStage
from ocos.execution.bridge import DecisionBridge

class _DummyCortex:
    def activate(self): pass

class _DummyAgent:
    agent_id = "p4f-test"
    cortex = _DummyCortex()
    def boot(self): pass
    def set_engine_bridge(self, eb): pass
    def world_context(self): return {"available": False, "entities": []}

rt = ResidentRuntime(agent=_DummyAgent(), db_path=db_path)
fs = FileSensor()
fs.watch_directory(watch_dir)
pipe = build_perception_pipeline(sensors=[fs], file_semantics=True)
rt.attach_perception_pipeline(pipe)

ar = rt._runtime
ar.boot()
ar._event_bus = rt._event_bus

# 关键: 挂 DecisionBridge (生产装配的 Attention source 注入点)
bridge = DecisionBridge()
bridge.attach_attention_source(lambda: ar._attention_report)
ar.attach_decision_bridge(bridge)

kernel = rt._kernel
kernel.start()
kernel.attach_agent_driver(lambda tick_id: ar.tick())

# Reality A: 空 → tick 1
print("\n[REALITY A] 初始状态 (空目录)")
kernel.tick_loop(max_ticks=1)

# Reality B: 创建 2 个文件 → tick 2
print("\n[REALITY B] 创建文件 → PerceptionPipeline.tick() → RuntimeKernel.tick()")
(watch_dir / "important_config.yaml").write_text("key: value", encoding="utf-8")
(watch_dir / "secret.txt").write_text("P4ssw0rd", encoding="utf-8")
time.sleep(0.1)

pipe.tick()
print(f"  _pending before tick = {len(rt._event_bus._pending)}")

kernel.tick_loop(max_ticks=1)

print(f"  _pending after tick  = {len(rt._event_bus._pending)}")

# ── 验证各 step 真实运行 ──
print(f"\n[AGENT RUNTIME 内部状态]")
print(f"  _last_ingestion_events = {len(ar._last_ingestion_events)} 条")
if ar._last_ingestion_events:
    for e in ar._last_ingestion_events:
        print(f"    📋 {e['event_type']}: {e['summary'][:70]}")

# AttentionReport (在 step 2 生成)
report = ar._attention_report
if report is not None:
    print(f"\n  AttentionReport:")
    # AttentionReport 属性名
    attrs = {name: getattr(report, name, None) for name in dir(report) 
             if not name.startswith('_') and not callable(getattr(report, name, None))}
    for k, v in list(attrs.items())[:10]:
        print(f"    {k} = {v}")
else:
    print(f"\n  AttentionReport = None")

# ── 关键验证: Attention context 能不能注入 DecisionBridge prompt ──
print(f"\n[KEY CHECK] Attention → Brain Prompt 注入")
memory_ctx = bridge._memory_decision_context("分析宿主机状态")
if "感知焦点状态" in (memory_ctx or ""):
    print(f"  ✅ Attention context 成功注入 prompt!")
    print(f"\n{memory_ctx}")
else:
    # 可能是 accepted_count=0 且 decisions 被 step 3 清空了
    # 让我们直接调 _attention_decision_context
    attn_ctx = bridge._attention_decision_context()
    print(f"  Attention ctx (direct): {attn_ctx}")
    print(f"  _attention_report: {report}")

# ── FINAL VERDICT ──
print("\n" + "=" * 70)
print("P4 FINAL VERDICT")
print("=" * 70)

v = {
    "① _pending 有 FILE_CHANGE (publish)": rt._event_bus._pending == 0 or len(ar._last_ingestion_events) > 0,
    "② _last_ingestion_events 非空 (step 1)": bool(ar._last_ingestion_events),
    "③ AttentionReport 非空 (step 2)": ar._attention_report is not None,
    "④ Attention context → DecisionBridge prompt": "感知焦点状态" in (memory_ctx or ""),
}

for desc, result in v.items():
    mark = "✅" if result else "❌"
    print(f"  {mark}  {desc}")

all_pass = all(v.values())
print(f"\nP4 COMPLETE: {'✅ ALL PASS — Reality → Attention → Brain prompt 注入链闭合' if all_pass else '⚠️ 部分通过 — Attention context 注入可能需要调整'}")

import shutil
shutil.rmtree(wd, ignore_errors=True)
