"""OCOS CLI — run 命令实现（P0：认知引擎生产启动入口）。

`ocos run` 点亮 AgentRuntime 10 步 tick 循环：
  1. 组装真实组件 MasterAgent（非 MagicMock，全部生产实现）
  2. AgentRuntime 挂持久化（默认 ~/.ocos/ocos.db，OCOS_DB_PATH 可覆盖）
  3. ResidentRuntime 常驻 tick 线程（默认每 5s 一次）

用法:
    ocos run                          # 常驻模式，Ctrl-C 优雅退出
    ocos run --ticks 3                # 跑 3 个 tick 后退出
    ocos run --interval 10 --db /tmp/ocos.db

架构约束:
    CLI → ResidentRuntime → AgentRuntime → MasterAgent
    入口不直接操作 Kernel Internal State。
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from ocos.interaction.cli.paths import DEFAULT_DB, resolve_db_path  # AUD-F8: 单一来源


def cmd_run(args, session) -> int:
    """ocos run [--ticks N] [--interval S] [--db PATH] [--agent-id ID]"""
    db_path = resolve_db_path(args.db)
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # P1-B: 单入口建全表 — storage.migrations 为唯一 DDL 编排
    if db_path != ":memory:":
        from ocos.storage.migrations import ensure_schema
        ensure_schema(db_path)

    print(f"OCOS 数字生命 — 点亮认知引擎")
    print(f"  agent_id : {args.agent_id}")
    print(f"  db_path  : {db_path}")
    print(f"  interval : {args.interval}s{'  （跑 %d ticks 后退出）' % args.ticks if args.ticks else ''}")

    from ocos.daemon.factory import build_master_agent

    agent = build_master_agent(args.agent_id)

    from ocos.daemon import ResidentRuntime
    from ocos.daemon.factory import build_health_loop
    from ocos.daemon.factory import build_execution_bridge
    from ocos.daemon.factory import build_knowledge_abi
    from ocos.daemon.factory import build_perception_pipeline

    rt = ResidentRuntime(
        agent,
        tick_interval=args.interval,
        db_path=db_path,
    )
    # R4-A: 决策执行铰链 — 自治决策 → capability_reality 真实执行 (AUTO) / 待批 (ASK)
    rt.attach_decision_bridge(build_execution_bridge(db_path=db_path))
    print("  bridge   : DecisionBridge 已挂载 (AUTO 真实执行 / ASK 待批)")
    print("             审批: 另开终端 ocos approvals list / approve <id>")
    # AUD-F1/PW-5.1: 感知管线 — 默认零传感器；--watch-dir 注入 FileSensor
    watch_dirs = [d.strip() for d in (args.watch_dir or "").split(",") if d.strip()]
    sensors = []
    if watch_dirs:
        try:
            from ocos.perception.file_sensor import FileSensor
            fs = FileSensor()
            for wd in watch_dirs:
                fs.watch_directory(wd)
            sensors.append(fs)
        except Exception as e:
            print(f"  perception: FileSensor 注入失败: {e}")
    rt.attach_perception_pipeline(
        build_perception_pipeline(sensors=sensors, file_semantics=bool(sensors)))
    print(f"  perception: 感知管线已挂载 ({len(sensors)} sensor, "
          f"watch={watch_dirs or '无'})")
    print("  engines  : reasoner/planner/decision/reflection/learning 已注册 (AUD-F9)")
    print("  hint     : 另开终端 — ocos status | ocos say --wait '...' | ocos approvals list")
    print("               Web 聊天: ocos-server 后访问 http://127.0.0.1:8900/ui")
    # GAP-P1-2: 周期健康体检（AlertManager Log+File 通道 → ~/.ocos/alerts/）
    rt.attach_health_loop(build_health_loop())
    rt.start()
    print(f"  runtime  : RUNNING (cycle={rt.cycle_count})")

    # AUD-F1: 知识平面 — boot() 已建 MemoryHub，Registry 镜像落 SemanticStore。
    # knowledge_abi 待 AUD-F9 引擎注册时经引擎 knowledge_abi 构造参数供引擎消费。
    hub = rt.memory_hub
    knowledge_abi = build_knowledge_abi(semantic_store=hub.semantic if hub else None)
    print("  knowledge: KnowledgeRegistry 已启用 (SemanticStore 镜像: %s)"
          % ("on" if hub else "off (no hub)"))

    # 优雅关闭: Ctrl-C → stop()
    stop_event = threading.Event()

    def _on_signal(signum, _frame):
        print(f"\n收到信号 {signum}，优雅关闭中...")
        stop_event.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        if args.ticks and args.ticks > 0:
            # 有限模式: 跑 N 个 tick 后退出
            target = args.ticks
            while rt.cycle_count < target and not stop_event.is_set():
                time.sleep(0.2)
            print(f"完成 {rt.cycle_count} 个 tick。")
        else:
            # 常驻模式: 直到 Ctrl-C
            while not stop_event.is_set():
                time.sleep(0.5)
    finally:
        rt.stop()
        status = rt.get_status()
        print(f"  final    : state={status['state']} cycles={status['cycle']} "
              f"goals_processed={status['processed']}")
        print(f"  db       : {db_path}")
    return 0
