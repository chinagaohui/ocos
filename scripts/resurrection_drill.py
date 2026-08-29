"""GAP-P2-5: 真实"死而复生"演练脚本。

把 living_test/day7_resurrection 的占位钩子替换为真实组件:
  run_ticks   = AgentRuntime.tick（真实 10 步认知循环, stub agent 带 agent_id）
  save_state  = SnapshotManager.save（AgentSnapshot 落 SQLite, 自愈建表）
  kill        = 丢弃内存态（模拟断电）
  restore     = CrashRecovery.recover + IdentitySQLiteStore + MemoryHub.episode
  query_handler = MemoryHub 真实记忆查询

用法:  python scripts/resurrection_drill.py [--ticks N] [--db PATH]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocos.event import RawEvent, EventSource
from ocos.living_test.day7_resurrection import ResurrectionScenario, test_resurrection
from ocos.recovery.crash_recovery import CrashRecovery
from ocos.snapshot.manager import SnapshotManager
from ocos.snapshot.models import AgentSnapshot

RESURRECTION_KEYWORD = "SQLite优先于MySQL"

AGENT_ID = "drill-agent"


class DrillAgent:
    """最小真实 Agent 替身 — 满足 AgentRuntime._init_persistence 的字符串 agent_id 守卫。"""

    agent_id = AGENT_ID
    identity = SimpleNamespace(get_name=lambda: "Drill Agent")

    def boot(self) -> None:
        """AgentRuntime.boot 会调用 agent.boot(); 替身无需额外启动动作。"""
        return

    # 无 goal_stack: _init_persistence 用 hasattr 守卫, 跳过 goal 持久化
    # 无 attach_memory_hub: MemoryHub 由 runtime 持有, drill 直接经 runtime 访问


def build_drill(db_path: str, tick_count: int) -> ResurrectionScenario:
    """装配真实钩子的 ResurrectionScenario。"""

    from ocos.agent.agent_runtime import AgentRuntime, RuntimeState
    from ocos.memory.episode.models import Episode, EpisodeStatus

    runtime: AgentRuntime | None = None

    def run_ticks(n: int) -> list[dict]:
        nonlocal runtime
        # DrillAgent 是结构兼容替身（运行时鸭子类型）, 与 MasterAgent 静态类型不同
        runtime = AgentRuntime(agent=DrillAgent(), db_path=db_path, max_cycles=n + 10)  # type: ignore[arg-type]
        runtime.boot()
        assert runtime.state == RuntimeState.RUNNING
        # 注入一条真实"经历"事件（模拟外部输入）
        runtime.event_bus.push(RawEvent(source=EventSource.TIMER, payload={"content": RESURRECTION_KEYWORD}))
        traces: list[dict] = []
        for _ in range(n):
            traces.append(runtime.tick())
        # 沉淀一段真实长期记忆（MemoryHub.episode 落 SQLite）
        runtime._memory_hub.episode.save(
            Episode(
                id="EPI-drill-1",
                experience_id="EXP-drill-1",
                created_at=datetime.now(timezone.utc),
                decision=RESURRECTION_KEYWORD,
                action="resurrection_drill",
                outcome={"success": True},
                source="reflection",
                status=EpisodeStatus.ACTIVE,
            )
        )
        return traces

    def save_state() -> None:
        assert runtime is not None, "run_ticks 必须先执行"
        snap = AgentSnapshot(
            snapshot_id="drill-resurrection",
            identity_state={"anchor": AGENT_ID},
            runtime_state={"cycle_count": runtime._cycle_count},
        )
        SnapshotManager(db_path).save(snap)

    def kill() -> None:
        nonlocal runtime
        # 模拟断电: 丢弃内存态（runtime 对象销毁, 仅剩 SQLite 落盘数据）
        runtime = None

    def restore() -> dict:
        from ocos.memory.hub import MemoryHub
        from ocos.agent.identity_store import IdentitySQLiteStore
        from ocos.goal.store import GoalStore

        report = CrashRecovery(db_path).recover()
        snap = SnapshotManager(db_path).load_latest()
        # 身份复活: 从 IdentitySQLiteStore 读回真实身份
        identity_store = IdentitySQLiteStore(db_path)
        identity_store.initialize()
        identity = identity_store.load(AGENT_ID)
        # 记忆复活: MemoryHub.episode 读回沉淀的经历
        hub = MemoryHub(db_path)
        hub.initialize()
        episode = hub.episode.get("EPI-drill-1")
        # 目标复活: 从 goal store 读回活跃目标（替身 agent 无 goal 子系统, 真实为空）
        # 注: GoalStore 无 initialize(), _conn() 内自愈建表
        goals = GoalStore(db_path).load_active()
        return {
            "identity": {"anchor": identity.to_dict().get("agent_id", "") if identity else ""},
            "memory": [episode.decision] if episode else [],
            "goals": goals,
            "recovery_report": {
                "checkpoints": report.recovered_checkpoints,
                "replayed": report.replayed_events,
            },
        }

    def query_handler(question: str) -> str:
        from ocos.memory.hub import MemoryHub

        hub = MemoryHub(db_path)
        hub.initialize()
        episode = hub.episode.get("EPI-drill-1")
        if episode is not None:
            return f"复活后仍记得: {episode.decision}"
        return ""

    return ResurrectionScenario(
        pre_death_tick=tick_count,
        pre_death_identity={"anchor": AGENT_ID},
        run_ticks=run_ticks,
        save_state=save_state,
        kill=kill,
        restore=restore,
        query_handler=query_handler,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="OCOS 死而复生演练")
    parser.add_argument("--ticks", type=int, default=3, help="死亡前运行的 tick 数")
    parser.add_argument("--db", type=str, default="", help="SQLite 路径（默认临时文件）")
    args = parser.parse_args()

    db_path = args.db or tempfile.mktemp(suffix=".db", prefix="ocos_drill_")
    sc = build_drill(db_path, args.ticks)
    result = test_resurrection(sc)

    print(f"DB: {db_path}")
    print(f"status={result.status.value}  score={result.score}/{result.max_score}")
    for key, ok in result.sub_results.items():
        print(f"  {'✅' if ok else '❌'} {key}")
    for w in result.warnings:
        print(f"  ⚠ {w}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
