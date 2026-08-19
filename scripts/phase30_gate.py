#!/usr/bin/env python3
"""Phase 30 Gate — Attention Model (v0.1)

验证:
  G1: pytest 全量 0 failed
  G2: shift_focus / release_focus / queue
  G3: fatigue accumulate + recover
  G4: auto_mode fatigue→mode降级
  G5: calculate_priority
  G6: lifecycle mode mapping
  G7: snapshot
  G8: Import rules
"""
import os, sys, subprocess

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"
results: dict[str, str] = {}

def gate(name: str, condition: bool, detail: str = ""):
    status = f"{GREEN}PASS{RESET}" if condition else f"{RED}FAIL{RESET}"
    results[name] = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}  {detail}")

print(f"{YELLOW}Phase 30 Gate — Attention Model{RESET}")
print("-" * 60)

# G1
p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=line"], cwd=PROJECT,
                   capture_output=True, text=True, timeout=120)
gate("G1: pytest (0 failed)",
     p.returncode == 0 and " failed" not in " ".join(p.stdout.splitlines()[-2:]),
     f"{'...'.join(p.stdout.strip().splitlines()[-2:])}")

from ocos.capability.attention import (
    AttentionManager, AttentionMode, FocusTarget, QueueItem, TargetType, AttentionSnapshot,
)

am = AttentionManager()

# G2: focus + queue
am.shift_focus(FocusTarget(TargetType.USER_INPUT, "ui-1", priority=0.9))
gate("G2: shift_focus ok", am.focus is not None and am.focus.target_id == "ui-1")
gate("G2: switch_count=1", am.switch_count == 1)
am.enqueue(QueueItem(item_id="q1", priority=0.8))
am.enqueue(QueueItem(item_id="q2", priority=0.5))
gate("G2: queue_size=2", am.queue_size == 2)
best = am.dequeue_best()
gate("G2: dequeue highest", best.item_id == "q1")
am.release_focus()
gate("G2: release → IDLE", am.mode == AttentionMode.IDLE and am.focus is None)

# G3: fatigue
am2 = AttentionManager()
am2.set_mode(AttentionMode.FOCUSED)
am2.tick(seconds=300)  # 5 min: 5 * 0.02 = 0.10
gate("G3: FOCUSED fatigue > 0.08", am2.fatigue > 0.08)
am2.set_mode(AttentionMode.IDLE)
am2.tick(seconds=120)  # 2 min: 2 * 0.05 = 0.10 recovery
gate("G3: IDLE recovery", am2.fatigue < 0.05)

# G4: auto_mode
am3 = AttentionManager()
am3.set_mode(AttentionMode.FOCUSED)
am3._fatigue = 0.75
m = am3.auto_mode()
gate("G4: fatigue 0.75 → SCANNING", m == AttentionMode.SCANNING)
am3._fatigue = 0.95
m = am3.auto_mode()
gate("G4: fatigue 0.95 → IDLE", m == AttentionMode.IDLE)

# G5: priority
target = FocusTarget(TargetType.GOAL, "g", priority=0.7)
p = am.calculate_priority(target, urgency_boost=1.2, relevance=0.8)
gate("G5: priority calculated", 0.6 < p < 1.0, f"p={p:.3f}")
gate("G5: USER_INPUT base=1.0", FocusTarget(TargetType.USER_INPUT, "x").base_priority == 1.0)
gate("G5: TIMED_EVENT base=0.4", FocusTarget(TargetType.TIMED_EVENT, "x").base_priority == 0.4)

# G6: lifecycle
am4 = AttentionManager()
am4.set_mode_for_lifecycle("WAKE")
gate("G6: WAKE → SCANNING", am4.mode == AttentionMode.SCANNING)
am4.set_mode_for_lifecycle("THINK")
gate("G6: THINK → FOCUSED", am4.mode == AttentionMode.FOCUSED)
am4.set_mode_for_lifecycle("SLEEP")
gate("G6: SLEEP → IDLE", am4.mode == AttentionMode.IDLE)

# G7: snapshot
snap = am4.snapshot()
gate("G7: snapshot type", isinstance(snap, AttentionSnapshot))
gate("G7: mode correct", snap.mode == AttentionMode.IDLE)
gate("G7: fatigue in snapshot", snap.fatigue == am4.fatigue)

# G8
p8 = subprocess.run([sys.executable, "-m", "pytest", "ocos/tests/test_import_rules.py", "-q", "--tb=short"],
                    cwd=PROJECT, capture_output=True, text=True, timeout=60)
gate("G8: Import rules", p8.returncode == 0, f"rc={p8.returncode}")

print("-" * 60)
passed = sum(1 for v in results.values() if v == "PASS")
total = len(results)
print(f"{GREEN if passed==total else RED}{passed}/{total} gates passed{RESET}")
sys.exit(0 if passed == total else 1)
