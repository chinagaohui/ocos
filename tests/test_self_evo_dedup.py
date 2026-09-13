"""COG-V2 Phase4.5: 自进化防灌水闸门单测。

生产实锤（2026-09-13）：goals 835 行仅 357 唯一描述——
  - 同一条工具探索目标被生成 50 次（去重只看活跃态，完成即放行）
  - 同标题 EVO-Plan 43 次（Pump 只按 artifact_id 去重，防不住同标题新产物）
  - LLM 把执行结果回显（✓/✗）复读成新方案（旧回声闸漏网，25 次）

两个零 LLM 确定性闸门：
  - ocos.daemon._recent_goal_exists：同标题 7 天窗、任意状态历史去重
  - ocos.daemon._echo_artifact_reason：Mini-Plan/JSON/套娃/✓✗回显拒绝
"""
from __future__ import annotations

import sqlite3

import pytest

from ocos.daemon import _echo_artifact_reason, _like_escape, _recent_goal_exists


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE goals ("
        "id TEXT PRIMARY KEY, description TEXT, status TEXT, created_at TEXT)"
    )
    yield conn
    conn.close()


def _add(db, title, status, when="-0 days"):
    n = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0] + 1
    db.execute(
        "INSERT INTO goals VALUES (?,?,?,?)",
        (f"G-{n:03d}", title, status,
         None if when is None else
         db.execute("SELECT datetime('now',?)", (when,)).fetchone()[0]),
    )
    db.commit()


# ── LIKE 转义 ──────────────────────────────────────────────────────────────

def test_like_escape_special_chars():
    out = _like_escape("a%b_c[d]")
    assert "%" not in out.replace("\\%", "")
    assert out == "a\\%b\\_c\\[d\\]"


# ── 历史标题去重 ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["PENDING", "ACTIVE", "COMPLETED", "ABANDONED"])
def test_recent_goal_any_status_blocks(db, status):
    """核心修复：COMPLETED/ABANDONED 历史同样拦截（旧逻辑只看活跃态）。"""
    _add(db, "EVO-Plan: new_knowledge — 重试策略优化", status)
    assert _recent_goal_exists(db, "EVO-Plan: new_knowledge — 重试策略优化")


def test_recent_goal_iso_timestamp_format(db):
    """created_at 存 ISO（T+tz）格式也能正确比较。"""
    db.execute(
        "INSERT INTO goals VALUES ('g1','EVO-Plan: X','COMPLETED',"
        "strftime('%Y-%m-%dT%H:%M:%S+00:00','now'))")
    db.commit()
    assert _recent_goal_exists(db, "EVO-Plan: X")


def test_recent_goal_prefix_anchored(db):
    """锚定 description 开头：相似但不同标题不误杀。"""
    _add(db, "EVO-Plan: 旧方案标题", "COMPLETED")
    assert not _recent_goal_exists(db, "EVO-Plan: 全新的不同方案")


def test_recent_goal_outside_window(db):
    _add(db, "EVO-Plan: 8 天前做过的方案", "COMPLETED", when="-8 days")
    assert not _recent_goal_exists(db, "EVO-Plan: 8 天前做过的方案")
    # 窗内（6 天）仍拦
    _add(db, "EVO-Plan: 6 天前做过的方案", "COMPLETED", when="-6 days")
    assert _recent_goal_exists(db, "EVO-Plan: 6 天前做过的方案")


def test_recent_goal_empty_table(db):
    assert not _recent_goal_exists(db, "任何标题")


def test_recent_goal_empty_title(db):
    assert not _recent_goal_exists(db, "")


def test_recent_goal_matches_production_duplicate(db):
    """生产实锤形态：同标题 43 次重复——第二次必被拦。"""
    title = ("EVO-Plan: new_knowledge — 新知识 [procedure] 说 "
             "'✓ [内生] 环境能力探索'")
    _add(db, title, "COMPLETED")
    assert _recent_goal_exists(db, title)


# ── 回声产物判定 ────────────────────────────────────────────────────────────

def test_echo_blocks_mini_plan():
    assert "Mini-Plan" in _echo_artifact_reason(
        "Mini-Plan: deepen_topic — 旧模板", "建议增加 follow-up goal")


def test_echo_blocks_execution_json():
    """执行日志 JSON 被当知识引用（生产 43 次重复的形态）。"""
    r = _echo_artifact_reason(
        "EVO-Plan: new_knowledge — 重试",
        "新知识 [procedure] 说 '{\"success\": false, \"cycle\": 364}'")
    assert r


def test_echo_blocks_nested_knowledge():
    r = _echo_artifact_reason(
        "EVO-Plan: x", "新知识 [concept] 说 'Q: 新知识 [procedure] 说 ...'")
    assert r


def test_echo_blocks_checkmark_echo():
    """本批新增：✓/✗ 执行回显复读（旧闸漏网，生产 25 次）。"""
    r1 = _echo_artifact_reason(
        "EVO-Plan: new_knowledge",
        "新知识 [procedure] 说 '✓ EVO-Plan: new_knowledge — 环境探索完成'")
    assert "回显" in r1
    r2 = _echo_artifact_reason(
        "EVO-Plan: retry", "新知识 [lesson] 说 '✗ Use curl to search GitHub'")
    assert "回显" in r2


def test_echo_allows_genuine_plan():
    """携带真实行动的新方案必须放行。"""
    assert _echo_artifact_reason(
        "EVO-Plan: 修复 writer 交付物空洞",
        "# 行动\n1. 在 bridge 层校验 ANSWER 标记\n"
        "success_criteria: writer 成功率周环比 +10pp") == ""


def test_echo_allows_plain_summary():
    assert _echo_artifact_reason("EVO-Plan: 主题深化", "对失败分类模型做实证研究") == ""
