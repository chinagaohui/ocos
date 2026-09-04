"""OCOS CLI — 命令行入口配置。"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """构建 OCOS CLI 参数解析器。

    顶层命令:
      ocos goal    — 目标管理
      ocos plan    — 规划请求
      ocos memory  — 记忆查询
      ocos belief  — 信念查询
      ocos self    — 自检查询
      ocos trace   — 决策追踪
    """
    parser = argparse.ArgumentParser(
        prog="ocos",
        description="OCOS Digital Brain — Cognitive Interface Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ocos status                        — 一屏总览（目标/待批/记忆）
  ocos goal create "帮我写一本科幻小说"
  ocos goal status GOAL-abc12345
  ocos plan "分析科幻小说市场趋势"
  ocos run                           — 启动认知引擎（认领目标并执行）
  ocos approvals list                — 查看 ASK 待批动作
  ocos memory query "科幻"
  ocos belief list
  ocos self status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", title="commands")

    # ── goal ──────────────────────────────────────────────────────────
    _add_goal_parser(subparsers)

    # ── plan ──────────────────────────────────────────────────────────
    _add_plan_parser(subparsers)

    # ── memory ────────────────────────────────────────────────────────
    _add_memory_parser(subparsers)

    # ── say/inbox（UX-P2: 对话通道） ─────────────────────────────────
    say = subparsers.add_parser("say", help="Send a message to the running cognitive engine")
    say.add_argument("message", type=str, help="用户消息内容")
    say.add_argument("--wait", action="store_true",
                     help="等待并显示 agent 的回复（需 ocos run 正在运行）")
    say.add_argument("--timeout", type=float, default=60.0,
                     help="--wait 的最长等待秒数（默认 60）")
    say.add_argument("--db", type=str, default="", help="SQLite 路径")
    inbox = subparsers.add_parser("inbox", help="View user message inbox")
    inbox.add_argument("--db", type=str, default="", help="SQLite 路径")

    # ── status（UX-2: 一屏总览） ─────────────────────────────────────
    st = subparsers.add_parser("status", help="One-screen cognitive status overview")
    st.add_argument("--db", type=str, default="",
                    help="SQLite 路径（默认 OCOS_DB_PATH 或 ~/.ocos/ocos.db）")

    # ── approvals（AUD-F12: R4-B 待批队列审批） ───────────────────────
    _add_approvals_parser(subparsers)

    # ── belief ────────────────────────────────────────────────────────
    _add_belief_parser(subparsers)

    # ── self ──────────────────────────────────────────────────────────
    _add_self_parser(subparsers)

    # ── trace ─────────────────────────────────────────────────────────
    _add_trace_parser(subparsers)

    # ── organ（S4：OpenTale 写作器官驱动） ────────────────────────────
    _add_organ_parser(subparsers)

    # ── decide（S5：MasterAgent 真实写作决策） ─────────────────────────
    _add_decide_parser(subparsers)

    # ── regulate（S7：自调节闭环） ─────────────────────────────────────
    _add_regulate_parser(subparsers)

    # ── feedback（S8：评审反馈回流） ────────────────────────────────────
    _add_feedback_parser(subparsers)

    # ── run（P0：认知引擎生产启动入口） ─────────────────────────────────
    _add_run_parser(subparsers)

    # ── chat（TUI交互界面） ───────────────────────────────────────────
    chat = subparsers.add_parser("chat", help="启动TUI交互界面")
    chat.add_argument("--host", type=str, default="localhost",
                      help="API服务器地址 (default: localhost)")
    chat.add_argument("--port", type=int, default=8900,
                      help="API服务器端口 (default: 8900)")
    chat.add_argument("-c", "--continue", dest="continue_", action="store_true",
                      help="恢复最近的会话")
    chat.add_argument("-r", "--resume", type=str, default=None, metavar="ID|TITLE",
                      help="通过 ID 或标题恢复指定会话")
    chat.add_argument("--mouse", action="store_true",
                      help="启用程序内鼠标（默认关闭以保留终端原生选中/复制/粘贴）")

    # ── growth（Phase 50：成长模块 — 外部信号→自我优化） ──────────────
    _add_growth_parser(subparsers)

    return parser


def _add_goal_parser(subparsers: argparse._SubParsersAction) -> None:
    goal = subparsers.add_parser("goal", help="Goal management")
    goal_sub = goal.add_subparsers(dest="goal_action", title="goal subcommands")

    # ocos goal create "text"
    create = goal_sub.add_parser("create", help="Create a new goal")
    create.add_argument("input", type=str, help="Goal description")
    create.add_argument("--domain", type=str, default="writing",
                        choices=["writing", "analysis", "research", "development"],
                        help="Goal domain (default: writing)")
    create.add_argument("--priority", type=int, default=3, choices=[1, 2, 3, 4, 5],
                        help="Priority 1-5 (default: 3)")
    create.add_argument("--constraint", type=str, action="append", default=[],
                        help="Add constraint (repeatable)")

    # ocos goal status <id>
    status = goal_sub.add_parser("status", help="Query goal status")
    status.add_argument("goal_id", type=str, help="Goal ID (e.g. GOAL-abc12345)")

    # ocos goal exec "描述" — Phase 51: 直接执行 (绕过认领)
    exec_p = goal_sub.add_parser(
        "exec", help="直接执行: 描述→LLM分解→沙盒只读执行 (绕过 daemon 认领)")
    exec_p.add_argument("input", type=str, help="Goal description to execute")

    # ocos goal list
    goal_sub.add_parser("list", help="List all goals")


def _add_plan_parser(subparsers: argparse._SubParsersAction) -> None:
    plan = subparsers.add_parser("plan", help="Request a plan")
    plan.add_argument("description", type=str, help="Planning goal description")
    plan.add_argument("--domain", type=str, default="writing",
                      choices=["writing", "analysis", "research", "development"],
                      help="Goal domain (default: writing)")


def _add_memory_parser(subparsers: argparse._SubParsersAction) -> None:
    memory = subparsers.add_parser("memory", help="Query memory")
    memory_sub = memory.add_subparsers(dest="memory_action", title="memory subcommands")

    # ocos memory query "keyword"
    query = memory_sub.add_parser("query", help="Search memory")
    query.add_argument("query", type=str, help="Search keyword or phrase")

    # ocos memory recent
    memory_sub.add_parser("recent", help="Show recent memories")


def _add_approvals_parser(subparsers: argparse._SubParsersAction) -> None:
    approvals = subparsers.add_parser(
        "approvals", help="Review pending ASK actions (R4-B approval queue)")
    approvals_sub = approvals.add_subparsers(dest="approvals_action",
                                             title="approvals subcommands")
    lst = approvals_sub.add_parser("list", help="List pending actions")
    lst.add_argument("--all", action="store_true",
                     help="Include decided/executed entries")
    approve = approvals_sub.add_parser("approve", help="Approve and execute")
    approve.add_argument("pending_id", type=str, help="Pending ID (PEND-xxxxxxxx)")
    deny = approvals_sub.add_parser("deny", help="Deny a pending action")
    deny.add_argument("pending_id", type=str, help="Pending ID (PEND-xxxxxxxx)")


def _add_belief_parser(subparsers: argparse._SubParsersAction) -> None:
    belief = subparsers.add_parser("belief", help="View beliefs")
    belief_sub = belief.add_subparsers(dest="belief_action", title="belief subcommands")

    belief_sub.add_parser("list", help="List all beliefs")
    belief_sub.add_parser("summary", help="Show belief summary")


def _add_self_parser(subparsers: argparse._SubParsersAction) -> None:
    self_p = subparsers.add_parser("self", help="Self inspection and modification")
    self_sub = self_p.add_subparsers(dest="self_action", title="self subcommands")

    # ocos self status
    self_sub.add_parser("status", help="Show self status")

    # ocos self identity
    self_sub.add_parser("identity", help="Show identity boundary")

    # ocos self review — Phase 52: 自省分析 (证据→LLM→报告)
    review = self_sub.add_parser("review", help="自省分析: 采集证据→LLM综合→报告落盘")
    review.add_argument("--db", type=str, default="", help="SQLite 路径")
    review.add_argument("--out", type=str, default="", help="报告输出目录")

    # ocos self mod --file "path" --content "..." --task "description"
    mod = self_sub.add_parser("mod", help="Modify OCOS code (dry-run mode)")
    mod.add_argument("--file", type=str, required=True, help="Target file path (relative to project root)")
    mod.add_argument("--content", type=str, default="", help="New content")
    mod.add_argument("--delete", action="store_true", help="Delete the file instead")
    mod.add_argument("--task", type=str, required=True, help="Task description")
    mod.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    mod.add_argument("--live", action="store_true", help="Execute live (requires approval)")

    # ocos self validate --file "path"
    validate = self_sub.add_parser("validate", help="Validate file path for modification")
    validate.add_argument("--file", type=str, required=True, help="File path to validate")


def _add_trace_parser(subparsers: argparse._SubParsersAction) -> None:
    trace = subparsers.add_parser("trace", help="Decision trace")
    trace_sub = trace.add_subparsers(dest="trace_action", title="trace subcommands")

    show = trace_sub.add_parser("show", help="Show decision trace")
    show.add_argument("trace_id", type=str, help="Trace ID")


def _add_organ_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos organ — OpenTale 写作器官驱动（S4：Organ API 客户端）。"""
    organ = subparsers.add_parser("organ", help="OpenTale Organ API client")
    organ_sub = organ.add_subparsers(dest="organ_action", title="organ subcommands")

    # ocos organ generate "大纲" --title 书名 --genre sci_fi --chapters 10
    gen = organ_sub.add_parser("generate", help="生成新书（支持设定契约）")
    gen.add_argument("content", type=str, help="大纲/创意文本")
    gen.add_argument("--title", type=str, required=True, help="书名")
    gen.add_argument("--genre", type=str, default="general", help="题材")
    gen.add_argument("--chapters", type=int, default=10, help="章数")
    gen.add_argument("--target-words", type=int, default=25000, help="目标字数")
    gen.add_argument("--character", type=str, action="append", default=[],
                     help="角色名（可重复；默认主角）")
    gen.add_argument("--role", type=str, action="append", default=[],
                     help="角色类型 名字=主角 格式（可重复）")
    gen.add_argument("--gender", type=str, action="append", default=[],
                     help="角色性别 名字=男/女 格式（可重复，S8 代词一致性）")
    gen.add_argument("--world", type=str, action="append", default=[],
                     help="世界观约束（可重复）")
    gen.add_argument("--wait", action="store_true", help="轮询至完成")
    gen.add_argument("--base-url", type=str,
                     default="http://127.0.0.1:8000/api/organ", help="Organ API 地址")

    # ocos organ resume 书名
    resume = organ_sub.add_parser("resume", help="续写")
    resume.add_argument("project", type=str, help="书名")
    resume.add_argument("--instruction", type=str, default="", help="指令")
    resume.add_argument("--wait", action="store_true", help="轮询至完成")
    resume.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ rewrite 书名 章号
    rewrite = organ_sub.add_parser("rewrite", help="重写章节")
    rewrite.add_argument("project", type=str, help="书名")
    rewrite.add_argument("chapter", type=int, help="章号")
    rewrite.add_argument("--instruction", type=str, default="", help="指令")
    rewrite.add_argument("--wait", action="store_true", help="轮询至 waiting_confirm")
    rewrite.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ verify 书名
    verify = organ_sub.add_parser("verify", help="校验项目")
    verify.add_argument("project", type=str, help="书名")
    verify.add_argument("--wait", action="store_true")
    verify.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ status
    organ_sub.add_parser("status", help="器官状态快照").add_argument(
        "--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ projects
    organ_sub.add_parser("projects", help="项目列表").add_argument(
        "--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ task <id> --events
    task = organ_sub.add_parser("task", help="任务状态/事件")
    task.add_argument("task_id", type=str, help="任务 ID")
    task.add_argument("--events", action="store_true", help="显示事件流")
    task.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")

    # ocos organ accept <id> / reject <id>
    acc = organ_sub.add_parser("accept", help="采纳草稿（写入项目，高风险）")
    acc.add_argument("task_id", type=str)
    acc.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")
    rej = organ_sub.add_parser("reject", help="拒绝草稿")
    rej.add_argument("task_id", type=str)
    rej.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/organ")


def _add_decide_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos decide — MasterAgent 真实写作决策（S5）。"""
    decide = subparsers.add_parser("decide", help="写作决策（MasterAgent）")
    decide.add_argument("input", type=str, help="大纲/创意文本")
    decide.add_argument("--title", type=str, default="", help="书名")
    decide.add_argument("--genre", type=str, default="general", help="题材")
    decide.add_argument("--chapters", type=int, default=10, help="章数")
    decide.add_argument("--character", type=str, action="append", default=[],
                        help="角色名（可重复；默认主角）")
    decide.add_argument("--role", type=str, action="append", default=[],
                        help="角色类型 名字=主角 格式（可重复）")
    decide.add_argument("--world", type=str, action="append", default=[],
                        help="世界观约束（可重复）")
    decide.add_argument("--focus", type=str, default="",
                        help="重点提示（relationship/conflict/character/world 或中文）")
    decide.add_argument("--tone", type=str, default="",
                        help="基调提示（tension/warmth/melancholy/hope 或中文）")
    decide.add_argument("--pacing", type=str, default="",
                        help="节奏提示（accelerate/maintain/decelerate 或中文）")
    decide.add_argument("--preview", action="store_true", help="预览 Organ 设定契约")
    decide.add_argument("--exec", action="store_true", help="决策后直接提交生成")
    decide.add_argument("--wait", action="store_true", help="--exec 时轮询至完成")
    decide.add_argument("--base-url", type=str,
                        default="http://127.0.0.1:8000/api/organ", help="Organ API 地址")


def _add_regulate_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos regulate — 自调节闭环（S7：TrendAnalyzer → ContractAdjustment）。"""
    reg = subparsers.add_parser("regulate", help="跨章自调节（趋势→契约调整）")
    reg.add_argument("project", type=str, help="书名")
    reg.add_argument("--apply", nargs="?", const=-1, type=int, default=None,
                     help="确认并应用调整到指定章节（省略=当前进度章）")
    reg.add_argument("--yes", action="store_true", help="跳过交互确认（审批链显式授权）")
    reg.add_argument("--max-chapters", type=int, default=40, help="分析最大章节数")
    reg.add_argument("--base-url", type=str,
                     default="http://127.0.0.1:8000/api/organ", help="Organ API 地址")


def _add_feedback_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos feedback — 评审反馈回流（S8 C3）。"""
    fb = subparsers.add_parser("feedback", help="评审反馈回流到 OCOS 记忆")
    fb.add_argument("project", type=str, help="书名")
    fb.add_argument("--base-url", type=str,
                    default="http://127.0.0.1:8000/api/organ", help="Organ API 地址")


def _add_run_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos run — 点亮认知引擎（P0：AgentRuntime 10 步 tick 生产入口）。"""
    run = subparsers.add_parser("run", help="启动认知引擎（常驻 tick 循环）")
    run.add_argument("--ticks", type=int, default=0,
                     help="跑 N 个 tick 后退出（默认 0 = 常驻）")
    run.add_argument("--interval", type=float, default=5.0,
                     help="tick 间隔秒数（默认 5.0）")
    run.add_argument("--db", type=str, default="",
                     help="SQLite 持久化路径（默认 ~/.ocos/ocos.db）")
    run.add_argument("--watch-dir", type=str, default="",
                     help="PW-5.1: 感知监听目录（可多次传入则逗号分隔）")
    run.add_argument("--agent-id", type=str, default="ocos-master",
                     help="Agent ID（默认 ocos-master）")


def _add_growth_parser(subparsers: argparse._SubParsersAction) -> None:
    """ocos growth — 成长模块（Phase 50：外部信号 → 自我优化）。

    子命令:
        ingest  接收外部智能体投递的技术信号 (持久化, 不分析)
        analyze LLM 分析待处理信号 → 优化提案 (只读)
        execute <proposal_id>  执行已分析提案 (受治理自动执行+回滚)
        status  查看执行历史
        grow    一键: ingest → analyze → execute (可 --preview 只预览)
    """
    growth = subparsers.add_parser("growth", help="成长模块: 外部信号→自我优化")
    growth_sub = growth.add_subparsers(dest="growth_action", title="growth subcommands")

    ingest = growth_sub.add_parser("ingest", help="接收外部技术信号")
    ingest.add_argument("--topic", type=str, default="tech-signal", help="信号主题")
    ingest.add_argument("--summary", type=str, required=True,
                        help="信号摘要 (≥60 chars)")
    ingest.add_argument("--source", type=str, default="external", help="投递者标识")
    ingest.add_argument("--url", type=str, default="", help="来源 URL")
    ingest.add_argument("--domain", type=str, default="python", help="技术域")
    ingest.add_argument("--confidence", type=float, default=0.5, help="投递者置信度")

    growth_sub.add_parser("analyze", help="LLM 分析待处理信号 (只读)")

    execute = growth_sub.add_parser(
        "execute", help="执行提案 (自动: 快照→改→测→保留/回滚)")
    execute.add_argument("proposal_id", type=str, help="提案 ID")

    status = growth_sub.add_parser("status", help="成长历史")
    status.add_argument("--limit", type=int, default=20, help="记录条数")

    grow = growth_sub.add_parser(
        "grow", help="一键成长: ingest→analyze→execute")
    grow.add_argument("--topic", type=str, default="tech-signal", help="信号主题")
    grow.add_argument("--summary", type=str, required=True,
                      help="信号摘要 (≥60 chars)")
    grow.add_argument("--source", type=str, default="cli", help="投递者标识")
    grow.add_argument("--url", type=str, default="", help="来源 URL")
    grow.add_argument("--domain", type=str, default="python", help="技术域")
    grow.add_argument("--confidence", type=float, default=0.5, help="置信度")
    grow.add_argument("--preview", action="store_true",
                      help="只分析+展示 diff, 不执行")
