"""COG-V2 Phase 3: 事件驱动反思 + 成功配方 + 多维 pattern + 自我差距刺激。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ocos.learning.event_reflection import EventReflector
from ocos.learning.recipe_sedimentor import RecipeSedimentor
from ocos.learning.unified_ingestor import IngestResult, IngestStatus
from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.pattern.extractor import PatternExtractor

_EPISODES_DDL = """
CREATE TABLE episodes (
    id TEXT PRIMARY KEY, experience_id TEXT DEFAULT 'x',
    session_id TEXT DEFAULT 'default', context TEXT DEFAULT '{}',
    goal TEXT, decision TEXT DEFAULT '', action TEXT DEFAULT '',
    outcome TEXT DEFAULT '{}', condition TEXT DEFAULT '',
    significance_score REAL DEFAULT 0.5, evaluation_trace TEXT DEFAULT '{}',
    source TEXT DEFAULT 'decision', status TEXT DEFAULT 'active',
    tags TEXT DEFAULT '[]', created_at TEXT
);
"""


def _mk_episodes(db):
    conn = sqlite3.connect(str(db))
    conn.execute(_EPISODES_DDL)
    conn.commit()
    conn.close()


def _insert_ep(db, *, id, action, source="decision", goal="", decision="",
               context=None, outcome=None, tags=None, created_at=None,
               condition=""):
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO episodes (id, action, source, goal, decision, context, "
        "outcome, tags, condition, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (id, action, source, goal, decision,
         json.dumps(context or {}, ensure_ascii=False),
         json.dumps(outcome or {}, ensure_ascii=False),
         json.dumps(tags or [], ensure_ascii=False), condition,
         created_at or datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


class _FakeTutor:
    def __init__(self, answer="失败机理：参数错误。替代方案：先只读检查表结构。检查项：一、schema 先行；二、加超时。"):
        self.answer = answer
        self.questions = []

    def ask(self, question, context_knowledge=""):
        self.questions.append(question)

        class _R:
            success = True
        r = _R()
        r.answer = self.answer
        r.sources = []
        r.confidence = 0.7
        return r


class _FakeIngestor:
    def __init__(self, status=IngestStatus.STORED):
        self.arts = []
        self._status = status

    def ingest(self, artifacts, *, owner=""):
        self.arts.extend(artifacts if isinstance(artifacts, list)
                         else [artifacts])
        return [IngestResult(status=self._status)]


# ── 3.1 事件驱动慢思考 ─────────────────────────────────────────────────

def test_event_reflection_gates_and_storage(tmp_path, monkeypatch):
    db = tmp_path / "er.db"
    _mk_episodes(db)
    # 近 60min 内的真实 failure_lesson（带 cause/cmd/stderr）
    _insert_ep(
        db, id="L1", action="failure_lesson", source="lesson",
        goal="调研 arXiv 论文",
        tags=["failure_lesson", "tool_unavailable"],
        context={"cause": "tool_unavailable",
                 "failure_lesson": {"evidence": {
                     "command": "curl http://x",
                     "stderr": "command blocked"}}})
    tutor, ing = _FakeTutor(), _FakeIngestor()
    er = EventReflector(str(db), tutor=tutor, ingestor=ing)

    # 成功目标不触发
    assert er.reflect_failure("g", {"success": True})["ran"] is False

    # 首次失败 → 反思入库
    res = er.reflect_failure("调研 arXiv 论文", {"success": False})
    assert res["ran"] is True and res["stored"] is True
    assert res["cause"] == "tool_unavailable"
    assert "tool_unavailable" in tutor.questions[0]
    assert ing.arts and ing.arts[0].knowledge_type == "lesson"
    assert "event_reflection" in ing.arts[0].tags

    # 间隔闸：立即第二次被抑制
    res2 = er.reflect_failure("g2", {"success": False})
    assert res2["ran"] is False and res2["reason"] == "interval"

    # 开关闸
    monkeypatch.setenv("OCOS_EVENT_REFLECTION", "0")
    # 先把间隔调小，证明是开关而非间隔在起作用
    monkeypatch.setenv("OCOS_EVENT_REFLECTION_INTERVAL_S", "0")
    assert er.reflect_failure("g3", {"success": False})["reason"] == "disabled"

    # 反思 episode 落库（预算计数的持久依据）
    conn = sqlite3.connect(str(db))
    n = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source='event_reflection'").fetchone()[0]
    conn.close()
    assert n == 1


def test_event_reflection_daily_cap(tmp_path, monkeypatch):
    db = tmp_path / "ercap.db"
    _mk_episodes(db)
    _insert_ep(db, id="L1", action="failure_lesson", source="lesson",
               tags=["failure_lesson", "execution_error"],
               context={"cause": "execution_error"})
    monkeypatch.setenv("OCOS_EVENT_REFLECTION_CAP", "1")
    monkeypatch.setenv("OCOS_EVENT_REFLECTION_INTERVAL_S", "0")
    er = EventReflector(str(db), tutor=_FakeTutor(), ingestor=_FakeIngestor())
    assert er.reflect_failure("g1", {"success": False})["stored"] is True
    res = er.reflect_failure("g2", {"success": False})
    assert res["ran"] is False and res["reason"] == "daily_cap"


def test_event_reflection_no_llm_means_no_product(tmp_path):
    db = tmp_path / "ern.db"
    _mk_episodes(db)
    er = EventReflector(str(db), tutor=None, ingestor=_FakeIngestor())
    res = er.reflect_failure("g", {"success": False})
    assert res["ran"] is False and res["reason"] == "tutor_unavailable"
    conn = sqlite3.connect(str(db))
    n = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE source='event_reflection'").fetchone()[0]
    conn.close()
    assert n == 0


# ── 3.2 成功配方沉淀 ───────────────────────────────────────────────────

def test_recipe_sediment_creates_and_is_idempotent(tmp_path):
    db = tmp_path / "rc.db"
    _mk_episodes(db)
    for i in range(2):
        _insert_ep(
            db, id=f"R{i}", action="researcher.execute",
            goal="调研 arXiv 最新论文",
            decision="输出\n$ curl -s https://arxiv.org/api",
            context={"agent": "researcher", "success": True,
                     "description": "检索 arxiv 论文",
                     "output_excerpt": "$ curl -s https://arxiv.org/api"})
    # 仅 1 次的姿势不达标
    _insert_ep(
        db, id="W1", action="writer.execute",
        decision="$ python3 build.py",
        context={"agent": "writer", "success": True,
                 "description": "开发构建脚本"})
    ing = _FakeIngestor()
    sed = RecipeSedimentor(str(db))
    stats = sed.maybe_sediment(ingestor=ing)
    assert stats["sedimented"] == 1, stats
    art = ing.arts[0]
    assert art.knowledge_type == "procedure"
    assert art.content.startswith("【工具配方】")
    assert "curl" in art.content and "researcher" in art.content

    # 第二次运行：TTL 内同签名不再沉淀
    stats2 = sed.maybe_sediment(ingestor=ing)
    assert stats2["sedimented"] == 0


def test_recipe_failed_marker_allows_retry(tmp_path):
    """生产首跑教训：ingestor 报 stored 但 knowledge 行未落盘（registry
    镜像 fail-open）时，marker 必须记 stored=false 且不构成 TTL 封条，
    下个周期重试；真正落盘后才幂等。"""
    db = tmp_path / "rf.db"
    _mk_episodes(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE knowledge (id TEXT PRIMARY KEY, statement TEXT, "
        "confidence REAL DEFAULT 0.75, status TEXT DEFAULT 'active', "
        "created_at TEXT DEFAULT '', updated_at TEXT)")
    conn.commit()
    conn.close()
    for i in range(2):
        _insert_ep(
            db, id=f"P{i}", action="researcher.execute",
            goal="调研 arXiv 最新论文",
            decision="输出\n$ curl -s https://arxiv.org/api",
            context={"agent": "researcher", "success": True,
                     "description": "检索 arxiv 论文",
                     "output_excerpt": "$ curl -s https://arxiv.org/api"})

    class _PersistingIngestor:
        def __init__(self, persist):
            self.persist = persist
            self.arts = []

        def ingest(self, artifacts, *, owner=""):
            out = []
            for art in artifacts:
                self.arts.append(art)
                if self.persist:
                    c = sqlite3.connect(str(db))
                    c.execute("INSERT OR REPLACE INTO knowledge "
                              "(id, statement) VALUES (?,?)",
                              (art.content_key, art.content))
                    c.commit()
                    c.close()
                out.append(IngestResult(
                    status=IngestStatus.STORED,
                    artifact_id=art.content_key, message="stored"))
            return out

    sed = RecipeSedimentor(str(db))
    # 第 1 轮：ingestor 声称 stored，但行没落盘 → 不算沉淀
    r1 = sed.maybe_sediment(ingestor=_PersistingIngestor(persist=False))
    assert r1["sedimented"] == 0 and r1["skipped"] == 1, r1
    # stored=false marker 留痕
    c = sqlite3.connect(str(db))
    stored_flag = c.execute(
        "SELECT json_extract(context,'$.stored') FROM episodes "
        "WHERE action='tool_recipe'").fetchone()[0]
    c.close()
    assert stored_flag in (0, False)
    # 第 2 轮：签名未被封禁，真正落盘
    r2 = sed.maybe_sediment(ingestor=_PersistingIngestor(persist=True))
    assert r2["sedimented"] == 1 and r2["skipped"] == 0, r2
    # 第 3 轮：stored=true marker 生效，TTL 幂等
    r3 = sed.maybe_sediment(ingestor=_PersistingIngestor(persist=True))
    assert r3["sedimented"] == 0, r3



# ── 3.2 多维 pattern trigger ───────────────────────────────────────────

def _ep(eid, *, agent, success, goal, decision="", tags=(), cause="",
        action=None):
    outcome = {"success": success}
    if cause:
        outcome["cause"] = cause
    return Episode(
        id=eid, experience_id=f"X-{eid}",
        created_at=datetime.now(timezone.utc),
        context={"agent": agent, "description": goal,
                 "output_excerpt": decision},
        goal=goal, decision=decision,
        action=action or f"{agent}.execute",
        outcome=outcome,
        condition=f"agent={agent}, success={str(success).lower()}",
        tags=list(tags), source="decision",
        status=EpisodeStatus.ACTIVE)


def test_pattern_extractor_multidim_triggers():
    ex = PatternExtractor(min_samples=3)
    eps = []
    # 3 次 researcher 检索成功 → task_type×agent 成功键
    for i in range(3):
        eps.append(_ep(f"S{i}", agent="researcher", success=True,
                       goal="检索 arxiv 论文资料"))
    # 3 次 curl tool_unavailable 失败 → tool×cause 失败键
    for i in range(3):
        eps.append(_ep(f"F{i}", agent="researcher", success=False,
                       goal="检索 openalex", decision="$ curl http://x",
                       tags=["failure_lesson", "tool_unavailable"],
                       cause="tool_unavailable"))
    # 3 条旧一维饱和 condition（无任务类型）→ 不应再成组
    for i in range(3):
        eps.append(_ep(f"O{i}", agent="writer", success=True, goal=""))
    cands = ex.extract(eps)
    triggers = [c.trigger_condition for c in cands]
    assert any("task_type=research" in t and "success=true" in t
               for t in triggers), triggers
    assert any("tool=curl" in t and "cause=tool_unavailable" in t
               and "success=false" in t for t in triggers), triggers
    assert not any(t.strip() == "agent=writer, success=true"
                   for t in triggers), triggers


# ── RecallRouter procedural 子库 ───────────────────────────────────────

def test_recall_router_procedural_recipe(tmp_path):
    from ocos.memory.recall_router import RecallRouter
    db = tmp_path / "rp.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE knowledge (id TEXT PRIMARY KEY, statement TEXT,
            confidence REAL, status TEXT DEFAULT 'active',
            source_patterns TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE belief (id TEXT PRIMARY KEY, statement TEXT,
            confidence REAL, status TEXT DEFAULT 'active',
            last_updated TEXT DEFAULT (datetime('now')));
        CREATE TABLE episodes (id TEXT PRIMARY KEY, action TEXT,
            goal TEXT, decision TEXT, outcome TEXT, context TEXT,
            tags TEXT, created_at TEXT);
    """)
    conn.execute(
        "INSERT INTO knowledge VALUES ('k1', ?, 0.8, 'active', '[]', "
        "datetime('now'), datetime('now'))",
        ("【工具配方】researcher 处理检索调研类任务时，`curl -s` 姿势"
         "近 7 天成功 4 次。复用要点：先确认域名可达。",))
    conn.commit()
    conn.close()
    items = RecallRouter(str(db)).recall("调研检索 arXiv 论文")
    proc = [i for i in items if i["subsystem"] == "procedural"]
    assert proc and proc[0]["type"] == "tool_recipe"
    assert "工具配方" in proc[0]["text"]


# ── 3.3 MotivationHub 自我差距刺激 ─────────────────────────────────────

def _hub_db(tmp_path, caps):
    db = tmp_path / "hub.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(_EPISODES_DDL)
    conn.execute(
        "CREATE TABLE agent_self_model (id INTEGER PRIMARY KEY, "
        "version INTEGER, capabilities TEXT, personality TEXT, focus TEXT, "
        "content_hash TEXT, calibrated_at TEXT, failure_modes TEXT)")
    conn.execute(
        "INSERT INTO agent_self_model VALUES (1,1,?,'{}','[]','h',"
        "datetime('now'),'[]')",
        (json.dumps(caps),))
    conn.commit()
    conn.close()
    from ocos.daemon.motivation import MotivationHub
    return db, MotivationHub(str(db))


def test_efficacy_gap_candidate_and_daily_limit(tmp_path):
    db, hub = _hub_db(tmp_path, [
        {"name": "shell", "attempts": 100, "successes": 50},
        {"name": "reviewer", "attempts": 2, "successes": 1},
    ])
    cands = hub._from_efficacy_gap()
    assert len(cands) == 1
    assert cands[0].kind == "LEARN"
    assert "reviewer" in cands[0].description
    assert cands[0].evidence.startswith("efficacy_gap")

    # 当天已提案过同类型 → 自限 1 个
    _insert_ep(db, id="M1", action="autonomous_goal_proposal",
               source="autonomous_goal_proposal",
               decision=cands[0].description,
               outcome={"evidence": "efficacy_gap reviewer n=2 k=1"})
    assert hub._from_efficacy_gap() == []

    # n≥5 不构成差距
    d2dir = tmp_path / "d2"
    d2dir.mkdir()
    db2, hub2 = _hub_db(d2dir, [
        {"name": "shell", "attempts": 50, "successes": 10}])
    assert hub2._from_efficacy_gap() == []


def test_physical_ttl_candidate(tmp_path, monkeypatch):
    import ocos.daemon.boot_awareness as ba
    from ocos.daemon.motivation import MotivationHub
    ctx = tmp_path / "boot_context.json"
    monkeypatch.setattr(ba, "BOOT_CONTEXT_PATH", ctx)
    # 新鲜文件 → 无信号
    ctx.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat()}),
                   encoding="utf-8")
    hub = MotivationHub(str(tmp_path / "m.db"))
    assert hub._from_physical_ttl() == []
    # 过期 8 天 → PROBE 环境复核
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    ctx.write_text(json.dumps({"at": old}), encoding="utf-8")
    cands = hub._from_physical_ttl()
    assert len(cands) == 1 and cands[0].kind == "PROBE"
    assert "环境复核" in cands[0].description
    assert cands[0].evidence.startswith("physical_ttl")
