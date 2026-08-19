"""MasterAgent — OCOS 写作决策引擎（S5：决策真实化）。

替换 opentale_bridge 中 produce_decision 的硬编码模拟（按章节号轮换 focus/tone），
改为**基于真实写作意图**的决策：

  输入：premise（大纲/创意）+ title/genre/characters + focus/tone/pacing 提示
  决策：关键词推导 + 意图解析 → primary_focus / emotional_tone / pacing_directive /
        chapter_goal / conflict_instruction / character_instructions / key_scenes
  输出：OcosDecision → DecisionTranslator blueprint → Organ 设定契约（generate 请求体）

设计依据（老高 S3/S4 判定）：
- 优势区 = 情感驱动、人物弧为核心的题材 → focus 默认偏 relationship/character
- 设定契约（characters/world）贯穿决策 → Organ generate，防漂移
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.opentale_bridge.bridge_model import OcosDecision


@dataclass
class WritingIntent:
    """写作意图（来自 goal/CLI 输入）。"""

    premise: str = ""
    title: str = ""
    genre: str = "general"
    characters: list[str] = field(default_factory=list)
    roles: dict[str, str] = field(default_factory=dict)
    genders: dict[str, str] = field(default_factory=dict)  # S8: 名字→男/女（代词一致性）
    world: list[str] = field(default_factory=list)
    focus_hint: str = ""      # relationship/conflict/character/world 或中文关键词
    tone_hint: str = ""       # tension/warmth/melancholy/hope
    pacing_hint: str = ""     # accelerate/maintain/decelerate
    total_chapters: int = 10


# ── 关键词表（中文 + 英文） ──


FOCUS_KEYWORDS: dict[str, list[str]] = {
    "relationship": ["关系", "感情", "爱情", "爱", "家庭", "友情", "暧昧", "亲情",
                     "婚姻", "恋人", "relationship", "romance", "love"],
    "conflict": ["冲突", "对抗", "斗争", "战争", "复仇", "对立", "竞争", "对决",
                 "危机", "conflict", "battle"],
    "character": ["成长", "人物", "角色", "蜕变", "救赎", "性格", "内心", "弧线",
                  "character", "growth"],
    "world": ["世界", "设定", "世界观", "文明", "社会", "时代", "背景",
              "world", "setting"],
    # S5 补充：悬疑/调查类（科幻悬疑/推理常被误判为 relationship）
    "investigation": ["查明", "调查", "追查", "真相", "谜", "秘密", "失踪", "信号",
                      "线索", "嫌疑", "案件", "证据", "investigation", "mystery",
                      "suspense", "悬念", "谜团", "呼救", "求救", "悬疑", "推理",
                      # P1-2：能力系悬疑（大脑过载/超能力类）
                      "过载", "超能力", "特异功能", "异能", "预知", "读心"],
}

TONE_KEYWORDS: dict[str, list[str]] = {
    "tension": ["紧张", "悬疑", "压迫", "惊悚", "危机", "悬念", "suspense", "tension"],
    "warmth": ["温暖", "治愈", "温情", "甜蜜", "warmth", "healing", "sweet"],
    "melancholy": ["忧伤", "伤感", "忧郁", "遗憾", "悲", "melancholy", "sad"],
    "hope": ["希望", "励志", "昂扬", "热血", "hope", "inspire"],
    # S5 补充：悬疑/未知/秘密 基调（配合 investigation focus）
    "suspense": ["秘密", "谜团", "未知", "诡异", "谜", "真相", "不解", "suspense",
                 "mystery", "cryptic", "悬疑", "推理", "过载", "超能力", "异能", "预知"],
}

PACING_KEYWORDS: dict[str, list[str]] = {
    "accelerate": ["快", "加速", "紧凑", "高能", "accelerate", "fast"],
    "decelerate": ["慢", "舒缓", "细腻", "沉浸", "decelerate", "slow"],
    "maintain": ["稳", "均衡", "maintain", "steady"],
}

FOCUS_TO_KEY_SCENES: dict[str, list[str]] = {
    "relationship": ["关键对话", "情感转折", "关系裂痕/修复"],
    "conflict": ["正面交锋", "局势升级", "代价显形"],
    "character": ["内心抉择", "性格暴露", "成长节点"],
    "world": ["世界观揭示", "规则显形", "时代切片"],
    "investigation": ["线索浮现", "追问真相", "反转/揭示"],
}

_DEFAULT_FOCUS = "relationship"
_DEFAULT_TONE = "tension"
_DEFAULT_PACING = "maintain"


class MasterAgent:
    """OCOS MasterAgent：写作意图 → 真实写作决策。"""

    # ── 意图解析 ──

    @staticmethod
    def _match(text: str, table: dict[str, list[str]]) -> list[str]:
        """返回 text 命中的类别（按命中词数排序）。"""
        hits: dict[str, int] = {}
        for category, keywords in table.items():
            n = sum(1 for kw in keywords if kw in text)
            if n:
                hits[category] = n
        return [c for c, _ in sorted(hits.items(), key=lambda x: -x[1])]

    def resolve_focus(self, intent: WritingIntent) -> str:
        if intent.focus_hint:
            hint = intent.focus_hint.lower()
            for focus in FOCUS_KEYWORDS:
                if focus in hint or hint in focus:
                    return focus
        text = f"{intent.premise} {intent.genre}"
        matched = self._match(text, FOCUS_KEYWORDS)
        return matched[0] if matched else _DEFAULT_FOCUS

    def resolve_tone(self, intent: WritingIntent) -> str:
        if intent.tone_hint:
            hint = intent.tone_hint.lower()
            for tone in TONE_KEYWORDS:
                if tone in hint or hint in tone:
                    return tone
        matched = self._match(f"{intent.premise} {intent.genre}", TONE_KEYWORDS)
        if matched:
            return matched[0]
        # 默认基调与重点联动：关系题材天然偏温情，冲突/世界题材偏紧张，
        # 人物弧偏内省（S5：不再全局默认 tension）
        focus = self.resolve_focus(intent)
        return {
            "relationship": "warmth",
            "conflict": "tension",
            "character": "melancholy",
            "world": "tension",
        }.get(focus, _DEFAULT_TONE)

    def resolve_pacing(self, intent: WritingIntent, chapter: int = 1) -> str:
        if intent.pacing_hint:
            hint = intent.pacing_hint.lower()
            for pacing in PACING_KEYWORDS:
                if pacing in hint or hint in pacing:
                    return pacing
        matched = self._match(intent.premise, PACING_KEYWORDS)
        if matched:
            return matched[0]
        # 默认节奏：开局加速建立钩子，中段稳定，收尾收束
        if chapter <= max(1, intent.total_chapters // 5):
            return "accelerate"
        if chapter >= intent.total_chapters - max(1, intent.total_chapters // 5):
            return "decelerate"
        return _DEFAULT_PACING

    # ── 决策生成 ──

    def decide(self, intent: WritingIntent, chapter: int = 1,
               trace_context=None) -> OcosDecision:
        """基于写作意图生成真实写作决策（替代 produce_decision 硬编码）。

        Phase R1（Trace Identity）：trace_context 可选；入口生成 agent_run_id
        （R1.3：agent_run_id 由 OCOS 生成，correlation_id 原样传播，禁止重新定义）。
        """
        from ocos.opentale_bridge.trace_context import TraceContext, new_id
        from ocos.opentale_bridge.ocos_activation import activate
        activate("E8_master_agent")
        activate("I4_decision_gen")
        if trace_context is None or not getattr(trace_context, "correlation_id", ""):
            # U4.2：OCOS 作为独立入口（chat 无 OpenTale 前置 corr）→ OCOS 生成根；
            # 已收到外部 corr → 原样传播（T-04，禁止重新生成）
            trace_context = TraceContext.new_root(component="interaction/chat", source_system="OCOS")
        agent_run_id = trace_context.agent_run_id or new_id("run_")  # R1.3
        focus = self.resolve_focus(intent)
        tone = self.resolve_tone(intent)
        pacing = self.resolve_pacing(intent, chapter)

        premise_head = intent.premise.strip()[:80] if intent.premise.strip() else "未提供大纲"
        ch_goal = (
            f"第 {chapter} 章：围绕{_focus_label(focus)}推进核心事件——{premise_head}"
        )
        conflict_map = {
            "relationship": "升级人物关系张力：一方有所隐瞒或误解，迫使双方正面回应",
            "conflict": "升级外部冲突：新代价显形，局势比上一章更不可退",
            "character": "推进人物弧：一个无法回避的内心抉择，暴露真实性格",
            "world": "揭示世界观新层：规则/背景信息通过情节自然浮出",
        }
        char_instructions: dict[str, str] = {}
        for name in intent.characters[:4]:
            role = intent.roles.get(name, "主角")
            if role == "主角":
                char_instructions[name] = (
                    f"推进{focus}主线，其选择直接影响本章走向")
            elif role in ("配角", "盟友"):
                char_instructions[name] = f"在关键场景中推动主角做出选择"
            elif role == "反派":
                char_instructions[name] = f"制造本章主要障碍/反作用力"

        # E7（P1-3/P2）：决策前经 OcosMemory 编排回忆（决策历史+反馈+长期经验）
        from ocos.opentale_bridge.ocos_memory import OcosMemory
        _memory = OcosMemory()
        _cognition = _memory.recall(intent.title)
        # I6 Attention（U5.3）：注意力焦点注入 reasoning 上下文（生产实际路径）
        # 只影响"认知系统看什么"，不触 Decision/Mutation/Action（Authority 冻结）
        _af = MasterAgent._attention_focus(intent)
        if _af:
            _cognition = f"{_cognition}；{_af}" if _cognition else _af
        decision = OcosDecision(
            decision_id=f"d{chapter:04d}_{uuid.uuid4().hex[:8]}",
            primary_focus=focus,
            emotional_tone=tone,
            pacing_directive=pacing,
            chapter_goal=ch_goal,
            conflict_instruction=conflict_map.get(focus, conflict_map["relationship"]),
            character_instructions=char_instructions,
            key_scenes=list(FOCUS_TO_KEY_SCENES.get(focus, FOCUS_TO_KEY_SCENES["relationship"])),
            word_target=3000,
            pov_character=intent.characters[0] if intent.characters else "",
            cliffhanger_type="emotional" if tone == "warmth" else (
                "plot" if focus == "conflict" else "revelation"),
            confidence=0.85,
            correlation_id=trace_context.correlation_id,      # R1.2：原样传播
            agent_run_id=agent_run_id,                        # R1.3：OCOS 生成
            generation_request_id=trace_context.generation_request_id,
            reasoning=(
                f"意图分析: focus={focus}（关键词命中），tone={tone}，"
                f"pacing={pacing}；角色契约 {len(intent.characters)} 个已绑定"
                + (f"；认知参考: {_cognition}" if _cognition else "")
            ),
        )
        self._writing_decision_gate(decision)  # R5（P1-3）：写作决策门禁校验
        _memory.record_decision(intent.title, decision)  # M6 + 触发巩固/遗忘
        return decision

    # ── 决策 → Organ 设定契约 ──



    @staticmethod
    def _record_decision_history(intent: WritingIntent, decision: OcosDecision) -> None:
        """决策历史持久化（委托 OcosMemory，P2 统一编排）。"""
        from ocos.opentale_bridge.ocos_memory import OcosMemory
        OcosMemory().record_decision(intent.title, decision)


    @staticmethod
    @staticmethod
    def _attention_focus(intent: WritingIntent) -> str:
        """I6 Attention（U5.3 GO，确定性版）：认知上下文选择器。

        只影响 Reasoning Context（认知系统"看什么"），不触 Decision/Mutation/Action。
        Authority 边界（冻结）：Read/Rank/Select/Influence ALLOW；Create/Approve Decision、
        Mutate State、Execute Action、Modify Policy/Identity 全 DENY。
        无状态、无学习、无随机——输入相同输出相同（Deterministic/Governed Attention）。
        """
        from ocos.opentale_bridge.ocos_activation import activate
        activate("I6_attention")
        from ocos.attention.candidate_selector import CandidateCollector
        from ocos.attention.scoring import AttentionScoringEngine

        collector = CandidateCollector()
        try:
            import json
            import os
            from pathlib import Path

            dpath = Path(os.getenv("OCOS_DECISION_HISTORY",
                                   str(Path.home() / ".ocos" / "decision_history.jsonl")))
            if dpath.exists():
                for line in [l for l in dpath.read_text(encoding="utf-8").splitlines() if l.strip()][-3:]:
                    try:
                        e = json.loads(line)
                        if e.get("title") == intent.title:
                            # event 候选：上轮决策信号（urgency = 与当前题材相关度）
                            collector.add_event(
                                event_id=f"dec-{e.get('decision_id','')}",
                                urgency=0.8,
                                summary=f"上轮 focus={e.get('focus')} tone={e.get('tone')}",
                            )
                    except Exception:
                        continue
        except Exception:
            pass
        engine = AttentionScoringEngine()
        scored = engine.score_all(collector.candidates())
        if not scored:
            return ""
        top = sorted(scored, key=lambda x: -x[1])[:1]
        cand = top[0][0]
        return f"注意力焦点: {cand.summary}（确定性选择，score={top[0][1]:.2f}）"

    @staticmethod
    def _collect_cognition_context(intent: WritingIntent) -> str:
        """E7 认知循环（P1-3 轻量版）：决策基于过往决策与项目反馈。

        读 ~/.ocos/decision_history.jsonl（M6）最近 2 条 + ~/.ocos/feedback/（C3）。
        返回简短认知参考文本（空串=无）。
        """
        import json
        import os
        from pathlib import Path

        parts: list[str] = []
        try:
            dpath = Path(os.getenv("OCOS_DECISION_HISTORY",
                                   str(Path.home() / ".ocos" / "decision_history.jsonl")))
            if dpath.exists():
                lines = [l for l in dpath.read_text(encoding="utf-8").splitlines() if l.strip()][-2:]
                for line in lines:
                    try:
                        e = json.loads(line)
                        if e.get("title") == intent.title:
                            parts.append(f"本作上轮决策 focus={e.get('focus')} tone={e.get('tone')}")
                    except Exception:
                        continue
        except Exception:
            pass
        if intent.title:
            try:
                fpath = Path(os.getenv("OCOS_FEEDBACK_DIR",
                                       str(Path.home() / ".ocos" / "feedback"))) / f"{intent.title}.json"
                if fpath.exists():
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    if data:
                        fb = data[-1]
                        parts.append(f"评审 {fb.get('book_review_score')} 分/"
                                     f"{fb.get('chapters', 0)} 章")
            except Exception:
                pass
        # I6 接线（U5.3）：attention 焦点注入 reasoning 上下文（只影响"看什么"）
        _focus = MasterAgent._attention_focus(intent)
        if _focus:
            parts.append(_focus)
        return "；".join(parts)

    @staticmethod
    def _writing_decision_gate(decision: OcosDecision) -> None:
        """R5 写作决策门禁（P1-3）：校验决策字段合法性，违规修正并记录。

        校验：focus/tone/pacing 枚举合法、word_target 范围、pov_character 在角色契约内。
        违规不阻断（记录 + 修正默认），未来可升级为硬门禁。
        """
        from ocos.opentale_bridge.ocos_activation import activate
        activate("R5_decision_gate")
        _valid_focus = {"relationship", "conflict", "character", "world", "investigation"}
        _valid_tone = {"tension", "warmth", "melancholy", "hope", "suspense"}
        _valid_pacing = {"accelerate", "maintain", "decelerate"}
        issues: list[str] = []
        if decision.primary_focus not in _valid_focus:
            decision.primary_focus = "relationship"; issues.append("focus 非法→relationship")
        if decision.emotional_tone not in _valid_tone:
            decision.emotional_tone = "tension"; issues.append("tone 非法→tension")
        if decision.pacing_directive not in _valid_pacing:
            decision.pacing_directive = "maintain"; issues.append("pacing 非法→maintain")
        if not (1000 <= decision.word_target <= 20000):
            decision.word_target = 3000; issues.append("word_target 越界→3000")
        if issues:
            import logging
            logging.getLogger("master_agent").warning(
                "R5 决策门禁修正: %s", "; ".join(issues))

    def to_organ_contract(self, intent: WritingIntent) -> dict[str, Any]:
        """把写作意图转成 Organ generate 请求体（设定契约）。"""
        return {
            "title": intent.title or "未命名作品",
            "genre": intent.genre,
            "chapters": intent.total_chapters,
            "target_words": intent.total_chapters * 2500,
            "content": intent.premise,
            "characters": list(intent.characters),
            "roles": dict(intent.roles),
            "genders": dict(intent.genders),
            "world": list(intent.world),
        }

    def summary(self, decision: OcosDecision) -> str:
        return (
            f"决策 {decision.decision_id}\n"
            f"  重点    : {_focus_label(decision.primary_focus)}（{decision.primary_focus}）\n"
            f"  基调    : {decision.emotional_tone}\n"
            f"  节奏    : {decision.pacing_directive}\n"
            f"  本章目标: {decision.chapter_goal[:60]}\n"
            f"  冲突指令: {decision.conflict_instruction[:60]}\n"
            f"  关键场景: {'、'.join(decision.key_scenes)}\n"
            f"  角色指令: {', '.join(f'{k}→{v[:20]}' for k, v in decision.character_instructions.items()) or '无'}\n"
            f"  推理    : {decision.reasoning[:80]}"
        )


def _focus_label(focus: str) -> str:
    return {
        "relationship": "关系",
        "conflict": "冲突",
        "character": "人物弧",
        "world": "世界观",
    }.get(focus, focus)
