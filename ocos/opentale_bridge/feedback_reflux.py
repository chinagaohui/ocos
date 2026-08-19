"""FeedbackReflux — 评审反馈回流（S8 C3：OpenTale 评审/issues → OCOS 记忆）。

闭环补全（此前缺失的一环）：
  生成 → 评审（issues/score）→ 本模块收集 → 写入 OCOS 反馈记忆
  （~/.ocos/feedback/<project>.json）→ 下次决策/调节时引用。

数据来源：Organ API 项目报告（book_review score/issues/chapters）。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError
from ocos.opentale_bridge.ocos_activation import activate


def _feedback_dir() -> Path:
    p = Path(os.getenv("OCOS_FEEDBACK_DIR", str(Path.home() / ".ocos" / "feedback")))
    p.mkdir(parents=True, exist_ok=True)
    return p


class FeedbackReflux:
    """评审反馈回流器。"""

    def __init__(self, organ_base: str = "http://127.0.0.1:8000/api/organ") -> None:
        self.organ = OrganClient(base_url=organ_base)

    # ── 收集 + 存储 ──

    def collect_and_store(self, project: str) -> dict[str, Any]:
        """读项目评审（Organ API）→ 结构化反馈 → 写入 OCOS 反馈记忆。

        返回存储的反馈记录。
        """
        activate("C3_feedback_reflux")
        try:
            report = self.organ.project(project)
        except OrganClientError as e:
            return {"status": "error", "detail": str(e)}

        feedback = {
            "project": project,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chapters": report.get("chapters", 0),
            "book_review_score": report.get("book_review_score"),
            "characters": report.get("characters", []),
            "issues": report.get("issues", []),
            "source": "organ_project_report",
        }
        # P2：经 OcosMemory 统一记录（C3 + 触发 M4 巩固/M5 遗忘）
        from ocos.opentale_bridge.ocos_memory import OcosMemory
        OcosMemory().record_feedback(project, feedback)
        return feedback

    # ── 读取（供决策/调节引用） ──

    def latest(self, project: str) -> Optional[dict[str, Any]]:
        """最近一条项目反馈（决策可引用）。"""
        path = _feedback_dir() / f"{project}.json"
        if not path.exists():
            return None
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            return history[-1] if history else None
        except Exception:
            return None

    def feedback_summary(self, project: str) -> str:
        """人类可读反馈摘要（注入决策 reasoning）。"""
        fb = self.latest(project)
        if not fb:
            return ""
        parts = [
            f"最近评审: 分 {fb.get('book_review_score', '?')}",
            f"{fb.get('chapters', 0)} 章",
        ]
        issues = fb.get("issues", []) or []
        if issues:
            parts.append(f"待改进 {len(issues)} 项: " + "；".join(
                str(i.get("message", i))[:60] for i in issues[:3]))
        return " | ".join(parts)
