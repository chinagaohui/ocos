#!/usr/bin/env python3
"""Perception P3 Validation — FileSensor Observation → CognitiveEvent → perception_bus

验证目标（冻结标准，先写脚本再修代码）：

PATH 3: File Reality → FileSensor → Observation → PerceptionEvent → WorldStore
                  ❌ Observation → CognitiveEvent 断链（三个断点）

PASS 条件：
  (a) FileSensor.poll() 能从真实文件变化产生 Observation           [已存在]
  (b) PerceptionPipeline.tick() 能把 Observation 转成 RawEvent      [需修复]
  (c) RawEvent → EventNormalizer → CognitiveEvent 自动归一化        [已存在]
  (d) CognitiveEvent 进入 perception_bus._pending                   [需修复]
  (e) ingestion 能从 _pending 拉走 CognitiveEvent                  [已存在]
  (f) AttentionController 能对 CognitiveEvent 打分                   [已存在]
  (g) CognitiveEvent 能进入 WM WorkingMemory                        [需验证]

验证步骤：
  Phase A: 创建 watch_dir → 注册 FileSensor → tick()
  Phase B: 创建测试文件 → tick() → 检查 _pending 有 CognitiveEvent
  Phase C: 修改测试文件 → tick() → 检查 _pending 有新 CognitiveEvent
  Phase D: ingest() → Attention → WM → 检查 WM 有文件 Observation 条目
  Phase E: 清理

不依赖 daemon、不依赖 LLM、纯链路验证。
"""

import sys
import os
import tempfile
import time
from pathlib import Path

# ── 环境 ──
sys.path.insert(0, str(Path(__file__).parent))
USE_VENV = Path(".venv/bin/python3").exists()

print("=" * 70)
print("PERCEPTION P3 VALIDATION — FileSensor → CognitiveEvent → perception_bus")
print("=" * 70)

# ── 导入 ──
from ocos.perception.file_sensor import FileSensor
from ocos.perception.pipeline import PerceptionPipeline
from ocos.perception_bus import EventBus, EventSource, EventSeverity
from ocos.perception.sensor_types import SensorModality, ObservationType, Observation

# ── 测试准备 ──
watch_dir = Path(tempfile.mkdtemp(prefix="ocos-p3-watch-"))
print(f"\n[SETUP] watch_dir = {watch_dir}")
print(f"[SETUP] watch_dir 初始文件: {list(watch_dir.iterdir())}")

# 创建初始文件让 FileSensor 有 baseline
(watch_dir / "baseline.txt").write_text("baseline content", encoding="utf-8")

# ── 实例化组件 ──
# EventBus (perception_bus)
event_bus = EventBus()

# FileSensor
file_sensor = FileSensor()
file_sensor.watch_directory(watch_dir)

# PerceptionPipeline（当前实现: 只写 WorldStore，不 publish EventBus）
# 我们传 event_bus 进去——这是修复点要实现的接口
try:
    pipeline = PerceptionPipeline()
    # 尝试注入 event_bus（修复后这会成功）
    if hasattr(pipeline, 'set_event_bus'):
        pipeline.set_event_bus(event_bus)
        print("[SETUP] pipeline.set_event_bus() — ✅ 有接口")
    elif hasattr(pipeline, '_event_bus'):
        pipeline._event_bus = event_bus
        print("[SETUP] pipeline._event_bus = event_bus — ✅ 手动注入")
    else:
        print("[SETUP] pipeline 没有 set_event_bus / _event_bus — ❌ 修复点尚未实现")
except Exception as e:
    print(f"[SETUP] pipeline init 失败: {e}")
    sys.exit(1)

pipeline.register_sensor(file_sensor)

print(f"[SETUP] EventBus._pending 初始: {len(event_bus._pending)} 条")

# ======================================================================
# PHASE A: 基线 tick（应该产生 baseline.txt 的初始观察，不是变化）
# ======================================================================
print("\n" + "─" * 70)
print("PHASE A: 基线 tick")
print("─" * 70)

events_a = pipeline.tick()
print(f"[PHASE A] PerceptionPipeline.tick() 返回 {len(events_a)} 条 PerceptionEvent")
for ev in events_a[:3]:
    obs = ev.observation
    if obs:
        print(f"  ├ Observation: modality={obs.modality}, type={obs.type}, content={obs.content}")
    else:
        print(f"  ├ PerceptionEvent: type={ev.type}, sensor={ev.sensor_name}")

pending_a = len(event_bus._pending)
print(f"[PHASE A] EventBus._pending = {pending_a} 条")

# ======================================================================
# PHASE B: 创建新文件 → 应该产生 FILE_CHANGE CognitiveEvent
# ======================================================================
print("\n" + "─" * 70)
print("PHASE B: 创建新文件 test.txt")
print("─" * 70)

# 确保 FileSensor 的 baseline 已建立（A tick 后 snapshot 里有 baseline.txt）
# 先 sleep 一下让时间戳不同
time.sleep(0.1)

# 创建新文件
test_file = watch_dir / "test.txt"
test_file.write_text("hello world", encoding="utf-8")
print(f"[PHASE B] 创建 {test_file} → size={test_file.stat().st_size}")

# tick
events_b = pipeline.tick()
print(f"[PHASE B] PerceptionPipeline.tick() 返回 {len(events_b)} 条 PerceptionEvent")
for ev in events_b:
    obs = ev.observation
    if obs and isinstance(obs.content, dict):
        print(f"  ├ Observation: path={obs.content.get('path')}, change={obs.content.get('change')}")
    else:
        print(f"  ├ Observation (no content dict)")

pending_b_before = pending_a
pending_b = len(event_bus._pending)
print(f"[PHASE B] EventBus._pending: {pending_b_before} → {pending_b} (Δ={pending_b - pending_b_before})")

# 检查 _pending 里有没有 FILE_CHANGE 类型的 CognitiveEvent
cognitive_types = []
for ce in event_bus._pending:
    cognitive_types.append(f"{ce.source.name}:{ce.event_type}")
print(f"[PHASE B] _pending 内容: {cognitive_types}")

has_file_create = any("file_created" in ct or "FILE_CHANGE" in ct for ct in cognitive_types)
print(f"[PHASE B] 包含 FILE_CHANGE CognitiveEvent: {has_file_create}")

# ======================================================================
# PHASE C: 修改文件 → 应该产生 file_modified CognitiveEvent
# ======================================================================
print("\n" + "─" * 70)
print("PHASE C: 修改 test.txt")
print("─" * 70)

time.sleep(0.1)
test_file.write_text("hello world MODIFIED", encoding="utf-8")
print(f"[PHASE C] 修改 {test_file} → new size={test_file.stat().st_size}")

events_c = pipeline.tick()
pending_c_before = pending_b
pending_c = len(event_bus._pending)
print(f"[PHASE C] EventBus._pending: {pending_c_before} → {pending_c} (Δ={pending_c - pending_c_before})")

# ======================================================================
# PHASE D: ingest → Attention → WM
# ======================================================================
print("\n" + "─" * 70)
print("PHASE D: ingest + Attention + WM")
print("─" * 70)

# ingest
ingested = event_bus.ingest(max_events=20)
print(f"[PHASE D] ingest() 拉走 {len(ingested)} 条 CognitiveEvent")
for ce in ingested:
    print(f"  ├ CognitiveEvent: source={ce.source.name}, type={ce.event_type}, severity={ce.severity.name}")
    print(f"    summary={ce.summary[:80]}")
    print(f"    payload={ce.metadata}")

# AttentionController 打分（如果模块可用）
try:
    from ocos.capability.attention import CognitiveAttentionController
    attention = CognitiveAttentionController()
    print(f"[PHASE D] AttentionController 可用 — ✅")
except Exception as e:
    print(f"[PHASE D] AttentionController 不可用: {e}")
    attention = None

# ======================================================================
# FINAL VERDICT
# ======================================================================
print("\n" + "=" * 70)
print("FINAL P3 VERDICT")
print("=" * 70)

checks = {
    "Observation 产生 (FileSensor.poll → Observation)": len(events_b) > 0,
    "PerceptionEvent 产生 (PerceptionEngine.tick)": len(events_b) > 0,
    "WorldStore 写入 (不应该断)": pipeline.accepted_count > 0 or pipeline.rejected_count > 0,
    "EventBus._pending 有新事件 (Δ>0)": pending_b > pending_a,
    "包含 FILE_CHANGE CognitiveEvent": has_file_create,
    "ingest() 能拉走事件": len(ingested) > 0,
    "CognitiveEvent.event_type 正确": any("file_" in ce.event_type for ce in ingested),
}

for desc, result in checks.items():
    mark = "✅" if result else "❌"
    print(f"  {mark}  {desc}")

all_pass = all(checks.values())
print(f"\nP3 VERDICT: {'✅ ALL PASS' if all_pass else '❌ FAIL — 需要修复断链'}")
print(f"  通过 {sum(checks.values())}/{len(checks)} 项")

# ======================================================================
# 清理
# ======================================================================
import shutil
shutil.rmtree(watch_dir, ignore_errors=True)
print(f"\n[CLEANUP] 删除 watch_dir: {watch_dir}")
