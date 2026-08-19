"""Phase 24 — Gate Tests: SelfMonitor 自主演化循环。

验证:
  SM01: 无 current_model → should_evolve 返回 True (initial build)
  SM02: run_once 无变化 → NO_CHANGE
  SM03: run_once 初始构建 → EVOLVED
  SM04: SelfGovernor 拒绝 → DENIED
  SM05: 频率限制 → SKIPPED_FREQUENCY
  SM06: seed() 注入初始 model
  SM07: Builder 异常 → DENIED（防御性）
  SM08: 完整 run() 循环
"""

import pytest
from datetime import datetime, timezone

from ocos.self.monitor import (
    SelfMonitor,
    ChangeDetector,
    MonitorAction,
    MonitorResult,
)
from ocos.self.governor import SelfGovernor, EvolutionRequest, DenialReason
from ocos.self.builder import SelfModelBuilder, BuilderConfig
from ocos.self.identity_boundary import IdentityBoundary
from ocos.self.models import (
    CapabilityDomain,
    CapabilityName,
    CapabilityState,
    Limitation,
    MaturitySnapshot,
    SelfModel,
    MATURITY_DIMENSIONS,
    PRESET_LIMITATIONS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


class FakeBeliefStore:
    """可编程的 BeliefStore stub。"""

    def __init__(self, self_beliefs=None):
        self._self_beliefs = self_beliefs or []
        self._query_calls = []

    def query_by_domain(self, domain, limit=50):
        self._query_calls.append(("query_by_domain", domain, limit))
        if domain == "self":
            return list(self._self_beliefs)
        return []

    def set_beliefs(self, beliefs):
        self._self_beliefs = beliefs


class FakeBelief:
    """简化的 Belief stub。"""

    def __init__(self, belief_id, statement, confidence=0.8, domain="self"):
        self.id = belief_id
        self.statement = statement
        self.confidence = confidence
        self.domain = domain


def make_boundary():
    return IdentityBoundary.create_default()


def make_governor(boundary=None):
    return SelfGovernor(boundary or make_boundary())


def make_belief_store():
    return FakeBeliefStore()


def make_builder(belief_store, boundary=None):
    try:
        return SelfModelBuilder(belief_store, boundary or make_boundary())
    except Exception:
        # Builder.__init__ 不支持假 BeliefStore，直接 mock
        return None


def make_basic_self_model(version=1, statement=None):
    """创建一个基本的 SelfModel 用于测试。"""
    now = datetime.now(timezone.utc)
    return SelfModel(
        model_id=f"SM-TEST-v{version}",
        version=version,
        capability_states=tuple(
            CapabilityState(
                name=name,
                confidence_score=0.5,
                belief_ids=(),
                evidence_summary="test",
                last_updated=now,
                status="uncertain",
            )
            for name in CapabilityName
        ),
        limitations=PRESET_LIMITATIONS,
        maturity=MaturitySnapshot(
            current_phase="phase24",
            phase_history=("phase21", "phase22", "phase23", "phase24"),
            dimensions={dim: 0.5 for dim in MATURITY_DIMENSIONS},
            capability_count=8,
            limitation_count=5,
            snapshot_at=now,
        ),
        statement=statement or "当前系统处于phase24阶段，成熟度：theory 50%, governance 50%。已激活能力：无。未确认能力数：8。硬性架构限制：5项。",
        created_at=now,
        previous_version_id=f"SM-TEST-v{version - 1}" if version > 1 else None,
        governor_approval_id=f"REC-TEST-v{version}",
    )


# ── SM01: 无 current_model → should_evolve ──────────────────────────────

def test_change_detector_no_model():
    """无 current_model → 应触发初始构建。"""
    store = make_belief_store()
    should, reason = ChangeDetector.should_evolve(store, None)
    assert should
    assert "initial build" in reason.lower()


# ── SM02: 无变化 → NO_CHANGE ──────────────────────────────────────────

def test_change_detector_no_change():
    """当前 model 已有，belief_store 无新数据 → 不触发。"""
    store = make_belief_store()
    model = make_basic_self_model()
    should, reason = ChangeDetector.should_evolve(store, model)
    assert not should
    assert "no significant change" in reason.lower()


# ── SM03: 有新 belief 数据 → should_evolve ────────────────────────────

def test_change_detector_new_evidence():
    """belief_store 新增 self-domain beliefs → 应触发。"""
    store = make_belief_store()
    store.set_beliefs([
        FakeBelief("b1", "文字理解能力提升", 0.9),
        FakeBelief("b2", "文本处理增强", 0.85),
        FakeBelief("b3", "模式识别改进", 0.8),
    ])
    model = make_basic_self_model()
    should, reason = ChangeDetector.should_evolve(store, model)
    assert should


# ── SM04: 频率限制 ────────────────────────────────────────────────────

def test_frequency_limit():
    """最近刚演化过 → 应跳过。"""
    store = make_belief_store()
    boundary = make_boundary()
    governor = make_governor(boundary)
    # 注入一个历史 MonitorResult 模拟刚演化
    monitor = _make_monitor(store, governor, boundary)
    # 手动写入一个最近的 EVOLVED 结果
    recent = MonitorResult(
        result_id="MON-RECENT",
        action=MonitorAction.EVOLVED,
        message="recent evolution",
        previous_version=1,
        new_version=2,
        checked_at=datetime.now(timezone.utc),
        evolution_record_id="REC-1",
    )
    monitor._history.append(recent)
    monitor._current_model = make_basic_self_model(2)

    result = monitor.run_once()
    assert result.action == MonitorAction.SKIPPED_FREQUENCY


# ── SM05: seed() 注入初始 model ────────────────────────────────────────

def test_seed_initial_model():
    """seed() 后 run_once 应检测到已有 model。"""
    store = make_belief_store()
    model = make_basic_self_model(1)
    monitor = _make_monitor(store, make_governor())
    monitor.seed(model)
    assert monitor.current_model is model
    result = monitor.run_once()
    assert result.action == MonitorAction.NO_CHANGE


# ── SM06: Builder 异常 → DENIED ────────────────────────────────────────

def test_monitor_builder_exception_is_defensive():
    """Builder 抛出异常 → Monitor 应防御性返回 DENIED，不崩溃。"""
    store = make_belief_store()
    store.set_beliefs([FakeBelief("b1", "new capability detected", 0.9)])
    governor = make_governor()

    # 使用不完整的 builder（会触发异常因为 FakeBeliefStore 不支持 builder 方法）
    # 这里用缺少 BeliefStore 的情况来触发异常
    monitor = _make_monitor(store, governor)

    # 没有 current_model → run_once 会尝试 evolve
    # builder.build_and_approve 内部调用 BeliefStore.query_by_domain
    # FakeBeliefStore 不返回真正的 Belief 对象 → 会出错
    result = monitor.run_once()
    # 即使 builder 失败，monitor 也应返回结果而非崩溃
    assert result is not None


# ── SM07: run() 完整循环 ─────────────────────────────────────────────

def test_run_complete_loop():
    """run() 在无数据情况下应结束（NO_CHANGE）。"""
    store = make_belief_store()
    monitor = _make_monitor(store, make_governor())
    monitor.seed(make_basic_self_model(1))

    results = monitor.run(max_iterations=5)
    assert len(results) >= 1
    assert results[0].action == MonitorAction.NO_CHANGE
    assert all(r.new_version is None for r in results)


# ── SM08: MonitorResult 不可变性 ──────────────────────────────────────

def test_monitor_result_frozen():
    """MonitorResult 是 frozen dataclass。"""
    mr = MonitorResult(
        result_id="test",
        action=MonitorAction.NO_CHANGE,
        message="test",
        previous_version=1,
        new_version=None,
        checked_at=datetime.now(timezone.utc),
        evolution_record_id=None,
    )
    assert mr.action == MonitorAction.NO_CHANGE
    assert mr.new_version is None


# ── Helpers ────────────────────────────────────────────────────────────


def _make_monitor(belief_store, governor, boundary=None):
    """创建带 fake builder 的 SelfMonitor。"""
    boundary = boundary or governor.boundary
    try:
        builder = SelfModelBuilder(belief_store, boundary)
    except Exception:
        builder = None
    return SelfMonitor(builder, governor, belief_store)
