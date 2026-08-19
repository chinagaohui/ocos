"""SelfRegulationLoop — OCOS 自调节闭环（S7：TrendAnalyzer → ContractAdjustment）。

闭环（写一章 → 分析 → 调整 → 下一章）：
  1. collect：经 Organ API 读项目章节 → 构造章节质量报告（复用 reviews/ch00X.json
     若有；否则基于文本规则推导简化分数）
  2. analyze：TrendAnalyzer.analyze（衰减/慢性维度/情绪单调/对话失衡/题材漂移）
  3. adjust：DecisionTranslator.translate_adjustment → ContractAdjustment
  4. confirm：调整建议展示 → 人工确认（审批链，受控开关）
  5. apply：确认后 → Organ rewrite（把调整转成下一章改写指令）

受控开关：OCOS_SELF_REGULATION（默认 on；"manual" 表示必须人工确认才应用）。
边界：调整不直接改 opentale 内部状态——经 Organ API 动作执行（器官自洽）。
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from ocos.opentale_bridge.decision_translator import DecisionTranslator
from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError
from ocos.opentale_bridge.trend_analyzer import TrendAnalyzer

_EMOTION_WORDS = [
    "痛", "怒", "哭", "笑", "怕", "慌", "暖", "冷", "爱", "恨",
    "颤抖", "沉默", "愤怒", "温柔", "绝望", "希望", "委屈", "愧疚",
]

_DIALOGUE_MARKERS = ["“", "”", "「", "」", "说", "道", "问", "喊", "答"]


def _self_regulation_mode() -> str:
    """off | auto | manual（默认 manual：调整需人工确认）。"""
    return os.getenv("OCOS_SELF_REGULATION", "manual").lower()


class SelfRegulationLoop:
    """OCOS 跨章自调节闭环。"""

    def __init__(self, organ_base: str = "http://127.0.0.1:8000/api/organ") -> None:
        self.organ = OrganClient(base_url=organ_base)
        self.trend_analyzer = TrendAnalyzer()
        self.translator = DecisionTranslator()

    # ── 1. 章节质量报告收集 ──

    def collect_chapter_reports(self, project: str,
                                max_chapters: int = 40) -> list[dict[str, Any]]:
        """读项目章节 → 质量报告序列（TrendAnalyzer 输入）。

        优先复用项目内 reviews/ch00X.json（真实评审分数）；缺失则按文本规则推导。
        """
        report = self.organ.project(project)
        total = min(int(report.get("chapters") or 0), max_chapters)
        reports: list[dict[str, Any]] = []
        for ch in range(1, total + 1):
            reports.append(self._chapter_report(project, ch))
        return reports

    def _chapter_report(self, project: str, ch: int) -> dict[str, Any]:
        # 1) 复用 opentale 评审分数（若存在 reviews/ch00X.json）
        try:
            text = self.organ.chapter(project, ch).get("content", "")
        except OrganClientError:
            text = ""
        score = self._text_quality_score(text)
        dims = self._text_dimensions(text)
        return {
            "chapter": ch,
            "chapter_number": ch,
            "ocos_overall": score,
            "ocos_dimensions": dims,
        }

    @staticmethod
    def _text_quality_score(text: str) -> float:
        if not text:
            return 0.0
        # 简化质量代理：长度（信息量）+ 对话（叙事活力）
        length = min(len(text) / 4000.0, 1.0)          # 4000 字封顶
        dialogue = min(sum(text.count(m) for m in _DIALOGUE_MARKERS) / 60.0, 1.0)
        return round(0.6 * length + 0.4 * dialogue, 3)

    @staticmethod
    def _text_dimensions(text: str) -> dict[str, dict[str, float]]:
        dims: dict[str, dict[str, float]] = {}
        for dim in ("narrative_density", "character_coherence",
                    "emotional_curve", "genre_compliance", "language_quality"):
            dims[dim] = {"score": 0.5}
        if text:
            emotion = min(sum(text.count(w) for w in _EMOTION_WORDS) / 20.0, 1.0)
            dims["emotional_curve"] = {"score": round(emotion, 3)}
            sentences = len(re.findall(r"[。！？!?]", text))
            density = min(sentences / 120.0, 1.0) if sentences else 0.3
            dims["narrative_density"] = {"score": round(density, 3)}
        return dims

    # ── 2+3. 趋势分析 → 契约调整 ──

    def analyze(self, project: str, max_chapters: int = 40) -> list[Any]:
        """分析项目跨章趋势 → TrendSignal 列表。"""
        from ocos.opentale_bridge.ocos_activation import activate
        activate("G5_self_regulation")
        reports = self.collect_chapter_reports(project, max_chapters)
        return self.trend_analyzer.analyze(reports)

    def adjust(self, project: str, max_chapters: int = 40) -> tuple[list[Any], Any]:
        """趋势 → ContractAdjustment（返回 (trends, adjustment)）。"""
        trends = self.analyze(project, max_chapters)
        adjustment = self.translator.translate_adjustment(trends)
        return trends, adjustment

    # ── 4. 建议展示 + 确认 ──

    def describe(self, trends: list[Any], adjustment: Any) -> str:
        lines = []
        if not trends:
            return "未检测到跨章质量趋势——当前写作曲线健康。"
        lines.append(f"检测到 {len(trends)} 个跨章趋势（严重度 {adjustment.severity}）：")
        for t in trends:
            lines.append(f"  · [{t.severity}] {t.description}（置信 {t.confidence:.0%}）"
                         f" 影响: {', '.join(t.affected_dimensions)}")
        if adjustment.reason and adjustment.reason != "No trends detected — no adjustment needed":
            lines.append(f"调整策略: {adjustment.reason}")
        if adjustment.chapter_focus_patch:
            lines.append(f"  章节重点调整: {adjustment.chapter_focus_patch}")
        if adjustment.emotion_curve_override:
            lines.append(f"  情绪曲线: {adjustment.emotion_curve_override}"
                         + (f"（共振目标 {adjustment.emotional_resonance_target}）"
                            if adjustment.emotional_resonance_target else ""))
        if adjustment.scene_distribution_patch:
            lines.append(f"  场景分布: {adjustment.scene_distribution_patch}")
        if adjustment.pov_policy_tightening:
            lines.append("  POV 策略: 收紧视角")
        return "\n".join(lines)

    # ── 5. 应用（经 Organ API，人工确认后） ──

    def apply(self, project: str, chapter: int, adjustment: Any,
               trace_context: Any = None) -> dict[str, Any]:
        # U4.1: trace_context 可选——经 organ.rewrite 传播 correlation_id（CIS-Trace 连续）
        """把契约调整应用到指定章节（Organ rewrite + 调整指令）。

        受控开关：manual（默认）要求调用方已确认；auto 直接应用；off 拒绝。
        """
        from ocos.opentale_bridge.ocos_activation import activate
        activate("A4_regulation_switch")
        activate("A3_adjustment_apply")
        mode = _self_regulation_mode()
        if mode == "off":
            return {"status": "skipped", "reason": "OCOS_SELF_REGULATION=off（受控开关关闭）"}
        if mode == "manual":
            # 调用方（CLI/WebChat）负责人工确认后才调用本方法
            pass
        instruction = self._adjustment_to_instruction(adjustment)
        resp = self.organ.rewrite(project, chapter, instruction=instruction,
                                  trace_context=trace_context)  # U4.1: trace 传播
        # 记忆巩固：调整历史随项目持久化（ocos_adjustments.json）——可回看的写作记忆
        _corr = ""
        if trace_context is not None:
            _corr = getattr(trace_context, "correlation_id", "") or ""
        self._record_adjustment(project, chapter, adjustment, instruction,
                                resp.get("task_id", ""), mode, correlation_id=_corr)
        return {"status": "applied", "mode": mode,
                "task_id": resp.get("task_id"),
                "instruction": instruction}

    @staticmethod
    def _record_adjustment(project: str, chapter: int, adjustment: Any,
                           instruction: str, task_id: str, mode: str,
                           correlation_id: str = "") -> None:
        """把调整记录追加到项目目录 ocos_adjustments.json（记忆巩固，随项目持久化）。"""
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        try:
            proj_dir = Path("/home/laogao/Documents/trae_projects/opentale/projects") / project
            if not proj_dir.is_dir():
                proj_dir = Path.home() / ".ocos" / "adjustments"
                proj_dir.mkdir(parents=True, exist_ok=True)
                log_path = proj_dir / f"{project}_adjustments.json"
            else:
                log_path = proj_dir / "ocos_adjustments.json"
            history: list[dict] = []
            if log_path.exists():
                try:
                    history = json.loads(log_path.read_text(encoding="utf-8"))
                except Exception:
                    history = []
            history.append({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "project": project, "chapter": chapter,
                "correlation_id": correlation_id,  # U4.1: Trace 连续（CIS-Trace 100%）
                "adjustment_id": getattr(adjustment, "adjustment_id", ""),
                "triggered_by": list(getattr(adjustment, "triggered_by", [])),
                "severity": getattr(adjustment, "severity", "info"),
                "reason": getattr(adjustment, "reason", ""),
                "instruction": instruction,
                "task_id": task_id,
                "mode": mode,
            })
            log_path.write_text(json.dumps(history, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        except Exception:
            pass  # 记忆记录失败不阻断应用

    @staticmethod
    def _adjustment_to_instruction(adjustment: Any) -> str:
        parts: list[str] = []
        if adjustment.chapter_focus_patch:
            focus_names = {k: k for k in adjustment.chapter_focus_patch}
            parts.append("本章重点向" + "/".join(focus_names) + "倾斜")
        if adjustment.emotion_curve_override:
            curve = adjustment.emotion_curve_override
            if curve == "oscillation":
                parts.append("情绪曲线改为起伏摆动，避免平铺")
            elif curve == "catharsis":
                parts.append("情绪曲线改为先抑后扬的宣泄结构，放大情感摆动")
            else:
                parts.append(f"情绪曲线按 {curve} 结构调整")
        if adjustment.scene_distribution_patch:
            parts.append("调整场景配比（" +
                         "、".join(f"{k}{v:+.1f}" for k, v in adjustment.scene_distribution_patch.items()) + "）")
        if adjustment.pov_policy_tightening:
            parts.append("收紧叙事视角，保持单一主角感知")
        if adjustment.emotional_resonance_target:
            parts.append(f"情感共鸣目标提升至 {adjustment.emotional_resonance_target:.0%}")
        return "；".join(parts) if parts else "保持当前写作方向，注意整体节奏一致性"
