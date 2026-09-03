"""Phase 50: 成长模块 (Growth) 测试。

验收:
    G1: TechSignal 注入 + sqlite 持久化 + 历史
    G2: LLM 分析信号 → 具体提案 (路径安全校验)
    G3: 自动执行: 快照→改→测→保留; 测试失败自动回滚
    G4: 防失控边界: 禁区路径拒绝, 治理模块拒绝
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

sys_path = str(Path(__file__).resolve().parent.parent.parent)
import sys  # noqa: E402
sys.path.insert(0, sys_path)

from ocos.growth.engine import (  # noqa: E402
    GrowthAnalyzer,
    GrowthEngine,
    GrowthOptimizer,
    GrowthProposal,
    GrowthResult,
    GrowthSignalStore,
    TechSignal,
    PROJECT_ROOT,
)

# 真实存在的测试目标文件 (LLM 提案必须命中磁盘真实文件)
_TARGET_FILE = "ocos/growth/engine.py"
_REAL_CONTENT = (PROJECT_ROOT / _TARGET_FILE).read_text(encoding="utf-8")

DB = "/tmp/ocos_phase50_test.db"

_DEFAULT_SUMMARY = (
    "Python 3.11+ 引入 asyncio.TaskGroup 用于结构化并发,"
    "相比 asyncio.gather 提供更好的取消传播与错误处理,"
    "官方文档推荐新代码优先使用 TaskGroup 管理任务生命周期。"
    "OCOS 的异步调度若仍使用旧式 gather, 可迁移获得收益。"
)


def _sig(topic="asyncio.TaskGroup", summary="", conf=0.8) -> TechSignal:
    return TechSignal(
        topic=topic,
        summary=summary or _DEFAULT_SUMMARY,
        source="hermes",
        source_url="https://docs.python.org/3/library/asyncio-task.html",
        domain="python",
        confidence=conf,
    )


@pytest.fixture(autouse=True)
def _cleanup():
    for suffix in ("", "-wal", "-shm"):
        p = Path(DB + suffix)
        if p.exists():
            p.unlink()
    yield
    for suffix in ("", "-wal", "-shm"):
        p = Path(DB + suffix)
        if p.exists():
            p.unlink()


def _fake_llm(payload: dict) -> Callable[[str], str]:
    def _fn(prompt: str) -> str:
        return json.dumps(payload, ensure_ascii=False)
    return _fn


# ── G1: 信号注入与存储 ────────────────────────────────────────────


class TestSignalStore:
    def test_ingest_and_pending(self):
        store = GrowthSignalStore(DB)
        sid = store.record_signal(_sig())
        assert sid.startswith("sig-")
        pending = store.pending_signals()
        assert len(pending) == 1
        assert pending[0]["topic"] == "asyncio.TaskGroup"
        assert pending[0]["status"] == "received"

    def test_mark_signal(self):
        store = GrowthSignalStore(DB)
        sid = store.record_signal(_sig())
        store.mark_signal(sid, "analyzed", "gr-abc")
        assert len(store.pending_signals()) == 0

    def test_log_and_history(self):
        store = GrowthSignalStore(DB)
        r = GrowthResult(proposal_id="gr-1", status="applied",
                         file_path="ocos/x.py", tests_passed=5, reason="ok")
        store.log_result(r)
        hist = store.history()
        assert len(hist) == 1
        assert hist[0]["status"] == "applied"
        assert hist[0]["tests_passed"] == 5

    def test_get_signal(self):
        store = GrowthSignalStore(DB)
        sid = store.record_signal(_sig())
        row = store.get_signal(sid)
        assert row is not None and row["topic"] == "asyncio.TaskGroup"
        assert store.get_signal("sig-nope") is None

    def test_engine_ingest_short_summary_rejected(self):
        engine = GrowthEngine(store=GrowthSignalStore(DB))
        with pytest.raises(ValueError):
            engine.ingest(TechSignal(topic="t", summary="too short"))


# ── G2: LLM 分析 ──────────────────────────────────────────────────


class TestAnalyzer:
    def test_worthwhile_proposal_parsed(self):
        payload = {
            "worthwhile": True,
            "rationale": "TaskGroup 替代 gather 提升取消传播",
            "file_path": _TARGET_FILE,
            "new_content": "# placeholder new content",
            "applicability": 0.8,
        }
        a = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        p = a.analyze(_sig())
        assert p is not None
        assert p.file_path == _TARGET_FILE
        assert p.applicability == 0.8
        assert p.rationale

    def test_patch_mode_proposal_parsed(self):
        """patch 式: old_snippet 逐字唯一存在于原文 → 接受。"""
        marker = "def _run_tests(self, file_path: str)"
        payload = {
            "worthwhile": True,
            "rationale": "rename for clarity",
            "file_path": _TARGET_FILE,
            "old_snippet": marker,
            "new_snippet": "def _verify_change(self, file_path: str)",
            "applicability": 0.7,
        }
        a = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        p = a.analyze(_sig())
        assert p is not None
        assert p.old_snippet == marker
        assert p.new_snippet.startswith("def _verify")

    def test_patch_old_snippet_must_exist(self):
        """patch 式: old_snippet 不在原文 → 拒绝 (防幻觉)。"""
        payload = {
            "worthwhile": True, "rationale": "r",
            "file_path": _TARGET_FILE,
            "old_snippet": "def this_does_not_exist_anywhere():",
            "new_snippet": "def renamed():",
            "applicability": 0.7,
        }
        a = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        assert a.analyze(_sig()) is None

    def test_not_worthwhile_returns_none(self):
        a = GrowthAnalyzer(llm_fn=_fake_llm(
            {"worthwhile": False, "rationale": "与 OCOS 无关"}))
        assert a.analyze(_sig()) is None

    def test_path_must_be_ocos_py(self):
        a = GrowthAnalyzer(llm_fn=_fake_llm({
            "worthwhile": True, "rationale": "r",
            "file_path": "/etc/passwd", "new_content": "x",
            "applicability": 0.9}))
        assert a.analyze(_sig()) is None

    def test_governance_module_rejected(self):
        a = GrowthAnalyzer(llm_fn=_fake_llm({
            "worthwhile": True, "rationale": "r",
            "file_path": "ocos/governance/policy.py", "new_content": "x",
            "applicability": 0.9}))
        assert a.analyze(_sig()) is None

    def test_nonexistent_file_rejected(self):
        """幻觉路径防护: 文件必须真实存在。"""
        a = GrowthAnalyzer(llm_fn=_fake_llm({
            "worthwhile": True, "rationale": "r",
            "file_path": "ocos/engines/ghost_scheduler.py", "new_content": "x",
            "applicability": 0.9}))
        assert a.analyze(_sig()) is None

    def test_fenced_json_response_parsed(self):
        def _fenced(prompt: str) -> str:
            return "```json\n" + json.dumps({
                "worthwhile": True, "rationale": "r",
                "file_path": _TARGET_FILE,
                "new_content": "y", "applicability": 0.7}) + "\n```"
        a = GrowthAnalyzer(llm_fn=_fenced)
        p = a.analyze(_sig())
        assert p is not None and p.applicability == 0.7

    def test_no_llm_returns_none(self):
        a = GrowthAnalyzer(llm_fn=None)
        assert a.analyze(_sig()) is None

    def test_unparseable_returns_none(self):
        a = GrowthAnalyzer(llm_fn=lambda p: "not json at all")
        assert a.analyze(_sig()) is None

    def test_llm_exception_returns_none(self):
        def _boom(prompt: str) -> str:
            raise RuntimeError("llm down")
        a = GrowthAnalyzer(llm_fn=_boom)
        assert a.analyze(_sig()) is None


# ── G3: 受治理自动执行 ────────────────────────────────────────────


class TestOptimizer:
    def test_validate_path_ok(self):
        o = GrowthOptimizer(PROJECT_ROOT)
        ok, err = o.validate_path(_TARGET_FILE)
        assert ok and err == ""

    def test_validate_path_forbidden_dirs(self):
        o = GrowthOptimizer(PROJECT_ROOT)
        for bad in (".venv/x.py", "ocos/.git/config.py", "ocos_data/db.py",
                    "../outside.py", "/abs/path.py", "ocos/.env"):
            ok, _ = o.validate_path(bad)
            assert not ok, f"should reject {bad}"

    def test_apply_low_applicability_skips(self):
        o = GrowthOptimizer(PROJECT_ROOT)
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path=_TARGET_FILE,
                           new_content="# x", applicability=0.3)
        r = o.apply(p)
        assert r.status == "skipped"
        assert "applicability" in r.reason

    def test_apply_syntax_error_rolls_back(self, tmp_path):
        """语法门: 坏代码即使无测试也必须回滚。"""
        target = tmp_path / "ocos" / "demo" / "mod.py"
        target.parent.mkdir(parents=True)
        original = "VALUE = 'original'\n"
        target.write_text(original)
        o = GrowthOptimizer(tmp_path)
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/demo/mod.py",
                           new_content="def broken(:\n", applicability=0.9)
        r = o.apply(p)
        assert r.status == "rolled_back", f"got {r.status}: {r.reason}"
        assert "syntax" in r.reason
        assert target.read_text() == original

    def test_apply_tests_fail_rolls_back(self, tmp_path):
        """目标文件已存在, 内容可编译但破坏测试 → 测试失败 → 自动回滚原文。"""
        target = tmp_path / "ocos" / "demo" / "mod.py"
        target.parent.mkdir(parents=True)
        original = "VALUE = 'original'\n"
        target.write_text(original)
        tfile = tmp_path / "ocos" / "tests" / "test_mod.py"
        tfile.parent.mkdir(parents=True)
        tfile.write_text("from ocos.demo.mod import VALUE\n"
                         "def test_v(): assert VALUE == 'original'\n")
        o = GrowthOptimizer(tmp_path)
        # 可编译但值改变 → 测试失败
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/demo/mod.py",
                           new_content="VALUE = 'changed'\n", applicability=0.9)
        r = o.apply(p)
        assert r.status == "rolled_back", f"got {r.status}: {r.reason}"
        assert target.read_text() == original

    def test_modifier_refusal_skips(self, tmp_path):
        """注入的 modifier 拒绝 → 不写文件 (skipped)。"""
        class _Refuser:
            def execute(self, **kwargs):
                return {"success": False, "error": "high risk detected"}
        o = GrowthOptimizer(tmp_path)
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/engines/scheduler.py",
                           new_content="# new", applicability=0.9)
        r = o.apply(p, modifier=_Refuser())
        assert r.status == "skipped"
        assert "refused" in r.reason


# ── G4: 端到端编排 ────────────────────────────────────────────────


class TestGrowthEngine:
    def test_grow_once_happy(self):
        store = GrowthSignalStore(DB)
        payload = {
            "worthwhile": True, "rationale": "r",
            "file_path": _TARGET_FILE,
            "new_content": _REAL_CONTENT,  # 原文 → 无实际变更
            "applicability": 0.9,
        }
        analyzer = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        engine = GrowthEngine(store=store, analyzer=analyzer,
                              optimizer=GrowthOptimizer(PROJECT_ROOT))
        out = engine.grow_once(_sig())
        assert out["signal_id"].startswith("sig-")
        assert len(out["proposals"]) == 1
        assert out["proposals"][0]["file_path"] == _TARGET_FILE
        # 自动执行: 内容 = 原文 → 测试通过 → applied
        assert out["results"] and out["results"][0]["status"] == "applied"

    def test_grow_once_auto_execute_false_no_results(self):
        store = GrowthSignalStore(DB)
        payload = {
            "worthwhile": True, "rationale": "r",
            "file_path": _TARGET_FILE, "new_content": _REAL_CONTENT,
            "applicability": 0.9,
        }
        analyzer = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        engine = GrowthEngine(store=store, analyzer=analyzer,
                              optimizer=GrowthOptimizer(PROJECT_ROOT))
        out = engine.grow_once(_sig(), auto_execute=False)
        assert out["results"] == []
        assert len(out["proposals"]) == 1

    def test_analyze_pending_specific_signal(self):
        store = GrowthSignalStore(DB)
        sid = store.record_signal(_sig())
        payload = {
            "worthwhile": True, "rationale": "r",
            "file_path": _TARGET_FILE, "new_content": _REAL_CONTENT,
            "applicability": 0.9,
        }
        analyzer = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        engine = GrowthEngine(store=store, analyzer=analyzer)
        props = engine.analyze_pending(sid)
        assert len(props) == 1
        # 已标记 analyzed → 不再出现在 pending
        assert store.pending_signals() == []
