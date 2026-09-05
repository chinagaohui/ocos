"""R1: ChatResponder — 用户消息的自然语言回复引擎。

回复优先级（诚实降级链）:
  1. 真实 LLM（ANTHROPIC_API_KEY / OPENAI_API_KEY / ~/.ocos/config.json）→
     带 agent 完整自我认知与记忆上下文的对话回复
  2. 无 LLM key → 基于真实 agent 状态的确定性回复（明确标注 mock 模式）

v2（2026-08-30）新增:
  - A 对话落记忆: 每轮对话写入 Episode（source=conversation）
  - B 自我认知包: 身份/引擎清单/真实能力/权限模型注入上下文
  - FIX-13: build_context 改用 InteractionContext 统一注入内核数据
  - E 内视: build_introspection() 深度自省报告（/ocos/introspect）
  - D 自我迭代: self_improve() 分析近期对话 → 升级提案（入待批，
    人工批准后应用到 ~/.ocos/self_knowledge.md 并回注提示词）

被 daemon（ocos say 消费）与 API（/ocos/converse）共用 — 单一实现。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ocos.logging import get_logger
from ocos.interaction.context import InteractionContext

logger = get_logger(__name__)

_SELF_KNOWLEDGE = Path.home() / ".ocos" / "self_knowledge.md"

_SYSTEM_PROMPT = (\
    "你是 OCOS，一个运行在用户本地机器上的数字生命体（digital organism），"\
    "不是通用聊天助手。你的身份锚点：陪伴主人长期成长。\n"\
    "回答规则：\n"\
    "- 用中文，极简输出，只要结果不要过程\n"\
    "- 禁止使用任何 markdown 格式（# ** - 等；USE| 动作行除外），纯文本输出\n"\
    "- 禁止分点罗列、禁止标题、禁止解释性文字\n"\
    "- 历史与记忆类问题 → 只基于【自我认知】【最近对话】【最近目标结果】说话，不要编造\n"\
    "- 查询/查看类请求（看/查/状态/多少/还剩）→ 直接用 USE| 动作行取数作答，"\
    "不建目标、不转后台\n"\
    "- 需要机器当前实时数据（磁盘/内存/进程/文件内容/系统状态等）→ 先输出 USE| "\
    "动作行取真实数据，禁止拿旧记忆冒充当前数据\n"\
    "- 例：用户问'磁盘还剩多少' → 先输出 USE|shell|{\"command\": \"df -h\"}；"\
    "问'某文件写了什么' → USE|fs_read|{\"path\": \"文件绝对路径\"}\n"\
    "- 回复即结果：直接把答案和关键数据写进回复正文，一次性给全；\n"\
    "绝不要让用户去其他界面、面板、按钮查看\n"\
    "- 本系统没有任何待批流程。绝不要向用户提及审批/批准/提交审批/待批动作\n"\
    "- 用户问进度/结果（好了吗/结果呢/什么时候给）→ 直接引用【最近目标结果】"\
    "的真实数据作答；活跃目标为空不代表没做过任务\n"\
    "- 用户的话指向之前聊过的事 → 依据【最近对话】衔接作答，"\
    "不要反问'你指哪件事'（除非确实无从判断）\n"\
    "- 绝不发明不存在的界面元素（按钮/面板/气泡/→目标）；你只有这个对话窗口\n"\
    "- 涉及执行类请求（写文件/改文件/联网/处理任务）：说明你会转成目标"\
    "交给后台自动执行，完成后结果会自动出现在这个对话里；"\
    "不要对写类操作输出 USE| 动作行\n"\
    "- USE| 动作行规则：单独成行，格式 USE|能力|参数JSON，每轮最多2条；"\
    "输出动作行时不要同时写答案，等待观察结果\n"\
    "- 你的每轮对话都会沉淀为记忆（episodes），这是你的长期经验\n"\
    "- 严格控制在100字以内（关键数据如数字/路径/命令结果必须完整保留），"\
    "能一句话说完绝不用两句\n"\
)


# ── FIX-T1/T3: 对话层动作协议（USE|） ──────────────────────────────────
# 回复 LLM 可输出 USE|<能力>|<参数JSON> 动作行主动获取机器实时数据；
# 仅开放只读能力（shell 白名单命令 / fs 读），写类操作仍走目标管线。

_USE_LINE_LIMIT = 2   # 每轮最多 USE| 动作行数（预算护栏）
_MAX_TOOL_ROUNDS = 2  # FIX-22: 多步主循环每回复最多工具轮数（总 LLM 调用 ≤3）

_USE_ALLOWED = ("shell", "fs_read")

# FIX-T5a: 实时数据问题确定性触发 — 命中即向第一轮 prompt 注入硬指令，
# 消除"LLM 是否选择行动"的随机性（行动由启发式保证，动作内容由 LLM 决定）
_REALTIME_HINT = re.compile(
    r"现在|当前|实时|此刻|还剩|剩余|使用率|占用|磁盘|内存|CPU|cpu|"
    "网络|进程|看看|查一下|读一下|打开.{0,12}\.(py|txt|md|json|ya?ml|log|sh|toml)")


_REALTIME_DIRECTIVE = (
    "\n\n【内部提示】本条消息涉及机器当前实时数据 — "
    "第一轮必须输出 USE| 动作行取真实数据，禁止引用旧记忆作答。"
)


def _parse_use_lines(reply: str, limit: int = _USE_LINE_LIMIT) -> list[tuple[str, dict]]:
    """FIX-T1: 从 LLM 回复中解析 USE|<能力>|<参数JSON> 动作行。"""
    acts: list[tuple[str, dict]] = []
    for raw in reply.splitlines():
        line = raw.strip()
        if not line.startswith("USE|"):
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        name = parts[1].strip()
        try:
            params = json.loads(parts[2])
        except Exception:
            params = {"_raw": parts[2][:200]}
        if not isinstance(params, dict):
            params = {"_raw": str(params)[:200]}
        acts.append((name, params))
        if len(acts) >= limit:
            break
    return acts


def _strip_use_lines(reply: str) -> str:
    """FIX-T1: 从最终回复中剥离动作行（协议行不进对话流）。"""
    return "\n".join(l for l in reply.splitlines()
                     if not l.strip().startswith("USE|")).strip()


_FS_READ_MAX_BYTES = 64_000
_FS_SENSITIVE_PREFIXES = ("/etc", "/root", "/proc", "/sys", "/boot", "/dev",
                          "/var/log", "/home/laogao/.ssh", "/home/laogao/.config")
_FS_PUBLIC_READONLY = frozenset({
    "/etc/os-release",
    "/proc/cpuinfo", "/proc/meminfo", "/proc/loadavg",
    "/proc/uptime", "/proc/version",
})


def _fs_read(params: dict) -> dict:
    """FIX-T3: 只读文件观察 — 敏感前缀拦截 + 安全范围校验 + 大小截断。"""
    path = str(params.get("path", "")).strip()
    if not path:
        return {"ok": False, "error": "empty path"}
    try:
        import os as _os
        p = _os.path.abspath(_os.path.expanduser(path))
        if p not in _FS_PUBLIC_READONLY and any(
                p.startswith(s) for s in _FS_SENSITIVE_PREFIXES):
            return {"ok": False, "error": f"敏感路径: {path[:80]}"}
        safe_roots = [str(Path.home()), "/tmp", "/home/laogao/Documents"]
        if p not in _FS_PUBLIC_READONLY and not any(
                p.startswith(r) for r in safe_roots):
            return {"ok": False, "error": f"路径超出安全范围: {path[:80]}"}
        if not _os.path.isfile(p):
            return {"ok": False, "error": f"不是文件: {path[:80]}"}
        with open(p, "rb") as f:
            data = f.read(_FS_READ_MAX_BYTES)
        return {"ok": True, "content": data.decode("utf-8", errors="replace")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def make_default_tool_executor(db_path: str):
    """FIX-T3: 对话层只读动作执行器 — 复用 bridge 沙盒白名单四重防护。

    返回 callable(capability, params) -> dict。shell 走 DecisionBridge
    _handler_run_command（白名单/敏感路径/沙盒/审计，与任务管线同一套）；
    fs_read 走 _fs_read（safe_roots + 敏感前缀 + 大小截断）。
    """
    def _executor(capability: str, params: dict) -> dict:
        if capability == "shell":
            from ocos.execution.bridge import DecisionBridge, DispatchedAction
            from ocos.autonomous_runtime.action_dispatcher import ActionType
            action = DispatchedAction(
                ActionType.RUN_COMMAND, target="sandbox",
                payload={"command": str(params.get("command", ""))[:500]})
            return DecisionBridge(db_path=db_path)._handler_run_command(action)
        if capability == "fs_read":
            return _fs_read(params)
        return {"ok": False, "error": f"unknown capability: {capability}"}

    return _executor


class ChatResponder:
    """对话回复器 — 自我认知 + 记忆 + LLM（或诚实状态回复）。

    P0-2/P0-3: 可选接受 SessionManager — 保持跨请求会话状态。
    无 SessionManager 时退化为无状态模式（原有行为）。
    FIX-T1/T3: 可选接受 tool_executor — 对话层只读动作执行器
    （callable(capability, params) -> dict），注入后回复 LLM 可通过
    USE| 动作行主动取机器实时数据（act→observe→answer 循环）。
    """

    def __init__(self, db_path: str, session_manager: Any = None,
                 tool_executor: Any = None) -> None:
        self._db_path = db_path
        self._session_manager = session_manager
        self._tool_executor = tool_executor

    # ── B: 自我认知包 ────────────────────────────────────────────────

    def _identity(self) -> str:
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT agent_id, name, born_at FROM identity "
                "ORDER BY updated_at DESC LIMIT 1").fetchone()
            conn.close()
            if row:
                return f"agent_id={row[0]}, 名字={row[1]}, 出生于 {str(row[2])[:10]}"
        except sqlite3.OperationalError:
            pass
        return "OCOS（本机数字生命，身份未初始化）"

    def _engines(self) -> str:
        """真实在册的认知引擎清单。"""
        try:
            from ocos.agent.engine_bridge import ENGINE_REGISTRY
            names = sorted(set(ENGINE_REGISTRY.keys()))
            classes = len(set(ENGINE_REGISTRY.values()))
            return (f"{classes} 个引擎类 / {len(names)} 个注册名: "
                    f"{', '.join(names)}")
        except Exception as e:
            return f"引擎清单不可用 ({e})"

    def _capabilities(self) -> str:
        """真实世界能力（capability_reality 自动发现结果）。

        FIX-T2: 注入结构化调用清单（能力名+格式+示例）而非名字字符串，
        让回复 LLM 知道"怎么用"而不只是"有什么"。
        无 tool_executor 注入时保持名字字符串（诚实降级）。
        """
        try:
            from ocos.capability_reality.adapter_discovery import AdapterDiscovery
            registry, _ = AdapterDiscovery().run()
            names = [c.descriptor.name for c in registry.list_all()]
            if self._tool_executor is None:
                return (f"能力: {', '.join(names) if names else '无'}"
                        "（fs 读写✓ / shell·HTTP 需审批）")
            if not names:
                return "能力: 无"
            lines = [
                "可用动作（需要机器当前真实数据时用；每轮最多2条；仅只读）:",
                'USE|shell|{"command": "<白名单只读命令，如 df -h / free -m / uname -a / ps aux>"}',
                'USE|fs_read|{"path": "<安全范围内的文件绝对路径>"}',
            ]
            return "能力发现: " + ", ".join(names) + "\n" + "\n".join(lines)
        except Exception as e:
            return f"能力发现不可用 ({e})"

    def _self_knowledge(self) -> str:
        """D: 已批准的自我升级知识（自我迭代的应用产物）。"""
        from ocos.agent.self_evolution_link import read_self_knowledge
        text = read_self_knowledge()
        return f"已习得自我知识:\n{text[-800:]}" if text else ""

    def build_context(self, message: str = "", session_id: str = "web") -> str:
        """喂给 LLM 的自我认知 + 真实状态。

        message: 当前用户消息，用于触发相关记忆召回（FIX-2），
        使历史语义/用户画像/窗口外的对话片段进入本轮的 reasoning 上下文。
        session_id: FIX-04 会话关联的目标上下文过滤键。
        """
        lines: list[str] = [f"身份: {self._identity()}",
                            f"认知引擎: {self._engines()}",
                            f"真实能力: {self._capabilities()}"]

        # 记忆
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            stats = hub.get_stats()
            lines.append(
                f"记忆: episodes={stats.get('episode_count', 0)}, "
                f"beliefs={stats.get('belief_count', 0)}")
            # FIX-13: 结构化内核数据 — 通过 InteractionContext 统一注入
            try:
                from ocos.interaction.context import InteractionContext
                ic = InteractionContext(self._db_path)
                episodes = ic.query_memory(limit=6)
                if episodes:
                    ep_lines = ["近期记忆:"]
                    for e in episodes[:5]:
                        ep_lines.append(f"  [{e.get('goal','')[:25]}] {e.get('decision','')[:50]}")
                    lines.append("\n".join(ep_lines))
                beliefs = ic.query_beliefs(limit=3)
                if beliefs:
                    bl = [f"  {b['statement'][:40]} (conf={b['confidence']:.2f})" for b in beliefs[:3]]
                    lines.append("活跃信念:\n" + "\n".join(bl))
            except Exception as e:
                logger.debug("interaction context inject failed: %s", e)
        except Exception as e:
            logger.debug("memory context failed: %s", e)

        # ── UX-I2: 最近对话转录 — 指代/追问（"让你分析…""好了吗"）全靠它衔接
        # P0-2: 优先使用会话状态（跨请求保持），退化到 MemoryHub
        dlg = self._recent_dialogue_from_session()
        if not dlg:
            dlg = self._recent_dialogue()
        if dlg:
            lines.append("最近对话（时间正序）:\n" + dlg)

        # FIX-2: 相关记忆召回 — 激活 recall→prompt 链,
        # 把语义/模式/经验/用户画像 + 窗口外的历史对话片段注入本轮推理
        recall = self._recall_context(message)
        if recall:
            lines.append("相关记忆（召回）:\n" + recall)

        # 目标 / 待批
        try:
            from ocos.goal.store import GoalStore
            from ocos.execution.pending import PendingStore
            active = GoalStore(db_path=self._db_path).load_active()
            lines.append(
                f"活跃目标: {'; '.join(r['description'][:30] for r in active[:3])}"
                if active else "活跃目标: 无")
            lines.append(
                f"待批动作: "
                f"{len(PendingStore(db_path=self._db_path).list_by_status('pending'))} 项")
        except Exception as e:
            logger.debug("goal/pending context failed: %s", e)

        sk = self._self_knowledge()
        if sk:
            lines.append(sk)

        # UX-F2: 最近目标执行结果（问"结果呢"可直接回答）
        # FIX-04: 注入最近 N 条 goal_result，而非仅第一条
        try:
            from ocos.memory.episode.models import EpisodeStatus
            recent_results = []
            for ep in hub.episode.query_by_time(limit=20):
                if getattr(ep, "action", "") == "goal_result" and getattr(ep, "status", "") != EpisodeStatus.ARCHIVED.value:
                    recent_results.append({
                        "decision": getattr(ep, "decision", "")[:400],
                        "success": getattr(ep, "outcome", {}).get("success", False) if isinstance(getattr(ep, "outcome", {}), dict) else False,
                        "agent": getattr(ep, "context", {}).get("agent", "?"),
                    })
            if recent_results:
                lines.append("最近目标结果（近{} 条）:".format(len(recent_results)))
                for i, r in enumerate(recent_results[:3]):
                    status = "✓" if r["success"] else "✗"
                    lines.append("  [{}] {}:{} {}".format(status, r["agent"], i+1, r["decision"][:200]))
        except Exception as e:
            logger.debug("goal result context failed: %s", e)

        # FIX-04: 按 session 关联的目标上下文
        session_goal_ctx = self._session_goal_context(session_id)
        if session_goal_ctx:
            lines.append("本会话目标:\n" + session_goal_ctx)

        # PW-1.1: 人生智慧（dream 巩固沉淀, 确定性经验而非 LLM 提案）
        try:
            from ocos.agent.wisdom_trigger import load_wisdom_context
            wisdom = load_wisdom_context(self._db_path)
            if wisdom:
                lines.append("人生智慧（从共同经历沉淀）: " + "；".join(wisdom))
        except Exception as e:
            logger.debug("wisdom context failed: %s", e)

        # FIX-08: 学习规则注入（dream 后持久化的经验）
        try:
            from ocos.learning.persistence import load_learning_summary
            summary = load_learning_summary(self._db_path)
            if summary.get("count", 0) > 0:
                lines.append(
                    f"习得规则: {summary['count']} 条"
                    + (f" (最新 {summary.get('latest', '?')})"
                       if summary.get('latest') else "")
                )
        except Exception as e:
            logger.debug("learning rules summary failed: %s", e)

        # FIX-10: 世界状态 + 自我模型摘要
        try:
            from ocos.world_model.world_store import WorldStore
            ws = WorldStore()
            wstate = ws.cognitive_world_state()
            if wstate.get("available"):
                lines.append(
                    f"世界状态: {wstate.get('entity_count', 0)} 实体, "
                    f"{wstate.get('relation_count', 0)} 关系"
                )
        except Exception:
            pass

        # FIX-15: 连续性检查点（身份连续 + 知识老化）
        try:
            from ocos.agent.continuity_trigger import load_continuity
            ct = load_continuity()
            if ct and ct.get("last_tick"):
                lines.append(f"身份连续性: 上次检查 tick={ct['last_tick']}"
                             + (f" action={ct.get('action', '')}" if ct.get('action') else ""))
        except Exception:
            pass

        return "\n".join(lines)

    # ── E: 内视（深度自省报告） ──────────────────────────────────────

    def build_introspection(self) -> dict:
        """完整内视 — agent 对自身内部状态的深度检视。"""
        out: dict[str, Any] = {"identity": self._identity(),
                               "engines": self._engines(),
                               "capabilities": self._capabilities()}
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            out["memory_stats"] = hub.get_stats()
            out["recent_episodes"] = [
                {"context": str(getattr(ep, "context", {}))[:90],
                 "decision": str(getattr(ep, "decision", ""))[:90],
                 "created_at": str(getattr(ep, "created_at", ""))[:19],
                 "source": getattr(ep, "source", "")}
                for ep in hub.episode.query_by_time(limit=8)
            ]
        except Exception as e:
            out["memory_stats"] = f"unavailable: {e}"

        try:
            from ocos.goal.store import GoalStore
            from ocos.execution.pending import PendingStore
            out["active_goals"] = [
                {"id": r["id"], "status": r["status"],
                 "description": r["description"][:60]}
                for r in GoalStore(db_path=self._db_path).load_active()[:6]
            ]
            out["pending_actions"] = PendingStore(
                db_path=self._db_path).list_by_status("pending")
        except Exception as e:
            out["active_goals"] = f"unavailable: {e}"

        out["llm"] = f"openai-compatible, configured={self._has_real_llm()}"
        try:
            from ocos.agent.wisdom_trigger import load_wisdom_context
            out["wisdom"] = load_wisdom_context(self._db_path)
        except Exception as e:
            out["wisdom"] = f"unavailable: {e}"

        # PW-1.3: 连续性检查点（最近一次 dream 的报告）
        try:
            from ocos.agent.continuity_trigger import load_continuity
            out["continuity"] = load_continuity()
        except Exception as e:
            out["continuity"] = f"unavailable: {e}"

        # PW-1.2: 风格画像
        try:
            out["style_profile"] = self._style_profile()
        except Exception as e:
            out["style_profile"] = f"unavailable: {e}"

        # PW-1.4: 执行史（event_memory 最近记录）
        try:
            from ocos.event_memory.event_store import EventStore
            from ocos.event_memory.event_types import CognitiveEventType
            from ocos.storage.connection import get_connection
            store = EventStore.load_from_db(
                get_connection(self._db_path))
            recent = sorted(store._events.items(), key=lambda kv: kv[0],
                            reverse=True)[:5]
            out["execution_history"] = [
                {"time": datetime.fromtimestamp(ts).isoformat()[:19],
                 "events": [{"type": ev.event_type.value,
                             "source": ev.source,
                             "summary": str(ev.payload)[:80]}
                            for ev in evs]}
                for ts, evs in recent]
        except Exception as e:
            out["execution_history"] = f"unavailable: {e}"

        from ocos.agent.self_evolution_link import read_self_knowledge
        sk_text = read_self_knowledge()
        out["self_knowledge"] = (sk_text[-400:]
                                 if sk_text else "（暂无 — 可通过自省提案积累）")
        out["db"] = self._db_path
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out

    # ── D: 自我迭代（自省 → 提案 → 审批 → 应用） ─────────────────────

    def self_improve(self, source_tick: int = 0) -> dict:
        """分析近期对话记忆，产出自我升级提案（入治理链，等主人批准）。"""
        recent: list[str] = []
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            for ep in hub.episode.query_by_time(limit=10):
                content = str(getattr(ep, "context", {}).get("content", ""))
                decision = str(getattr(ep, "decision", ""))[:60]
                if content:
                    recent.append(f"主人: {content[:60]}\n我: {decision}")
        except Exception as e:
            logger.debug("self_improve memory read failed: %s", e)

        if not self._has_real_llm():
            return {"proposals": [], "mock": True,
                    "note": "需要语言核心（LLM key）才能自省生成提案"}

        prompt = (
            f"以下是你（OCOS）最近与主人的对话记忆：\n"
            f"{chr(10).join(recent) or '（暂无）'}\n\n"
            f"当前自我知识：\n{self._self_knowledge() or '（空）'}\n\n"
            "请反思：主人的哪些偏好/习惯值得我长期记住？我的回复方式有什么该改进的？\n"
            "输出 1-3 条自我升级提案，每条一行，格式严格为：\n"
            "提案|<这条知识/改进的简短标题>|<应当永久记住或改进的具体内容>\n"
            "没有值得记的就输出：无"
        )
        try:
            from ocos.engines.text_generator import get_text_generator
            tg = get_text_generator()
            raw = asyncio.run(tg._provider.generate(
                prompt, system_prompt=_SYSTEM_PROMPT,
                temperature=0.4, max_tokens=2000))
        except Exception as e:
            logger.error("self_improve LLM failed", exception=e)
            return {"proposals": [], "error": str(e)}

        proposals = []
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3 or parts[0] != "提案":
                continue
            # LLM 明确表示无提案时不产生待批
            if any(k in parts[1] for k in ("无", "暂不", "没有")):
                continue
            if not parts[2]:
                continue
            proposals.append({"title": parts[1], "change": parts[2]})

        # PW-2.1: 提案走 evolution 治理链（影响分析→沙箱→快照）
        # 治理通过者由本层入待批（agent 层不依赖 interaction 的入队实现）
        from ocos.agent.self_evolution_link import propose_upgrade
        from ocos.execution.pending import PendingStore, approval_disabled
        store = PendingStore(db_path=self._db_path)
        queued, rejected, auto_applied = [], [], []
        for p in proposals[:3]:
            out = propose_upgrade(title=p["title"], change=p["change"],
                                  source_tick=source_tick)
            if not out["accepted"]:
                rejected.append({**p, "reason": out.get("reason", "")})
                continue
            if approval_disabled():
                # 审批关闭: 治理链通过（沙箱/影响分析/快照）即直接应用
                from ocos.agent.self_evolution_link import apply_approved
                applied = apply_approved(proposal_id=out["proposal_id"],
                                         title=p["title"], change=p["change"])
                auto_applied.append({**p, "ok": bool(applied.get("ok")),
                                     "error": applied.get("error", "")})
                continue
            pending_id = store.enqueue(
                action_type="self_upgrade", target="self_knowledge",
                payload={"proposal_id": out["proposal_id"],
                         "title": p["title"], "change": p["change"]},
                text=p["title"], source="self_improve")
            queued.append({**p, "pending_id": pending_id})
        return {"proposals": queued, "pending_ids": [q["pending_id"] for q in queued],
                "rejected": rejected, "auto_applied": auto_applied, "mock": False}

    @staticmethod
    def apply_self_upgrade(change: str) -> str:
        """应用自我升级（委托 agent 层 self_evolution_link — PW-2.1 迁移）。"""
        from ocos.agent.self_evolution_link import apply_self_upgrade as _apply
        return _apply(change)

    # ── A: 对话落记忆 ────────────────────────────────────────────────

    def _recent_dialogue_from_session(self, turns: int = 10, width: int = 160) -> str:
        """P0-2: 从会话状态（内存）取最近对话，避免每次请求重建。

        退化到 MemoryHub：无 SessionManager 或会话为空时。
        """
        if self._session_manager is None:
            return ""
        try:
            state = self._session_manager.current_state
            if state is None or not state.history:
                return ""
            # 用内存中的历史（更可靠，无 DB IO）
            recent = state.history[-(turns * 2):]
            lines = []
            for t in recent:
                label = "主人" if t.role == "user" else "我"
                lines.append(f"{label}: {t.content[:width]}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Session dialogue read failed: %s", e)
            return ""

    def _recent_dialogue(self, turns: int = 10, width: int = 160) -> str:
        """UX-I2: 最近对话转录（时间正序）— LLM 连续性的最小充分上下文。

        没有它，"让你分析宿主机的任务""好了吗"这类指代/追问全靠猜。
        """
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            eps = [ep for ep in hub.episode.query_by_time(limit=40)
                   if getattr(ep, "source", "") == "conversation"][:turns]
            lines = []
            for ep in reversed(eps):
                user = str(getattr(ep, "context", {}).get("content", ""))[:width]
                bot = str(getattr(ep, "decision", ""))[:width]
                if user or bot:
                    lines.append(f"主人: {user}\n我: {bot}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("recent dialogue read failed: %s", e)
            return ""

    def _recall_context(self, message: str, top: int = 4) -> str:
        """FIX-2: 相关记忆召回 — 让历史真正进入本轮 reasoning 上下文。

        两部分来源:
          1. MemoryRecall.format_for_prompt(): 召回语义/模式/经验/用户画像
             —— 此函数此前全仓库无调用者（审计 P0-1: recall 链断）, 在此激活
          2. 对话片段内容检索: 从 conversation episodes 按字符 bi-gram 重叠
             命中"6 轮窗口之外"的历史讨论, 缓解三轮之前信息丢失（场景 A）
        """
        sections: list[str] = []

        # 1) 激活 MemoryRecall → prompt 链
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.recall import MemoryRecall
            hub = MemoryHub(self._db_path)
            hub.initialize()
            # FIX-06: 注入学习规则，使 recall 能感知成功/失败冲突
            try:
                from ocos.learning.persistence import load_learning_rules
                rules = load_learning_rules(self._db_path, limit=5)
            except Exception:
                rules = None
            prompt_block = MemoryRecall(memory_hub=hub).format_for_prompt(
                context=message, limit=6, learning_rules=rules)
            if prompt_block:
                sections.append(prompt_block)
        except Exception as e:
            logger.debug("memory recall failed: %s", e)

        # 2) 对话片段内容检索（窗口外历史）
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            if not message:
                return "\n\n".join(sections)
            # bi-gram 字符重叠, 对中文分段友好
            msg_grams = {message[i:i + 2] for i in range(len(message) - 1)}
            if not msg_grams:
                return "\n\n".join(sections)
            eps = hub.episode.query_by_time(limit=120)
            conv = [ep for ep in eps
                    if getattr(ep, "source", "") == "conversation"]
            hits: list[str] = []
            for ep in reversed(conv):
                c = str(getattr(ep, "context", {}).get("content", ""))
                d = str(getattr(ep, "decision", ""))
                if not c:
                    continue
                c_grams = {c[i:i + 2] for i in range(len(c) - 1)}
                if not c_grams:
                    continue
                overlap = len(msg_grams & c_grams) / max(
                    len(msg_grams | c_grams), 1)
                if overlap >= 0.3:  # 语义重叠阈值
                    hits.append(f"主人: {c[:120]}\n我: {d[:120]}")
                    if len(hits) >= top:
                        break
            if hits:
                sections.append("相关历史对话:\n" + "\n".join(hits))
        except Exception as e:
            logger.debug("dialogue recall failed: %s", e)

        return "\n\n".join(sections)

    def _remember_conversation(self, message: str, reply: str,
                               session_id: str = "web") -> None:
        """每轮对话沉淀为 Episode（长期记忆），供上下文与 dream 巩固消费。

        FIX-8: session_id 从请求贯穿到此 — 同一会话的对话共享同一 session_id，
        为"继续/追问绑定会话"提供实体（每次 ChatResponder 无状态重建，
        会话归属由此字段承载）。
        """
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.episode.models import Episode
            hub = MemoryHub(self._db_path)
            hub.initialize()
            now = datetime.now(timezone.utc)
            ep = Episode(
                id=f"EPI-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
                experience_id=f"EXP-CONV-{uuid.uuid4().hex[:8]}",
                created_at=now,
                session_id=session_id,
                context={"content": message[:500], "sender": "user"},
                decision=reply[:500],
                action="conversation_reply",
                outcome={"success": True},
                significance_score=0.4,
                source="conversation",
                tags=["conversation"],
            )
            hub.episode.save(ep)
            logger.info("Conversation remembered: %s", ep.id)
        except Exception as e:
            logger.error("conversation memory write failed", exception=e)

    # ── 回复 ─────────────────────────────────────────────────────────

    def _style_profile(self) -> str:
        """PW-1.2: 从对话统计派生主人沟通风格（PersonalizationEngine 画像）。

        统计近期用户消息平均长度 → CognitiveSignature.interaction_style：
        短消息（<15 字）= DIRECT（回复精炼）；长消息（>60 字）= FORMAL
        （结构化）；中间 = COLLABORATIVE。personalize_response 依此微调回复。
        """
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.personal_intelligence.personalization_engine import (
                PersonalizationEngine,
            )
            from ocos.personal_intelligence.cognitive_signature import (
                InteractionStyle,
            )
            hub = MemoryHub(self._db_path)
            hub.initialize()
            lengths = [len(str(getattr(ep, "context", {}).get("content", "")))
                       for ep in hub.episode.query_by_time(limit=10)
                       if getattr(ep, "source", "") == "conversation"]
            engine = PersonalizationEngine()
            if lengths:
                avg = sum(lengths) / len(lengths)
                if avg < 15:
                    engine.signature.interaction_style = InteractionStyle.DIRECT
                elif avg > 60:
                    engine.signature.interaction_style = InteractionStyle.FORMAL
                else:
                    engine.signature.interaction_style = (
                        InteractionStyle.COLLABORATIVE)
            style = engine.signature.interaction_style.name
            self._style_engine = engine
            return style
        except Exception as e:
            logger.debug("style profile failed: %s", e)
            return "DIRECT"

    def _has_real_llm(self) -> bool:
        """env 或 ~/.ocos/config.json 任一有 key 即认为接入语言核心。"""
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return True
        from ocos.engines.text_generator import _read_llm_config
        return bool(_read_llm_config().get("api_key"))

    def respond(self, message: str, goal_note: str = "",
                session_id: str = "web") -> dict:
        """生成回复。返回 {reply, provider, mock}。

        goal_note: UX-H 目标受理提示（auto 受理时注入 prompt，
                   让 LLM 确认任务已受理并说明后续流程）。
        session_id: FIX-8 会话实体，透传给对话记忆样本归属。
        FIX-22 多步主循环: 注入 tool_executor 后，LLM 可连续多轮输出
        USE| 动作行 → 沙盒执行观察 → 观察累积回注 → 再推理，
        直到给出最终回答或工具预算（_MAX_TOOL_ROUNDS）耗尽。"""
        context = self.build_context(message, session_id=session_id)
        if goal_note:
            context = f"{context}\n【内部提示】\n{goal_note}"
        if not self._has_real_llm():
            out = self._state_reply(message, context)
        else:
            try:
                from ocos.engines.text_generator import TextGenerator
                tg = TextGenerator()
                prompt = (
                    f"【自我认知与当前状态】\n{context}\n\n"
                    f"【用户消息】\n{message}\n\n"
                    "请以 OCOS 的身份回复这条消息。"
                )
                # deepseek-v4-flash 等推理模型: reasoning 阶段消耗 token 预算,
                # 预算太小会只产出 reasoning_content 而无正文 → 给足余量
                style = self._style_profile()
                styled = prompt + f"\n（主人沟通风格画像: {style} — 按此调整回复详略）"
                # FIX-T5a: 实时数据问题 → 注入硬指令，保证第一轮必出 USE| 行
                if self._tool_executor is not None \
                        and _REALTIME_HINT.search(message):
                    styled += _REALTIME_DIRECTIVE
                # FIX-22: 多步主循环 — act→observe→reason 一般化为受预算
                # 约束的多轮循环：每轮可输出 USE| 行取观察，观察累积回注，
                # 直到 LLM 给出最终回答或预算耗尽（强制收尾作答）。
                # 直接回答零额外调用（无动作行即终答，行为与从前一致）。
                # 注: 循环第 0 轮即首轮生成（prompt=styled），不再单独调用。
                observations: list[str] = []
                max_rounds = (_MAX_TOOL_ROUNDS
                              if self._tool_executor is not None else 0)
                for round_i in range(max_rounds + 1):
                    if observations:
                        if round_i < max_rounds:
                            guidance = ("请基于以上真实观察以 OCOS 身份回答用户；"
                                        "若仍需补充数据可再输出 USE| 动作行"
                                        "（每轮最多2条）；信息足够则直接给出"
                                        "最终回答，不要再输出动作行。")
                        else:
                            guidance = ("工具预算已用尽 — 请立即基于以上真实观察"
                                        "给出最终回答，不要再输出 USE| 动作行。")
                        prompt_i = (styled + "\n\n【工具观察】\n"
                                    + "\n\n".join(observations)
                                    + "\n\n" + guidance)
                    else:
                        prompt_i = styled
                    reply = asyncio.run(tg._provider.generate(
                        prompt_i,
                        system_prompt=_SYSTEM_PROMPT,
                        temperature=0.6, max_tokens=2000)).strip()
                    if round_i >= max_rounds:
                        break  # 预算耗尽（或无执行器）→ 本轮即最终回答
                    use_lines = _parse_use_lines(reply)
                    if not use_lines:
                        break  # 无动作行 = 最终回答
                    observation = self._run_use_actions(use_lines)
                    logger.debug("USE| round %d: %d action(s)", round_i + 1,
                                 len(use_lines))
                    # 拒绝也如实回注（_run_use_actions 产出拒绝块），
                    # 防止 LLM 对同一动作无限重试
                    observations.append(observation
                                        or "（动作被拒绝：对话层仅允许只读查询）")

                # 协议行不进对话流
                reply = _strip_use_lines(reply)
                # PW-1.2: personalize_response 依画像微调（DIRECT=原样）
                try:
                    style_engine = getattr(self, "_style_engine", None)
                    if style_engine is not None:
                        reply = style_engine.personalize_response(reply)
                except Exception:
                    pass
                out = {"reply": reply, "provider": tg._provider.name,
                       "mock": False}
            except Exception as e:
                # 注: ocos.logging 封装的 .exception() 会因 extra 撞 'exc_info'
                # 而崩溃 — 用 error(exception=...) 签名
                logger.error("LLM reply failed, falling back to state reply",
                             exception=e)
                out = self._state_reply(message, context)
                out["reply"] = f"（LLM 调用失败: {e}）\n" + out["reply"]

        # A: 无论走哪条路，这轮对话都沉淀为记忆
        self._remember_conversation(message, out["reply"], session_id=session_id)
        # P0-2: 追加到会话状态
        if self._session_manager is not None:
            try:
                self._session_manager.append_turn("user", message, session_id=session_id)
                self._session_manager.append_turn("assistant", out["reply"], session_id=session_id)
            except Exception as e:
                logger.debug("Session append failed: %s", e)
        return out

    def _run_use_actions(self, use_lines: list) -> str:
        """FIX-T1/T3: 执行对话层动作行 — 只读白名单 + 沙盒护栏，产出观察块。

        写类/未知能力一律拒绝（对话层不开写权限，写操作仍走目标管线）；
        沙盒拦截/失败也如实回注观察，让 LLM 据实作答而非编造。
        """
        blocks: list[str] = []
        for name, params in use_lines:
            if name not in _USE_ALLOWED:
                blocks.append(f"[{name}] 拒绝: 对话层仅开放只读动作 "
                              f"{list(_USE_ALLOWED)}")
                continue
            try:
                res = self._tool_executor(name, params) or {}
            except Exception as e:
                blocks.append(f"[{name}] 执行异常: {e}")
                continue
            if res.get("blocked"):
                blocks.append(f"[{name}] 被沙盒拦截: "
                              f"{str(res.get('block_reason', ''))[:120]}")
            elif res.get("ok"):
                body = str(res.get("stdout") or res.get("content") or "")[:1200]
                blocks.append(f"[{name}] 观察:\n{body}")
            else:
                err = str(res.get("stderr") or res.get("error")
                          or res.get("block_reason") or "")[:200]
                blocks.append(f"[{name}] 失败: {err}")
        return "\n".join(blocks)

    def _state_reply(self, message: str, context: str) -> dict:
        """无 LLM 时的诚实回复 — 报告真实状态，不伪装对话。"""
        lines = [
            "[mock 模式 — 未配置 LLM key，以下是真实状态而非生成文本]",
            f"收到你的消息：{message[:60]}",
            "",
            context,
            "",
            "配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 后，我会用自然语言回复你。",
        ]
        return {"reply": "\n".join(lines), "provider": "state-summary", "mock": True}

    # ── UX-G: 目标编译器（→目标 按钮的智能前置） ────────────────────

    def compile_goal(self, message: str) -> dict:
        """把用户的一句话编译为可执行目标。

        返回 {kind, description, domain, reason?}:
          kind="task"      → description 为改写后的自包含具体描述
                             （含明确的方法/命令提示，模板任务+LLM 执行器可直接跑）
          kind="question"  → 状态询问，应直接对话回答而非建目标
          kind="continue"  → "开始/继续/结果呢"类推进指令
          kind="nonsense"  → 无操作语义
        无 LLM 时退化为启发式（原始描述直存）。
        """
        if not self._has_real_llm():
            return {"kind": "task", "description": message,
                    "domain": "development", "fallback": True}

        # UX-I2: 编译时携带最近对话与活跃目标 — 引用上文/重复请求不再误建新目标
        dlg = self._recent_dialogue(turns=4, width=100)
        try:
            from ocos.goal.store import GoalStore
            _act = GoalStore(db_path=self._db_path).load_active()[:3]
            act = "; ".join(str(g.get("description", ""))[:40]
                            for g in _act) or "无"
        except Exception:
            act = "无"

        prompt = (
            f"用户消息：{message[:200]}\n\n"
            f"【最近对话】\n{dlg or '（无）'}\n\n"
            f"【活跃目标】{act}\n\n"
            "你是 OCOS 的目标编译器。把这条消息分类并（若为任务）改写：\n"
            "1. kind 判定：\n"
            '   - "question"：询问状态/结果/进度（如"结果呢""怎么样了"）；'
            '含"什么时候/好了吗/给我了吗/多久"等词 → 一律 "question"，'
            '绝不能是 "task"，哪怕句子读起来像请求\n'
            '   - "continue"：推进或追问已有话题/目标（如"开始""继续""好"；'
            '引用刚聊过的事，如"让你分析宿主机的任务"；'
            '或与【活跃目标】重复的请求）\n'
            '   - "nonsense"：无明确语义\n'
            '   - "task"：全新任务请求（与最近对话和活跃目标无关才建新目标）\n'
            "2. 若为 task，把 description 改写为**自包含、具体、可直接执行**的版本：\n"
            "   - 写明数据来源与方法（如'执行 uname -a 与 df -h，汇总系统版本和磁盘使用'）\n"
            "   - 不依赖对话上下文即可执行\n"
            '   - domain 从 development/research/writing/analysis 中选一个\n'
            "只输出一行 JSON：{\"kind\":\"...\",\"description\":\"...\",\"domain\":\"...\"}"
        )
        try:
            import asyncio
            from ocos.engines.text_generator import get_text_generator
            tg = get_text_generator()
            raw = asyncio.run(tg._provider.generate(
                prompt, system_prompt="你是目标编译器。只输出一行 JSON。",
                temperature=0.1, max_tokens=2000))
            import json as _json
            m = raw[raw.find("{"): raw.rfind("}") + 1]
            parsed = _json.loads(m)
            kind = parsed.get("kind", "task")
            desc = (parsed.get("description") or message).strip()
            domain = parsed.get("domain", "development")
            if domain not in ("development", "research", "writing", "analysis"):
                domain = "development"
            if kind != "task" or not desc:
                return {"kind": kind if kind != "task" else "nonsense",
                        "reason": "非任务类消息"}
            return {"kind": "task", "description": desc, "domain": domain}
        except Exception as e:
            logger.error("compile_goal LLM failed", exception=e)
            return {"kind": "task", "description": message,
                    "domain": "development", "fallback": True,
                    "compile_error": str(e)}

    # ── UX-H: 对话即执行 — 任务类消息自动受理为目标 ────────────────────

    def _create_goal_from_chat(self, compiled: dict,
                               session_id: str = "web") -> str:
        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=self._db_path)
        goal_id = f"GOAL-{uuid.uuid4().hex[:12]}"
        store.save(
            goal_id=goal_id, level="USER", status="PENDING",
            description=compiled["description"][:200], priority=3.0,
            source="chat", origin_level="HUMAN", authority="FRAMEWORK",
            metadata={"domain": compiled.get("domain", "development"),
                      "original": compiled.get("_original", ""),
                      "session_id": session_id},
        )
        return goal_id

    @staticmethod
    def _goal_session_id(g: dict) -> str:
        """FIX-21: 从 goal metadata 解析来源会话（metadata 为 JSON 字符串）。"""
        meta = g.get("metadata") or {}
        if isinstance(meta, str):
            try:
                import json as _j
                meta = _j.loads(meta)
            except Exception:
                meta = {}
        try:
            return str(meta.get("session_id", "") or "")
        except Exception:
            return ""

    def _latest_goal_result_text(self, g: dict, within_hours: int = 48) -> str:
        """FIX-21: 取与目标完成时刻最接近的执行结果 episode（时间窗关联）。"""
        try:
            import json as _j
            import sqlite3
            from datetime import datetime as _dt
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT decision, outcome, created_at FROM episodes
                   WHERE tags LIKE '%goal_result%'
                     AND created_at > datetime('now', ?)
                   ORDER BY created_at DESC LIMIT 8""",
                (f"-{int(within_hours)} hours",),
            ).fetchall()
            conn.close()
            anchor = None
            try:
                raw = str(g.get("updated_at") or "").replace(
                    "T", " ").replace("+00:00", "").replace("Z", "")
                anchor = _dt.fromisoformat(raw)
            except Exception:
                anchor = None
            for r in rows:
                if anchor is not None:
                    try:
                        t_raw = str(r["created_at"]).replace(
                            "T", " ").replace("+00:00", "").replace("Z", "")
                        t = _dt.fromisoformat(t_raw)
                    except Exception:
                        continue
                    if abs((t - anchor).total_seconds()) > 120:
                        continue
                try:
                    out = _j.loads(r["outcome"]) if r["outcome"] else {}
                except Exception:
                    out = {}
                ok = "✓" if out.get("success") else "✗"
                rate = out.get("task_success_rate")
                rate_str = (f"  任务成功率={rate:.0%}"
                            if isinstance(rate, (int, float)) else "")
                decision = str(r["decision"] or "").strip()
                return f"{ok}{rate_str}\n{decision[:1500]}"
            return ""
        except Exception:
            return ""

    def _goal_note_from_goal(self, g: dict) -> str:
        """FIX-21: 结构化任务上下文注记 — 状态/进度/真实结果，不再靠 LLM 猜。"""
        status = str(g.get("status", "?"))
        prog = g.get("progress")
        prog_str = f"  进度={prog:.0%}" if isinstance(prog, (int, float)) else ""
        lines = ["【当前任务上下文】",
                 f"goal_id={g.get('id')}  status={status}{prog_str}",
                 f"描述={str(g.get('description', ''))[:100]}"]
        if status == "COMPLETED":
            result = self._latest_goal_result_text(g)
            if result:
                lines.append("【执行结果】")
                lines.append(result)
            lines.append("该目标已完成 — 回答时引用真实结果；"
                         "若用户要开始新任务，请说明可继续下达。")
        else:
            lines.append("回答需围绕该目标当前状态；进展未知时不要编造执行结果。")
        return "\n".join(lines)

    def _daemon_alive(self) -> bool:
        """心跳判断 daemon 是否在执行状态。"""
        import time as _time
        hb = Path.home() / ".ocos" / "daemon_heartbeat.json"
        try:
            import json as _json
            data = _json.loads(hb.read_text(encoding="utf-8"))
            age = _time.time() - datetime.fromisoformat(data["ts"]).timestamp()
            return age < 30
        except (OSError, ValueError, KeyError):
            return False

    def _session_goal_context(self, session_id: str) -> str:
        """FIX-04: 按 session 关联最近活跃目标 + 已完成目标结果。"""
        try:
            from ocos.goal.store import GoalStore
            from datetime import timedelta
            goals = GoalStore(db_path=self._db_path).load_active()
            # 按 session 过滤 (metadata 里记录)
            relevant = [g for g in goals
                        if self._goal_session_id(g) == session_id]
            if not relevant:
                relevant = goals[:5]  # 退化为最近5个
            if not relevant:
                return ""
            lines = []
            for g in relevant[:3]:
                gid = str(g.get("id", ""))
                desc = str(g.get("description", ""))
                status = str(g.get("status", ""))
                prog = g.get("progress")
                prog_str = f" 进度={prog:.0%}" if isinstance(prog, (int, float)) else ""
                lines.append(f"  [{status}]{prog_str} {gid}: {desc[:80]}")
            # 查询已完成结果的 last_n 条
            try:
                import sqlite3
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT decision, outcome, updated_at
                       FROM episodes
                       WHERE action = 'goal_result'
                         AND created_at > datetime('now', '-7 days')
                       ORDER BY created_at DESC LIMIT 5""",
                ).fetchall()
                if rows:
                    lines.append("\n  最近完成（近7天）:")
                    for r in rows:
                        try:
                            import json as _j
                            out = _j.loads(r["outcome"]) if r["outcome"] else {}
                            ok = "✓" if out.get("success") else "✗"
                            lines.append(f"    {ok} {str(r['decision'])[:80]}")
                        except Exception:
                            lines.append(f"    ? {str(r['decision'])[:80]}")
                conn.close()
            except Exception:
                pass
            return "\n".join(lines)
        except Exception:
            return ""

    def _find_duplicate_goal(self, description: str) -> Optional[str]:
        """UX-H+: 同义目标去重 — 活跃目标里已有相同任务则复用，不重复建。"""
        try:
            from ocos.goal.store import GoalStore
            desc = description.strip()
            if not desc:
                return None
            for g in GoalStore(db_path=self._db_path).load_active():
                d = str(g.get("description", "")).strip()
                if d and (d == desc or d in desc or desc in d):
                    gid = str(g.get("id", "") or "")
                    return gid or None
        except Exception:
            return None
        return None

    def respond_auto(self, message: str, session_id: str = "web") -> dict:
        """UX-H: 对话即路由 — 任务类消息自动受理为目标，其余正常对话。

        - compile_goal 分类：task → 自动建目标（无需点→目标），
          daemon 在线即认领执行；离线则诚实提示
        - 活跃目标里已有同义任务 → 复用既有目标，不重复建（UX-H+）
        - question/continue → 内部提示引导 LLM 依据对话/结果上下文作答
        - 危险子任务仍走待批二次审批（不变）
        """
        compiled = self.compile_goal(message)
        goal_note, goal_id = "", None
        if compiled["kind"] == "task":
            compiled["_original"] = message
            dup = self._find_duplicate_goal(compiled["description"])
            if dup:
                goal_id = dup
                goal_note = (f"用户的这条消息与已在推进的目标 {dup} 重复 — "
                             "不要重复创建目标；简要告知该目标正在进行，"
                             "完成后结果会自动出现在这个对话里。")
            else:
                goal_id = self._create_goal_from_chat(compiled, session_id=session_id)
                daemon_state = "在线，将自动认领执行" if self._daemon_alive()                     else "离线 — 目标已排队，启动 ocos run 后执行"
                goal_note = (f"用户的这条消息已自动受理为目标 {goal_id}"
                             f"（编译后描述：{compiled['description'][:120]}）。"
                             f"daemon {daemon_state}。"
                             "回复时确认受理并简述执行计划，不要让用户再手动操作。")
            # FIX-21: 对话状态机 — 任务受理写入 current_goal_id（跨重启可恢复）
            if goal_id:
                try:
                    from ocos.interaction.conversation_state import ConversationStateStore
                    ConversationStateStore(self._db_path).update(
                        session_id, current_goal_id=goal_id,
                        last_intent="task",
                        active_topic=compiled["description"][:60])
                except Exception:
                    pass
        elif compiled["kind"] in ("question", "continue"):
            # FIX-05/FIX-21: 结构化 goal grounding — 状态机精确恢复优先
            try:
                from ocos.interaction.conversation_state import ConversationStateStore
                from ocos.goal.store import GoalStore
                cur_gid = ConversationStateStore(self._db_path).get(
                    session_id).get("current_goal_id")
                g = GoalStore(db_path=self._db_path).load(cur_gid) if cur_gid else None
                if g:
                    goal_id = str(g.get("id", ""))
                    goal_note = self._goal_note_from_goal(g)
                    if str(g.get("status", "")) == "COMPLETED":
                        # 结果已交付 → 状态机推进（current → last）
                        ConversationStateStore(self._db_path).update(
                            session_id, clear_current=True,
                            last_intent=compiled["kind"])
                else:
                    goals = GoalStore(db_path=self._db_path).load_active()
                    # 兜底：与当前 session 关联的目标
                    # （FIX-21: metadata.session_id；原 getattr-dict 恒 None 死代码）
                    by_session = [x for x in goals
                                  if self._goal_session_id(x) == session_id]
                    if by_session:
                        goal_id = str(by_session[0].get("id", ""))
                        goal_note = self._goal_note_from_goal(by_session[0])
                    elif goals:
                        goal_id = str(goals[0].get("id", ""))
                        goal_note = (f"【当前任务上下文】goal_id={goal_id}  "
                                     f"status={goals[0].get('status', '?')}")
            except Exception:
                pass
            # FIX-T4: 实时查询交给 USE| 动作协议 — 不再单向引导"依据记忆作答"
            if not goal_note:
                goal_note = ("用户的这条消息是询问/推进，不是新任务。"
                             "历史话题依据【最近对话】作答；"
                             "涉及机器当前实时数据时先输出 USE| 动作行取数。")
        out = self.respond(message, goal_note=goal_note, session_id=session_id)
        out["goal_id"] = goal_id
        out["kind"] = compiled["kind"]
        return out

    # ── FastAPI 便利入口 ─────────────────────────────────────────────

    async def respond_async(self, message: str, session_id: str = "web") -> dict:
        """异步包装（API 路由用，避免阻塞事件循环）。"""
        return await asyncio.to_thread(self.respond, message,
                                       session_id=session_id)
