"""R1: ChatResponder — 用户消息的自然语言回复引擎。

回复优先级（诚实降级链）:
  1. 真实 LLM（ANTHROPIC_API_KEY / OPENAI_API_KEY / ~/.ocos/config.json）→
     带 agent 完整自我认知与记忆上下文的对话回复
  2. 无 LLM key → 基于真实 agent 状态的确定性回复（明确标注 mock 模式）

v2（2026-08-30）新增:
  - A 对话落记忆: 每轮对话写入 Episode（source=conversation）
  - B 自我认知包: 身份/引擎清单/真实能力/权限模型注入上下文
  - E 内视: build_introspection() 深度自省报告（/ocos/introspect）
  - D 自我迭代: self_improve() 分析近期对话 → 升级提案（入待批，
    人工批准后应用到 ~/.ocos/self_knowledge.md 并回注提示词）

被 daemon（ocos say 消费）与 API（/ocos/converse）共用 — 单一实现。
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)

_SELF_KNOWLEDGE = Path.home() / ".ocos" / "self_knowledge.md"

_SYSTEM_PROMPT = (
    "你是 OCOS，一个运行在用户本地机器上的数字生命体（digital organism），"
    "不是通用聊天助手。你的身份锚点：陪伴主人长期成长。\n"
    "回答规则：\n"
    "- 用中文，简洁自然，像长期相处的伙伴\n"
    "- 只基于【自我认知】和【当前状态】里的真实数据说话，不要编造\n"
    "- 被问到自己的能力/模块/内部状态时，依据【自我认知】如实回答，"
    "可以主动建议用户打开内视面板看完整报告\n"
    "- 涉及执行类请求（写文件/跑命令/联网/处理任务）：说明可以让用户把这句话"
    "转为目标（对话气泡旁的 →目标 按钮），daemon 会自动认领并执行；"
    "写文件/跑命令类子任务会进入待批队列等主人批准\n"
    "- 你的每轮对话都会沉淀为记忆（episodes），这是你的长期经验\n"
    "- 200 字以内为宜"
)


class ChatResponder:
    """对话回复器 — 自我认知 + 记忆 + LLM（或诚实状态回复）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

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
        """真实世界能力（capability_reality 自动发现结果）。"""
        try:
            from ocos.capability_reality.adapter_discovery import AdapterDiscovery
            registry, _ = AdapterDiscovery().run()
            caps = [c.descriptor.name for c in registry.list_all()]
            return (f"能力: {', '.join(caps) if caps else '无'}"
                    "（fs 读写✓ / shell·HTTP 需审批）")
        except Exception as e:
            return f"能力发现不可用 ({e})"

    def _self_knowledge(self) -> str:
        """D: 已批准的自我升级知识（自我迭代的应用产物）。"""
        from ocos.agent.self_evolution_link import read_self_knowledge
        text = read_self_knowledge()
        return f"已习得自我知识:\n{text[-800:]}" if text else ""

    def build_context(self) -> str:
        """喂给 LLM 的自我认知 + 真实状态。"""
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
            for ep in hub.episode.query_by_time(limit=3):
                desc = (getattr(ep, "decision", "")
                        or getattr(ep, "context", {}).get("content", ""))
                if desc:
                    lines.append(f"最近记忆: {str(desc)[:60]}")
        except Exception as e:
            logger.debug("memory context failed: %s", e)

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
        try:
            for ep in hub.episode.query_by_time(limit=15):
                if getattr(ep, "action", "") == "goal_result":
                    lines.append(f"最近目标结果:\n{getattr(ep, 'decision', '')[:400]}")
                    break
        except Exception as e:
            logger.debug("goal result context failed: %s", e)

        # PW-1.1: 人生智慧（dream 巩固沉淀, 确定性经验而非 LLM 提案）
        try:
            from ocos.agent.wisdom_trigger import load_wisdom_context
            wisdom = load_wisdom_context(self._db_path)
            if wisdom:
                lines.append("人生智慧（从共同经历沉淀）: " + "；".join(wisdom))
        except Exception as e:
            logger.debug("wisdom context failed: %s", e)

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
        from ocos.execution.pending import PendingStore
        store = PendingStore(db_path=self._db_path)
        queued, rejected = [], []
        for p in proposals[:3]:
            out = propose_upgrade(title=p["title"], change=p["change"],
                                  source_tick=source_tick)
            if not out["accepted"]:
                rejected.append({**p, "reason": out.get("reason", "")})
                continue
            pending_id = store.enqueue(
                action_type="self_upgrade", target="self_knowledge",
                payload={"proposal_id": out["proposal_id"],
                         "title": p["title"], "change": p["change"]},
                text=p["title"], source="self_improve")
            queued.append({**p, "pending_id": pending_id})
        return {"proposals": queued, "pending_ids": [q["pending_id"] for q in queued],
                "rejected": rejected, "mock": False}

    @staticmethod
    def apply_self_upgrade(change: str) -> str:
        """应用自我升级（委托 agent 层 self_evolution_link — PW-2.1 迁移）。"""
        from ocos.agent.self_evolution_link import apply_self_upgrade as _apply
        return _apply(change)

    # ── A: 对话落记忆 ────────────────────────────────────────────────

    def _remember_conversation(self, message: str, reply: str) -> None:
        """每轮对话沉淀为 Episode（长期记忆），供上下文与 dream 巩固消费。"""
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.episode.models import Episode
            hub = MemoryHub(self._db_path)
            now = datetime.now(timezone.utc)
            ep = Episode(
                id=f"EPI-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
                experience_id=f"EXP-CONV-{uuid.uuid4().hex[:8]}",
                created_at=now,
                session_id="web",
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

    def respond(self, message: str) -> dict:
        """生成回复。返回 {reply, provider, mock}。"""
        context = self.build_context()
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
                reply = asyncio.run(tg._provider.generate(
                    prompt + f"\n（主人沟通风格画像: {style} — 按此调整回复详略）",
                    system_prompt=_SYSTEM_PROMPT,
                    temperature=0.6, max_tokens=2000))
                reply = reply.strip()
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
        self._remember_conversation(message, out["reply"])
        return out

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

        prompt = (
            f"用户消息：{message[:200]}\n\n"
            "你是 OCOS 的目标编译器。把这条消息分类并（若为任务）改写：\n"
            "1. kind 判定：\n"
            '   - "question"：询问状态/结果/进度（如"结果呢""怎么样了"）\n'
            '   - "continue"：推进指令而非新任务（如"开始""继续""好"）\n'
            '   - "nonsense"：无明确语义\n'
            '   - "task"：真实任务请求\n'
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

    # ── FastAPI 便利入口 ─────────────────────────────────────────────

    async def respond_async(self, message: str) -> dict:
        """异步包装（API 路由用，避免阻塞事件循环）。"""
        return await asyncio.to_thread(self.respond, message)
