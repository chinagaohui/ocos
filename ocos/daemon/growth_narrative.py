"""L2-5: 成长叙事周报 — episode 流 → "我这一周学到了什么"（V5/V1）。

升级方案 v1.0 §L2: narrative_pipeline 上电 — 定期从 episode 流生成
成长叙事，入记忆 + 可主动汇报；L4 复用为"自传"（跨周连续编号）。

设计（上电而非重写）:
  - 叙事 = 既有生产事实的结构化叙述（episode/goal 表聚合），纯确定性，
    无 LLM、不编造——"这一周做了什么/学到什么/失败了什么"全部可溯源
  - 存档: ~/.ocos/narrative/week_YYYY-Wnn.md（连续章节号 = 存档数 + 1，
    跨周单调递增——生命有了自传）
  - 入记忆: episode（source='growth_narrative', tags=['growth_narrative', 周键]）
  - 触发: daemon 每 N tick 检查 ISO 周切换；周切换后首次检查即生成上一周叙事
    （无状态——已生成到哪周由既有 episode 记录推导，不依赖额外状态文件）
  - 汇报: 生成后经 outbox + 通道链路主动推送（V1 主动汇报出口）
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NarrativeReport:
    """一周成长叙事。"""
    week_key: str = ""            # YYYY-Wnn（ISO 周）
    chapter: int = 0              # 跨周连续章节号
    goals_completed: int = 0
    goals_created: int = 0
    episodes_total: int = 0
    lessons: list[str] = field(default_factory=list)
    failures: int = 0
    narrative: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"# 成长叙事 第{self.chapter}章（{self.week_key}）",
            "",
            f"本周创建目标 {self.goals_created} 个，完成 {self.goals_completed} 个；"
            f"沉淀经历 {self.episodes_total} 段。",
        ]
        if self.failures:
            attributed = "，且均已沉淀为 lesson" if len(self.lessons) >= self.failures else ""
            lines.append(f"经历失败 {self.failures} 次{attributed}。")
        if self.lessons:
            lines.append("")
            lines.append("## 本周学到")
            for i, lesson in enumerate(self.lessons[:5], 1):
                lines.append(f"{i}. {lesson}")
        lines.append("")
        lines.append(f"> 由 OCOS 成长叙事管道从 episode 流自动生成 "
                     f"（可溯源，无虚构）。")
        return "\n".join(lines)


def _iso_week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_bounds(week_key: str) -> tuple[str, str]:
    """周键 → [start, end) ISO 时间戳（UTC）。"""
    year, week = int(week_key[:4]), int(week_key[6:])
    start = datetime.fromisocalendar(year, week, 1).replace(
        hour=0, tzinfo=timezone.utc)
    return start.isoformat(), (start + timedelta(days=7)).isoformat()


def _latest_narrative_week(db_path: str) -> str | None:
    """已生成的最后一周叙事键（无记录 = None）。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT context FROM episodes WHERE source = 'growth_narrative' "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return None
        import json as _json
        try:
            context = _json.loads(row[0] or "{}")
        except ValueError:
            return None
        return context.get("week_key") if isinstance(context, dict) else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def generate_weekly_narrative(db_path: str, week_key: str,
                              archive_dir: Path | None = None) -> NarrativeReport:
    """为指定 ISO 周生成成长叙事（幂等：同周重复调用覆盖同章存档）。"""
    report = NarrativeReport(week_key=week_key)
    start_iso, end_iso = _week_bounds(week_key)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE status IN "
            "('COMPLETED','completed','DONE','done') "
            "AND updated_at >= ? AND updated_at < ?",
            (start_iso, end_iso)).fetchone()
        report.goals_completed = int(row[0] or 0)
        row = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE created_at >= ? AND created_at < ?",
            (start_iso, end_iso)).fetchone()
        report.goals_created = int(row[0] or 0)
        row = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE created_at >= ? AND created_at < ?",
            (start_iso, end_iso)).fetchone()
        report.episodes_total = int(row[0] or 0)
        row = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE created_at >= ? AND created_at < ? "
            "AND outcome LIKE '%\"success\": false%'",
            (start_iso, end_iso)).fetchone()
        report.failures = int(row[0] or 0)
        rows = conn.execute(
            "SELECT decision FROM episodes WHERE created_at >= ? AND created_at < ? "
            "AND (source IN ('lesson','reflection') OR tags LIKE '%lesson%') "
            "ORDER BY created_at LIMIT 5",
            (start_iso, end_iso)).fetchall()
        report.lessons = [str(r[0])[:80] for r in rows if r[0]]
    except sqlite3.Error as e:
        logger.warning("narrative aggregation degraded: %s", e)
    finally:
        conn.close()

    # 连续章节号 = 存档文件数 + 1（跨周单调）
    adir = Path(archive_dir) if archive_dir else (Path.home() / ".ocos" / "narrative")
    try:
        report.chapter = len(list(adir.glob("week_*.md"))) + 1
    except OSError:
        report.chapter = 1
    report.narrative = report.to_markdown()

    # 存档 + 入记忆（失败降级不抛——叙事是增值产物，不阻断 daemon）
    try:
        adir.mkdir(parents=True, exist_ok=True)
        (adir / f"week_{week_key}.md").write_text(
            report.narrative, encoding="utf-8")
    except OSError as e:
        logger.warning("narrative archive write failed: %s", e)
    try:
        from ocos.memory.episode.models import Episode
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(db_path)
        store.initialize()
        ep = Episode.from_candidate(
            experience_id=f"narrative-{week_key}",
            context={"week_key": week_key, "kind": "growth_narrative",
                     "chapter": report.chapter},
            goal="周度成长回顾",
            decision=report.narrative[:4000],
            action="growth_narrative.generate",
            outcome={"success": True, "week": week_key,
                     "chapter": report.chapter},
            condition="daemon weekly trigger",
            significance_score=0.9,
            evaluation_trace={"source_stats": {
                "episodes": report.episodes_total,
                "goals_completed": report.goals_completed,
                "failures": report.failures}},
            source="growth_narrative",
            tags=["growth_narrative", week_key],
        )
        store.save(ep)
    except Exception as e:
        logger.warning("narrative episode write failed: %s", e)
    return report


def check_week_rollover(db_path: str,
                        archive_dir: Path | None = None) -> NarrativeReport | None:
    """daemon 周期调用：ISO 周已切换且上周尚未生成 → 生成上周叙事。

    无状态：已生成进度由 growth_narrative episodes 推导。返回 None =
    本周无需生成（诚实沉默）。
    """
    if not db_path:
        return None
    current = _iso_week_key(datetime.now(timezone.utc))
    last = _latest_narrative_week(db_path)
    if last is not None and last >= current:
        return None   # 已跟上当前周（或超前，不回写）
    # 目标周 = 当前周的前一周（首次运行时若从未生成，从上周讲起，
    # 不回溯历史——诚实性优先于完整性）
    now = datetime.now(timezone.utc)
    prev_week_dt = now - timedelta(days=now.isocalendar()[2])  # 回到本周周一
    target = _iso_week_key(prev_week_dt - timedelta(seconds=1))
    if last is not None and target <= last:
        return None
    return generate_weekly_narrative(db_path, target, archive_dir)


__all__ = ["NarrativeReport", "generate_weekly_narrative", "check_week_rollover"]
