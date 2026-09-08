"""升级方案 v1.0 §3.1: 生命体征日报告 — vitals 快照每日归档 + 主动汇报。

设计（与 growth_narrative 周报同构，纯确定性无 LLM）:
  - 内容 = compute_vitals 从 episodes/goals/pending 聚合的真实快照
    + check_thresholds(L4) 判定（不装样子，缺数据诚实标注未点亮）
  - 存档: ~/.ocos/reports/vitals_YYYY-MM-DD.md
  - 入记忆: episode（source='vitals_report', tags=['vitals_report', 日键]）
  - 触发: daemon 每 N tick 检查日切换；已生成到今天则沉默（无状态，
    进度由 vitals_report episodes 推导）
  - 汇报: 生成后经 outbox 主动推送（本身即 V1 主动汇报行为）
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VitalsDailyReport:
    """一日生命体征快照。"""
    day_key: str = ""                 # YYYY-MM-DD（UTC）
    violations: list[str] = field(default_factory=list)
    markdown: str = ""

    @property
    def passed(self) -> bool:
        hard = [v for v in self.violations if not v.startswith("[未点亮]")]
        return not hard

    def summary(self) -> str:
        """outbox 推送用一句话摘要（结果直呈，不要求用户翻面板）。"""
        tag = "✓ 全部达标" if self.passed else "✗ 存在未达标项"
        head = f"[生命体征日报 {self.day_key}] {tag}"
        if self.violations:
            head += "：" + "；".join(self.violations[:3])
            if len(self.violations) > 3:
                head += f"（等共 {len(self.violations)} 项）"
        return head


def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _latest_report_day(db_path: str) -> str | None:
    """已生成的最后一个日报日键（无记录 = None）。

    从 tags 解析全部日键取 max（确定性）——不依赖 created_at 排序，
    同刻写入的 episodes 不会产生歧义。
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    days: list[str] = []
    try:
        for (tags,) in conn.execute(
                "SELECT tags FROM episodes WHERE source = 'vitals_report'"):
            try:
                arr = json.loads(tags or "[]")
            except ValueError:
                continue
            days.extend(t for t in arr if isinstance(t, str) and
                        len(t) == 10 and t[4] == "-" and t[7] == "-")
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    return max(days) if days else None


def generate_daily_vitals(db_path: str, day_key: str | None = None,
                          archive_dir: Path | None = None) -> VitalsDailyReport:
    """生成指定日的生命体征日报（幂等：同日重复调用覆盖同日存档）。"""
    from ocos.monitoring.vitals import check_thresholds, compute_vitals, render_vitals

    dk = day_key or _day_key(datetime.now(timezone.utc))
    vitals = compute_vitals(db_path, window_days=7)
    violations = check_thresholds(vitals, "L4")
    body = render_vitals(vitals)
    gate_line = (f"\n[Gate L4] ✓ 阈值全部达标" if not violations
                 else "\n[Gate L4] 未达标项:\n" +
                 "\n".join(f"  - {v}" for v in violations))
    report = VitalsDailyReport(
        day_key=dk,
        violations=violations,
        markdown=(f"# 生命体征日报（{dk}）\n\n{body}{gate_line}\n\n"
                  f"> 由 OCOS vitals 管道从生产数据聚合（可溯源，无自报告）。"),
    )

    adir = Path(archive_dir) if archive_dir else (Path.home() / ".ocos" / "reports")
    try:
        adir.mkdir(parents=True, exist_ok=True)
        (adir / f"vitals_{dk}.md").write_text(report.markdown, encoding="utf-8")
    except OSError as e:
        logger.warning("vitals report archive write failed: %s", e)
    try:
        from ocos.memory.episode.models import Episode
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(db_path)
        store.initialize()
        ep = Episode.from_candidate(
            experience_id=f"vitals-report-{dk}",
            context={"day_key": dk, "kind": "vitals_report",
                     "violations": list(violations)},
            goal="生命体征日报告",
            decision=report.markdown[:4000],
            action="vitals_report.generate",
            outcome={"success": report.passed, "day": dk,
                     "violation_count": len(violations)},
            condition="daemon daily trigger",
            significance_score=0.6,
            evaluation_trace={"gate": "L4", "violations": list(violations)},
            source="vitals_report",
            tags=["vitals_report", dk],
        )
        store.save(ep)
    except Exception as e:
        logger.warning("vitals report episode write failed: %s", e)
    return report


def check_day_rollover(db_path: str,
                       archive_dir: Path | None = None) -> VitalsDailyReport | None:
    """daemon 周期调用：昨日尚未生成日报 → 生成昨日快照。

    无状态：进度由 vitals_report episodes 推导。返回 None = 无需生成。
    中断多日不回溯补齐——窗口聚合对过去日期不可精确重构，诚实起见
    从最近一个完整日（昨日）恢复。
    """
    if not db_path:
        return None
    yesterday = _day_key(datetime.now(timezone.utc) - timedelta(days=1))
    last = _latest_report_day(db_path)
    if last is not None and last >= yesterday:
        return None   # 已跟上（含中断后追到昨日，不回溯历史）
    return generate_daily_vitals(db_path, yesterday, archive_dir)


__all__ = ["VitalsDailyReport", "generate_daily_vitals", "check_day_rollover"]
