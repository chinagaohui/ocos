"""OCOS WebChat 路由（S6：OCOS 作为主对话入口）。

POST /ocos/chat — 对话消息 → 意图解析 → 写作决策（MasterAgent）→ 响应。
可选执行：--exec 类动作经 Organ API 驱动 OpenTale（ocos 作为大脑调用器官）。

架构约束（老高裁决）：
- OCOS 是入口/大脑：记忆、决策、建议在 OCOS 侧
- OpenTale 是写作器官：执行经 Organ API（HTTP），不 import 内部
- 高风险写作动作返回任务引用，由用户显式确认后执行
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse

router = APIRouter()

# OCOS 会话记忆（进程内；长期记忆归 ocos.memory，此处为 WebChat 会话上下文）
_CHAT_SESSIONS: dict[str, dict[str, Any]] = {}


@router.post("/ocos/chat", tags=["chat"])
async def chat_message(body: dict[str, Any]) -> APIResponse:
    """POST /ocos/chat — WebChat 对话。

    请求: {"session_id": "...", "message": "...", "preferences": {...}}
    响应: {"content": "...", "decision": {...}|None, "suggested": [...]}
    """
    session_id = str(body.get("session_id") or "default")
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message 不能为空")

    session = _CHAT_SESSIONS.setdefault(session_id, {"history": [], "intent": {}})

    # ── 意图解析：写作意图 or 普通对话 ──
    intent = _parse_intent(message, session)

    if intent["kind"] == "writing":
        # 写作意图 → MasterAgent 真实决策
        from ocos.opentale_bridge.master_agent import MasterAgent, WritingIntent

        ma = MasterAgent()
        wi = WritingIntent(
            premise=intent.get("premise") or message,
            title=intent.get("title", "") or "未命名作品",  # U3.5/F-02: 空 title 防护（决策历史不落空书名）
            genre=intent.get("genre", "general"),
            characters=intent.get("characters", []),
            roles=intent.get("roles", {}),
            world=intent.get("world", []),
            total_chapters=intent.get("chapters", 10),
        )
        decision = ma.decide(wi, chapter=1)
        session["intent"] = {"writing_intent": wi, "decision": decision}

        content = (
            f"我理解了你的写作意图。决策如下：\n\n{ma.summary(decision)}\n\n"
            f"回复「开始写」即可通过写作器官（OpenTale）执行生成；"
            f"或告诉我调整重点/基调/角色。"
        )
        suggested = [
            {"label": "开始写", "action": "organ_generate", "title": wi.title or "未命名作品"},
            {"label": "调整基调", "action": "adjust", "field": "tone"},
            {"label": "调整重点", "action": "adjust", "field": "focus"},
        ]
        return APIResponse(success=True, message="ok", data={
            "session_id": session_id,
            "content": content,
            "decision": {
                "focus": decision.primary_focus,
                "tone": decision.emotional_tone,
                "pacing": decision.pacing_directive,
                "chapter_goal": decision.chapter_goal,
                "characters": list(decision.character_instructions.keys()),
                "reasoning": decision.reasoning,
            },
            "suggested": suggested,
        })

    if intent["kind"] == "execute":
        # 「开始写」→ 用已存决策/意图 → Organ API 提交生成
        from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError

        wi = session["intent"].get("writing_intent")
        if wi is None:
            return APIResponse(success=False, message="no_intent", data={
                "content": "还没有写作意图——请先描述你想写的故事。",
            })
        base_url = _organ_base_url()
        client = OrganClient(base_url=base_url)
        try:
            resp = client.generate(
                title=wi.title or "未命名作品",
                content=wi.premise, genre=wi.genre, chapters=wi.total_chapters,
                target_words=wi.total_chapters * 2500,
                characters=list(wi.characters), roles=dict(wi.roles), world=list(wi.world),
            )
        except OrganClientError as e:
            return APIResponse(success=False, message="organ_error", data={
                "content": f"写作器官调用失败: {e}",
            })
        session["pending_task"] = resp["task_id"]
        return APIResponse(success=True, message="ok", data={
            "session_id": session_id,
            "content": f"已通过写作器官提交生成任务（{resp['task_id']}）。\n"
                       f"轮询: {resp['poll']}\n生成完成前可随时查看任务状态。",
            "task_id": resp["task_id"],
            "poll": resp["poll"],
            "suggested": [{"label": "查看任务", "action": "task_status", "task_id": resp["task_id"]}],
        })

    if intent["kind"] == "task_status":
        from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError

        task_id = intent.get("task_id") or session.get("pending_task") or ""
        if not task_id:
            return APIResponse(success=False, message="no_task", data={
                "content": "当前没有进行中的任务。",
            })
        client = OrganClient(base_url=_organ_base_url())
        try:
            t = client.task(task_id)
        except OrganClientError as e:
            return APIResponse(success=False, message="organ_error", data={
                "content": f"查询失败: {e}",
            })
        status = t.get("status", "?")
        progress = t.get("progress", {})
        parts = [
            f"任务 {task_id}",
            f"状态: {status}",
            f"进度: {progress.get('step', '?')}/{progress.get('total', '?')} {progress.get('label', '')}",
        ]
        if t.get("result"):
            parts.append(f"结果: {t['result'][:150]}")
        if t.get("error"):
            parts.append(f"错误: {t['error'][:150]}")
        return APIResponse(success=True, message="ok", data={
            "session_id": session_id, "content": "\n".join(parts),
        })

    # ── 普通对话（非写作意图）──
    session["history"].append({"role": "user", "content": message})
    return APIResponse(success=True, message="ok", data={
        "session_id": session_id,
        "content": (
            "我是 OCOS——你的写作大脑。我可以：\n"
            "1. 理解你的小说构想并给出写作决策（重点/基调/节奏/章节目标）\n"
            "2. 经写作器官（OpenTale）执行生成\n"
            "3. 查看生成任务状态\n\n"
            "试试描述一个故事构想，例如：「我想写一部都市情感小说，讲离婚冷静期三十天里两人重新学会面对彼此」。"
        ),
    })


# ── 意图解析（轻量规则；后续可升级 LLM 意图分类） ──


def _parse_intent(message: str, session: dict[str, Any]) -> dict[str, Any]:
    text = message.strip()
    # 执行意图
    if text in ("开始写", "开始", "执行", "写吧", "go"):
        return {"kind": "execute"}
    if "任务" in text and ("状态" in text or "进度" in text or "查看" in text):
        return {"kind": "task_status", "task_id": _extract_task_id(text)}
    # 写作意图关键词
    writing_markers = ("写", "小说", "故事", "作品", "创作", "构思", "大纲", "题材")
    if any(m in text for m in writing_markers):
        return {
            "kind": "writing",
            "premise": text,
            "title": _extract_title(text),
            "genre": _extract_genre(text),
        }
    return {"kind": "talk"}


def _extract_title(text: str) -> str:
    """尝试从「《》」提取书名。"""
    import re

    m = re.search(r"[《「]([^》」]+)[》」]", text)
    return m.group(1).strip() if m else ""


def _extract_genre(text: str) -> str:
    genre_map = {
        "科幻": "sci_fi", "玄幻": "fantasy", "言情": "romance", "都市": "urban",
        "悬疑": "suspense", "推理": "mystery", "历史": "historical", "武侠": "wuxia",
    }
    for zh, code in genre_map.items():
        if zh in text:
            return code
    return "general"


def _extract_task_id(text: str) -> str:
    import re

    m = re.search(r"(task-[0-9a-f]{12})", text)
    return m.group(1) if m else ""


def _organ_base_url() -> str:
    import os

    return os.getenv("OCOS_ORGAN_BASE", "http://127.0.0.1:8000/api/organ")
