"""OcosMemory — OCOS 记忆编排（S8-P2：M3 编排 + M4 巩固 + M5 遗忘，统一 M6/C3）。

统一管理 OCOS 写作记忆：
  M6 决策历史   : ~/.ocos/decision_history.jsonl（decide 落盘）
  C3 项目反馈   : ~/.ocos/feedback/<project>.json（评审回流）
  M4 长期巩固   : ~/.ocos/longterm_memory.json（成功经验固化）
  M5 记忆遗忘   : 超限/低价值清理（prune）
  M3 编排入口   : recall(title) 聚合决策+反馈+长期经验（供 E7 认知上下文）

设计：零依赖、文件持久化、跨进程安全（append + 原子写）。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _base_dir() -> Path:
    p = Path(os.getenv("OCOS_MEMORY_DIR", str(Path.home() / ".ocos")))
    p.mkdir(parents=True, exist_ok=True)
    return p


class OcosMemory:
    """OCOS 写作记忆编排器（P2：M3/M4/M5 + M6/C3 统一）。"""

    # 遗忘阈值（M5）
    KEEP_DECISION = 200      # 决策历史保留条数
    KEEP_FEEDBACK = 10       # 每项目反馈保留条数
    CONSOLIDATE_SCORE = 80.0  # 巩固分数线（评审分 ≥ 此值 → 长期经验）

    def __init__(self) -> None:
        self._base = _base_dir()

    # ── 路径 ──

    @property
    def decision_path(self) -> Path:
        return self._base / "decision_history.jsonl"

    def feedback_path(self, project: str) -> Path:
        return self._base / "feedback" / f"{project}.json"

    @property
    def longterm_path(self) -> Path:
        return self._base / "longterm_memory.json"

    # ── M6：决策历史 ──

    def record_decision(self, title: str, decision: Any) -> None:
        """追加决策历史（M6）并触发巩固/遗忘。"""
        entry = {
            "decision_id": getattr(decision, "decision_id", ""),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "title": title,
            "focus": getattr(decision, "primary_focus", ""),
            "tone": getattr(decision, "emotional_tone", ""),
            "pacing": getattr(decision, "pacing_directive", ""),
            "chapter_goal": getattr(decision, "chapter_goal", "")[:120],
            # Phase R1（R1.7 持久化）：Trace 字段随决策历史落盘
            "correlation_id": getattr(decision, "correlation_id", ""),
            "agent_run_id": getattr(decision, "agent_run_id", ""),
            "generation_request_id": getattr(decision, "generation_request_id", ""),
        }
        self._append_jsonl(self.decision_path, entry)
        self.prune()
        self.consolidate()

    # ── C3：项目反馈 ──

    def record_feedback(self, project: str, feedback: dict[str, Any]) -> None:
        """追加项目反馈（C3）并触发巩固/遗忘。"""
        path = self.feedback_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        history: list[dict] = []
        if path.exists():
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append(feedback)
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        self.prune()
        self.consolidate()

    # ── M4：记忆巩固（成功经验固化） ──

    def consolidate(self) -> None:
        """扫描决策历史 + 反馈：同作品有评审高分（≥80）→ 固化长期经验。

        长期经验：题材/重点/基调组合 + 成功证据（评审分/章数）。
        """
        try:
            longterm = self._load_json(self.longterm_path, {})
            # 每项目的最近反馈
            fb_dir = self._base / "feedback"
            if fb_dir.is_dir():
                for f in fb_dir.glob("*.json"):
                    try:
                        history = json.loads(f.read_text(encoding="utf-8"))
                        if not history:
                            continue
                        latest = history[-1]
                        score = latest.get("book_review_score")
                        if score is not None and float(score) >= self.CONSOLIDATE_SCORE:
                            project = latest.get("project") or f.stem
                            # 找该作品最近决策补充 focus/tone
                            focus, tone = self._last_decision_meta(project)
                            longterm[project] = {
                                "project": project,
                                "focus": focus or "",
                                "tone": tone or "",
                                "book_review_score": float(score),
                                "chapters": latest.get("chapters", 0),
                                "consolidated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            }
                    except Exception:
                        continue
            self._atomic_write(self.longterm_path, longterm)
        except Exception:
            pass

    def _last_decision_meta(self, title: str) -> tuple[str, str]:
        focus = tone = ""
        for line in self._read_tail_jsonl(self.decision_path, limit=50):
            if line.get("title") == title:
                focus = line.get("focus", "")
                tone = line.get("tone", "")
                break
        return focus, tone

    # ── M5：记忆遗忘（超限/低价值清理） ──

    def prune(self) -> None:
        """清理超限记忆：决策历史保留最新 KEEP_DECISION；每项目反馈保留 KEEP_FEEDBACK。"""
        try:
            # 决策历史
            lines = self._read_tail_jsonl(self.decision_path, limit=self.KEEP_DECISION)
            if self.decision_path.exists():
                # 重写为最新 N 条（原子）
                tmp = self.decision_path.with_suffix(".jsonl.tmp")
                with open(tmp, "a", encoding="utf-8") as f:
                    for e in lines:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
                tmp.replace(self.decision_path)
        except Exception:
            pass
        try:
            # 项目反馈
            fb_dir = self._base / "feedback"
            if fb_dir.is_dir():
                for f in fb_dir.glob("*.json"):
                    try:
                        history = json.loads(f.read_text(encoding="utf-8"))
                        if len(history) > self.KEEP_FEEDBACK:
                            f.write_text(json.dumps(history[-self.KEEP_FEEDBACK:],
                                                     ensure_ascii=False, indent=2),
                                         encoding="utf-8")
                    except Exception:
                        continue
        except Exception:
            pass

    # ── M3：编排入口（聚合记忆供决策引用） ──

    def recall(self, title: str) -> str:
        """聚合决策历史 + 项目反馈 + 长期经验 → 认知上下文（E7）。

        OPT-D3（2026-08-19）：Memory 不可用时优雅降级返回空串（不抛错打断决策，
        与 E7 语义一致：空串=无认知参考）。降级明示（不伪装正常）。
        """
        try:
            return self._recall_impl(title)
        except Exception:
            return ""  # 降级：Memory 不可用 → 空认知上下文（明示降级）

    def _recall_impl(self, title: str) -> str:
        parts: list[str] = []
        # 同作品最近决策
        for e in self._read_tail_jsonl(self.decision_path, limit=30):
            if e.get("title") == title:
                parts.append(f"上轮决策 focus={e.get('focus')} tone={e.get('tone')}")
                break
        # 项目反馈
        fb = self.latest_feedback(title)
        if fb:
            parts.append(f"评审 {fb.get('book_review_score')} 分/{fb.get('chapters', 0)} 章")
        # 长期经验
        lt = self._load_json(self.longterm_path, {})
        if title in lt:
            parts.append("长期经验: 该题材方向已获高分验证")
        return "；".join(parts)

    def latest_feedback(self, project: str) -> Optional[dict]:
        path = self.feedback_path(project)
        if not path.exists():
            return None
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            return history[-1] if history else None
        except Exception:
            return None

    def longterm_memory(self) -> dict[str, Any]:
        return self._load_json(self.longterm_path, {})

    # ── 内部工具 ──

    @staticmethod
    def _append_jsonl(path: Path, entry: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_tail_jsonl(path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        try:
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            return [json.loads(l) for l in lines[-limit:]]
        except Exception:
            return []

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
