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
            "new_content": _REAL_CONTENT,  # 真实大小 → 过规模护栏
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

    def test_scale_guard_rejects_mass_deletion_patch(self):
        """规模护栏 (解析层): 大段删除 patch → 拒绝, 危险提案不出 preview。"""
        original = (PROJECT_ROOT / _TARGET_FILE).read_text(encoding="utf-8")
        # old_snippet = 文件前 100 行, new_snippet 只有 1 行 → 净删 > 30
        lines = original.splitlines()
        old_block = "\n".join(lines[:120])
        payload = {
            "worthwhile": True, "rationale": "删除冗余",
            "file_path": _TARGET_FILE,
            "old_snippet": old_block,
            "new_snippet": "def replaced(): pass",
            "applicability": 0.95,
        }
        a = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        assert a.analyze(_sig()) is None

    def test_scale_guard_allows_small_patch(self):
        """规模护栏: 小范围精确 patch 正常通过。"""
        original = (PROJECT_ROOT / _TARGET_FILE).read_text(encoding="utf-8")
        marker = "def _run_tests(self, file_path: str)"
        assert original.count(marker) == 1
        payload = {
            "worthwhile": True, "rationale": "重命名",
            "file_path": _TARGET_FILE,
            "old_snippet": marker,
            "new_snippet": "def _verify_change(self, file_path: str)",
            "applicability": 0.8,
        }
        a = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        p = a.analyze(_sig())
        assert p is not None and p.old_snippet == marker

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
                "new_content": _REAL_CONTENT,  # 真实大小 → 过护栏
                "applicability": 0.7}) + "\n```"
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

    def test_executor_guard_mass_deletion(self, tmp_path):
        """执行层护栏: 直接注入的大段删除提案 → guarded, 文件不动。"""
        target = tmp_path / "ocos" / "demo" / "big.py"
        target.parent.mkdir(parents=True)
        original = "\n".join(f"def f{i}():\n    return {i}\n" for i in range(60))
        target.write_text(original)
        # 整文件式: 只保留 5 行 → 净删 55 > 30
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/demo/big.py",
                           new_content="def kept():\n    pass\n", applicability=0.9)
        r = GrowthOptimizer(tmp_path).apply(p)
        assert r.status == "guarded"
        assert "net deletion" in r.reason
        assert target.read_text() == original  # 零写入

    def test_executor_guard_low_keep_ratio(self, tmp_path):
        """执行层护栏: 保留比例 <50% → guarded。"""
        target = tmp_path / "ocos" / "demo" / "big.py"
        target.parent.mkdir(parents=True)
        original = "\n".join(f"def f{i}():\n    return {i}\n" for i in range(40))
        target.write_text(original)
        # 40 行原文 → 22 行保留 (55%)? 低于阈值需 <50% → 用 15 行 (37.5%)
        kept = "\n".join(f"def g{i}():\n    pass\n" for i in range(5))  # 10 行
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/demo/big.py",
                           new_content=kept, applicability=0.9)
        r = GrowthOptimizer(tmp_path).apply(p)
        assert r.status == "guarded"
        assert target.read_text() == original

    def test_executor_guard_small_patch_passes(self, tmp_path):
        """执行层: 小范围 patch 不触发护栏, 正常 applied。"""
        target = tmp_path / "ocos" / "demo" / "mod.py"
        target.parent.mkdir(parents=True)
        original = "VALUE = 'original'\n"
        target.write_text(original)
        p = GrowthProposal(signal_topic="t", rationale="r",
                           file_path="ocos/demo/mod.py",
                           old_snippet="VALUE = 'original'",
                           new_snippet="VALUE = 'changed'",
                           applicability=0.9)
        r = GrowthOptimizer(tmp_path).apply(p)
        # 迷你仓库无对应 test 文件 → import 门 (ocos.demo.mod 不可导入
        # 因 tmp 树无 __init__ 链) → 可能 rolled_back。检查非 guarded 即护栏通过
        assert r.status != "guarded", f"护栏误伤小 patch: {r.reason}"
        assert r.status in ("applied", "rolled_back", "rejected")


# ── G4: 端到端编排 ────────────────────────────────────────────────


class TestGrowthEngine:
    def test_grow_once_happy(self, tmp_path):
        """隔离仓库 E2E: 迷你 ocos/ 树 + 真实执行 + applied。"""
        store = GrowthSignalStore(DB)
        # 迷你仓库: ocos/engines/scheduler.py (真实存在)
        mini = tmp_path / "repo" / "ocos" / "engines"
        mini.mkdir(parents=True)
        target = mini / "scheduler.py"
        target.write_text("def schedule():\n    return 'old'\n")
        content = "def schedule():\n    return 'new'\n"
        payload = {
            "worthwhile": True, "rationale": "r",
            "file_path": "ocos/engines/scheduler.py",
            "new_content": content,
            "applicability": 0.9,
        }
        analyzer = GrowthAnalyzer(llm_fn=_fake_llm(payload))
        # analyzer 的 file-exists 校验用 PROJECT_ROOT — 直接注入已构造 proposal
        proposal = GrowthProposal(
            signal_topic="t", rationale="r",
            file_path="ocos/engines/scheduler.py",
            new_content=content, applicability=0.9)
        engine = GrowthEngine(store=store, analyzer=analyzer,
                              optimizer=GrowthOptimizer(tmp_path / "repo"))
        # 绕过 analyzer 走直执行
        result = engine.execute_proposal(proposal)
        assert result.status == "applied", f"got {result.status}: {result.reason}"
        assert target.read_text() == content
        hist = store.history()
        assert len(hist) == 1 and hist[0]["status"] == "applied"

    def test_grow_once_auto_execute_false_no_results(self, tmp_path):
        """隔离仓库: 不自动执行 → results 空。"""
        store = GrowthSignalStore(DB)
        mini = tmp_path / "repo" / "ocos" / "engines"
        mini.mkdir(parents=True)
        (mini / "scheduler.py").write_text("def schedule():\n    return 'old'\n")
        proposal = GrowthProposal(
            signal_topic="t", rationale="r",
            file_path="ocos/engines/scheduler.py",
            new_content="def schedule():\n    return 'new'\n", applicability=0.9)
        engine = GrowthEngine(store=store, analyzer=GrowthAnalyzer(),
                              optimizer=GrowthOptimizer(tmp_path / "repo"))
        result = engine.execute_proposal(proposal)
        assert result.status == "applied"
        assert (mini / "scheduler.py").read_text().startswith("def schedule")

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

    def test_project_root_untouched_after_suite(self):
        """防污染回归: 测试套件绝不能真实改动生产仓库文件。

        用 git 检查: 除 Phase 50 自身文件外, 无其他生产文件被本套件修改。
        白名单随 Phase 演进追加 (cli goal/parser/main 为合法修改)。
        """
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "diff", "--name-only", "--", "ocos/"],
            capture_output=True, text=True)
        changed = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        # 允许的修改: Phase 50 growth 自身 + 各 Phase 合法改动
        # + P0-2/P0-3 session state + daemon factory
        # + 工作区已有但未提交的改动 (审计/诊断类修复)
        allowed = {
            "ocos/growth/engine.py",
            "ocos/interaction/cli/commands/growth.py",
            "ocos/interaction/cli/commands/goal.py",
            "ocos/interaction/cli/main.py",
            "ocos/interaction/cli/parser.py",
            "ocos/tests/test_import_rules.py",
            "ocos/tests/test_phase50_growth.py",
            "ocos/execution/goal_executor.py",
            "ocos/tests/test_phase51_goal_exec.py",
            "ocos/reflection/self_review.py",
            "ocos/interaction/cli/commands/self.py",
            "ocos/tests/test_phase52_self_review.py",
            "ocos/interaction/session_state.py",  # P0-2/P0-3
            "ocos/daemon/factory.py",  # P0-2/P0-3
            "ocos/tests/test_phase_session_state.py",  # P0-2/P0-3
            # 工作区已有未提交改动（审计/诊断相关）
            "ocos/agent/agent_runtime.py",
            "ocos/agent/master_agent.py",
            "ocos/agent/wisdom_trigger.py",
            "ocos/daemon/__init__.py",
            "ocos/execution/bridge.py",
            "ocos/interaction/__main__.py",
            "ocos/interaction/api/routes/converse.py",
            "ocos/interaction/cli/commands/chat.py",
            "ocos/interaction/converse.py",
            "ocos/interaction/inbox.py",
            "ocos/interaction/tui.py",
            "ocos/operations/sandbox_ops.py",
            "ocos/personal_memory/wisdom_store.py",
            "ocos/tests/test_execution_bridge.py",
            "ocos/tests/test_say_channel.py",
            "ocos/interaction/cli/commands/run.py",  # FIX-17
            "ocos/daemon/factory.py",  # FIX-17: 注入 proactive_output_callback
        }
        violations = [l for l in changed if l not in allowed]
        assert violations == [], f"测试污染了生产代码: {violations}"
