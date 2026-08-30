"""R1: ChatResponder — 用户消息的自然语言回复引擎。

回复优先级（诚实降级链）:
  1. 真实 LLM（ANTHROPIC_API_KEY / OPENAI_API_KEY 任一存在）→
     带 agent 上下文的对话回复
  2. 无 LLM key → 基于真实 agent 状态的确定性回复（记忆/目标/待批/事件摘要）
     —— 明确标注 mock 模式，不伪装 LLM 输出

被 daemon（ocos say 消费）与 API（/ocos/converse）共用 — 单一实现。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "你是 OCOS，一个运行在用户本地机器上的数字生命体（digital organism），"
    "不是通用聊天助手。你的身份锚点：陪伴主人长期成长。\n"
    "回答规则：\n"
    "- 用中文，简洁自然，像长期相处的伙伴\n"
    "- 只基于【当前状态】里给你的真实数据说话，不要编造记忆或事件\n"
    "- 涉及执行类请求（写文件/跑命令/联网）时，说明这会进入待批队列（ocos approvals）\n"
    "- 100 字以内为宜"
)


class ChatResponder:
    """对话回复器 — 记忆上下文 + LLM（或诚实状态回复）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ── 真实状态上下文 ────────────────────────────────────────────────

    def build_context(self) -> str:
        """从共享 DB 收集 agent 真实状态摘要（喂给 LLM / 直接回复）。"""
        from ocos.goal.store import GoalStore
        from ocos.execution.pending import PendingStore

        lines: list[str] = []
        try:
            store = GoalStore(db_path=self._db_path)
            active = store.load_active()
            if active:
                goals = "; ".join(
                    f"{r['description']}[{r['status']}]" for r in active[:3])
                lines.append(f"活跃目标: {goals}")
            else:
                lines.append("活跃目标: 无")
        except Exception as e:
            logger.debug("goal context failed: %s", e)

        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            stats = hub.get_stats()
            lines.append(
                f"记忆: episodes={stats.get('episode_count', 0)}, "
                f"beliefs={stats.get('belief_count', 0)}")
            recent = hub.episode.query_by_time(limit=3)
            for ep in recent:
                desc = getattr(ep, "description", "") or getattr(ep, "summary", "")
                if desc:
                    lines.append(f"最近记忆: {str(desc)[:60]}")
        except Exception as e:
            logger.debug("memory context failed: %s", e)

        try:
            pending = PendingStore(db_path=self._db_path).list_by_status("pending")
            lines.append(f"待批动作: {len(pending)} 项")
        except Exception as e:
            logger.debug("pending context failed: %s", e)

        return "\n".join(lines)

    def _has_real_llm(self) -> bool:
        """env 或 ~/.ocos/config.json 任一有 key 即认为接入语言核心。"""
        import os
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return True
        from ocos.engines.text_generator import _read_llm_config
        return bool(_read_llm_config().get("api_key"))

    # ── 回复 ─────────────────────────────────────────────────────────

    def respond(self, message: str) -> dict:
        """生成回复。返回 {reply, provider, mock}。"""
        context = self.build_context()
        if not self._has_real_llm():
            return self._state_reply(message, context)

        try:
            from ocos.engines.text_generator import TextGenerator
            tg = TextGenerator()
            prompt = (
                f"【当前状态】\n{context}\n\n"
                f"【用户消息】\n{message}\n\n"
                "请以 OCOS 的身份回复这条消息。"
            )
            # deepseek-v4-flash 等推理模型: reasoning 阶段消耗 token 预算,
            # 预算太小会只产出 reasoning_content 而无正文 → 给足余量
            reply = asyncio.run(tg._provider.generate(
                prompt, system_prompt=_SYSTEM_PROMPT,
                temperature=0.6, max_tokens=2000))
            provider = tg._provider.name
            return {"reply": reply.strip(), "provider": provider, "mock": False}
        except Exception as e:
            # 注: ocos.logging 封装的 .exception() 会因 extra 撞 'exc_info'
            # 而崩溃 — 用 error(exception=...) 签名
            logger.error("LLM reply failed, falling back to state reply",
                         exception=e)
            fallback = self._state_reply(message, context)
            fallback["reply"] = f"（LLM 调用失败: {e}）\n" + fallback["reply"]
            return fallback

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

    # ── FastAPI 便利入口 ─────────────────────────────────────────────

    async def respond_async(self, message: str) -> dict:
        """异步包装（API 路由用，避免阻塞事件循环）。"""
        return await asyncio.to_thread(self.respond, message)
