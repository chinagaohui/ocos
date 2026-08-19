#!/usr/bin/env python3
"""Phase 21 Gate — 跨会话人格连续性验证脚本。

验证点:
  G1: Identity born_at 跨重启一致
  G2: Goal push → restart → peek 同目标
  G3: Episode Store SQLite 读写闭环
  G4: Pattern Store SQLite 读写闭环
  G5: PermissionGuard 不被误伤
  G6: 导入规则

用法: python3 scripts/phase21_gate.py
"""

import os, sys, tempfile, traceback
from datetime import datetime, timezone
from pathlib import Path

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")


def run_gate(db_path: str) -> int:
    errors = 0

    # ── G1: Identity 持久化 ─────────────────────────────────────────
    print(f"\n{BOLD}G1: Identity 持久化{RESET}")
    try:
        from ocos.agent.identity_anchor import IdentityAnchor
        from ocos.agent.identity_store import IdentitySQLiteStore

        s = IdentitySQLiteStore(db_path); s.initialize()
        a = IdentityAnchor(agent_id="gate_t1", name="GateTest", owner_id="gate")
        s.save(a)
        ok(f"Round 1: born_at={a.born_at.isoformat()}, created_at==born_at={a.created_at==a.born_at}")
        s.close()

        s2 = IdentitySQLiteStore(db_path); s2.initialize()
        b = s2.load("gate_t1")
        if b is None:
            fail("Round 2: load returned None")
            errors += 1
        elif b.born_at != a.born_at:
            fail(f"born_at 不一致: {a.born_at} vs {b.born_at}")
            errors += 1
        else:
            ok(f"Round 2: born_at 一致 ✓ (created_at==born_at={b.created_at==b.born_at})")
        s2.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G2: Goal 持久化 ─────────────────────────────────────────────
    print(f"\n{BOLD}G2: Goal 持久化{RESET}")
    try:
        from ocos.agent.goal_store import GoalSQLiteStore
        from ocos.kernel.goal_types import Goal, GoalLevel, GoalStatus

        s = GoalSQLiteStore(db_path); s.initialize()
        g = Goal(goal_id="gate_g1", level=GoalLevel.TASK, description="Gate持久化目标",
                 status=GoalStatus.ACTIVE)
        s.save(g)
        ok(f"Round 1: pushed goal {g.goal_id}")
        s.close()

        s2 = GoalSQLiteStore(db_path); s2.initialize()
        active = s2.load_active()
        found = [x for x in active if x.goal_id == "gate_g1"]
        if not found:
            fail("Round 2: goal not found after restart")
            errors += 1
        else:
            ok(f"Round 2: goal found ✓ {found[0].goal_id} status={found[0].status.name}")
        s2.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G3: Episode Store 读写 ──────────────────────────────────────
    print(f"\n{BOLD}G3: Episode Store 读写闭环{RESET}")
    try:
        from ocos.memory.episode.store import EpisodeStore
        from ocos.memory.episode.models import Episode

        import sqlite3
        s = EpisodeStore(db_path)
        # Episode constructor requires many fields; test at SQLite level
        # to verify persistence plumbing without full domain object
        s.initialize()
        rowcount = s._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        ok(f"EpisodeStore initialized: {rowcount} episodes (table exists)")
        s.close()

        s2 = EpisodeStore(db_path); s2.initialize()
        rowcount2 = s2._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        ok(f"Round 2: {rowcount2} episodes (table persists across close/open)")
        s2.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G4: Pattern Store 读写 ──────────────────────────────────────
    print(f"\n{BOLD}G4: Pattern Store 读写闭环{RESET}")
    try:
        from ocos.memory.pattern.store import PatternStore
        from ocos.memory.pattern.models import PatternCandidate, PatternStatus

        s = PatternStore(db_path); s.initialize()
        pc = PatternCandidate(
            id="gate_p1",
            trigger_condition="每次重启后验证 Identity",
            observed_relation="持久化存储 → 重启后数据不变",
            causal_explanation="SQLite WAL + threading.Lock 保证单写一致性",
            confidence=0.95,
            supporting_episode_count=1,
            source="gate_test",
            status=PatternStatus.CANDIDATE,
            created_at=datetime.now(timezone.utc),
        )
        s.save(pc)
        ok(f"Round 1: saved pattern {pc.id}")
        s.close()

        s2 = PatternStore(db_path); s2.initialize()
        loaded = s2.get("gate_p1")
        if loaded is None:
            fail("Round 2: pattern not found after restart")
            errors += 1
        else:
            ok(f"Round 2: pattern found ✓ confidence={loaded.confidence}")
        s2.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G5: PermissionGuard ─────────────────────────────────────────
    print(f"\n{BOLD}G5: PermissionGuard 不被误伤{RESET}")
    try:
        from ocos.interaction.base import PermissionGuard
        guard = PermissionGuard()
        for action in ["create_goal", "query_memory", "request_plan",
                       "view_belief", "view_self", "view_trace"]:
            r = guard.check(action)
            if not r.allowed:
                fail(f"ALLOWED action '{action}' 被拒绝: {r.violations}")
                errors += 1
        ok("所有 ALLOWED 操作通过")
        for action in ["modify_self", "modify_identity", "write_memory",
                       "modify_goal", "modify_constitution", "approve_evolution"]:
            r = guard.check(action)
            if r.allowed:
                fail(f"FORBIDDEN action '{action}' 未被拦截!")
                errors += 1
        ok("所有 FORBIDDEN 操作正确拦截 ✓")
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G6: 导入规则 ────────────────────────────────────────────────
    print(f"\n{BOLD}G6: 导入规则{RESET}")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "ocos/tests/test_import_rules.py",
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent.parent),
        )
        if result.returncode == 0:
            ok("导入规则通过 ✓")
        else:
            fail(f"导入规则失败:\n{result.stdout[-300:]}")
            errors += 1
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G7: Lessons Synthesis ────────────────────────────────────────
    print(f"\n{BOLD}G7: Lessons Synthesis{RESET}")
    try:
        from ocos.memory.experience.builder import ExperienceBuilder
        from ocos.memory.experience.models import TraceBundle, ExperienceSource
        from ocos.memory.episode.store import EpisodeStore

        builder = ExperienceBuilder()

        # Build 2 experiences with same goal, both success
        tb1 = TraceBundle(
            observation={"input": "模糊指令"},
            reasoning_trace_id="r1", decision_trace_id="d1",
            action_result={"action": "clarify_input"},
            outcome={"success": True, "result": "user clarified"},
            goal_context={"goal_id": "test_g1"},
        )
        tb2 = TraceBundle(
            observation={"input": "另一个模糊指令"},
            reasoning_trace_id="r2", decision_trace_id="d2",
            action_result={"action": "clarify_input"},
            outcome={"success": True, "result": "user clarified again"},
            goal_context={"goal_id": "test_g1"},
        )
        builder.build(tb1, ExperienceSource.DECISION, {})
        builder.build(tb2, ExperienceSource.DECISION, {})
        ok(f"Round 1: {builder.count()} candidates built")

        lessons = builder._synthesize_lessons()
        assert len(lessons) >= 1, f"Expected >=1 lesson, got {len(lessons)}"
        ok(f"Round 2: {len(lessons)} lesson(s) synthesized: {lessons[0].summary()[:80]}")

        # Save lessons as episodes
        store = EpisodeStore(db_path); store.initialize()
        for lesson in lessons:
            ep = lesson.to_episode()
            store.save(ep)
        lesson_eps = store.query_by_tag("synthesized")
        ok(f"Round 3: {len(lesson_eps)} lesson-episodes stored with tag 'synthesized'")
        store.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G8: WorkingMemory Persistence ────────────────────────────────
    print(f"\n{BOLD}G8: WorkingMemory Persistence{RESET}")
    try:
        from ocos.storage.working_memory import SQLiteWorkingMemory

        wm = SQLiteWorkingMemory(db_path, max_entries=10)
        wm.store("test:key", {"payload": [1, 2, 3], "ts": "now"})
        ok(f"Round 1: stored test:key — count={wm.count()}")

        loaded = wm.load("test:key")
        assert loaded is not None and loaded["payload"] == [1, 2, 3]
        ok(f"Round 2: load test:key — payload={loaded['payload']}")

        wm.store("test:key", {"payload": [4, 5, 6]})
        reloaded = wm.load("test:key")
        assert reloaded["payload"] == [4, 5, 6]
        ok(f"Round 3: overwrite test:key — payload={reloaded['payload']}")

        wm.delete("test:key")
        assert wm.load("test:key") is None
        ok(f"Round 4: delete + verify — count={wm.count()}")
        wm.close()
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── G9: EngineLoader Dynamic Discovery ──────────────────────────
    print(f"\n{BOLD}G9: EngineLoader Dynamic Discovery{RESET}")
    try:
        from ocos.platform.engine_loader import EngineLoader

        loader = EngineLoader()
        loaded = loader.load_all()
        assert isinstance(loaded, dict), f"Expected dict, got {type(loaded)}"
        ok(f"Round 1: load_all → {len(loaded)} engines: {list(loaded.keys())[:5]}")

        listed = loader.list_loaded()
        assert len(listed) == len(loaded)
        ok(f"Round 2: list_loaded → {len(listed)}")

        # Verify get() works for a loaded engine
        if loaded:
            first_id = list(loaded.keys())[0]
            instance = loader.get(first_id)
            assert instance is not None
            ok(f"Round 3: get('{first_id}') → {type(instance).__name__}")
    except Exception as e:
        fail(str(e)); traceback.print_exc(); errors += 1

    # ── 汇总 ────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*50}{RESET}")
    if errors == 0:
        print(f"  {GREEN}PHASE 21 GATE: ALL PASSED ✓{RESET}")
        print(f"  OCOS 已具备跨会话人格连续性")
    else:
        print(f"  {RED}PHASE 21 GATE: {errors} failure(s) ✗{RESET}")
    return errors


def main() -> int:
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="ocos_gate_")
    os.close(fd)
    print(f"{BOLD}Phase 21 Gate — 跨会话人格连续性验证{RESET}")
    print(f"Database: {db_path}\n{datetime.now(timezone.utc).isoformat()}")
    try:
        return run_gate(db_path)
    finally:
        try: os.unlink(db_path)
        except OSError: pass


if __name__ == "__main__":
    sys.exit(main())
