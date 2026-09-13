"""R10 Perception Causality Audit — 观测→决策传播链 A/B 实验。

用户裁决 R10 标准（2026-09-08）: 能力产物必须能通过生产路径改变后续行为，
且有可重复的行为级证据；静态审计推断（模块存在/函数被调/数据落库均无效）。

本文件 = 传播级 A/B（确定性、无 LLM）:
  Treatment: inject_user_message(marker) → tick() →
             Step1 摄入(trace_id) → Step2 Attention → Step3 WM(summary+trace_id)
             → learning_artifacts(MEM_CTX) 召回观测(marker+trace_id)
  Control:   同构造无注入 → 全链无 marker
  PASS 判据: T 全链可见同一 trace_id，C 全链不可见。

行为级 A/B（真 LLM、生产 daemon 多轮）由脚本侧执行，见
~/.ocos/artifacts/r10_causality_report.md。
"""

from __future__ import annotations

import pytest

MARKER = "R10ZEBRA7741"
MARKER_TEXT = f"环境观测通报 {MARKER}: R10 因果实验信号注入"


def _build_runtime(db_file: str):
    from ocos.agent.agent_runtime import AgentRuntime
    from ocos.daemon.factory import build_master_agent

    _agent, _ = build_master_agent("t", db_path=":memory:")
    rt = AgentRuntime(agent=_agent, max_cycles=10, db_path=db_file)
    rt.boot()
    return rt


class TestR10TransmissionAB:
    """传播级 A/B: Observation → Attention → WM → Recall(MEM_CTX)。"""

    def test_treatment_marker_flows_full_chain(self, tmp_path):
        rt = _build_runtime(str(tmp_path / "r10_treatment.db"))

        out = rt.inject_user_message(MARKER_TEXT, sender="r10")
        assert out["accepted"], "注入必须被 EventBus 接受"

        tick = rt.tick()
        steps = {s.get("step"): s for s in tick["steps"]}

        # ── Stage 1: Observe（EventBus → ingest, trace_id 生成）──
        s1 = steps.get(1) or {}
        assert s1.get("status") != "no_events", "注入事件必须被 Step1 摄入"
        traces = s1.get("traces") or []
        assert traces, "Step1 必须产出事件 trace"
        t1 = next((t for t in traces if MARKER in (t.get("summary") or "")), None)
        assert t1 is not None, "Step1 trace 必须携带 marker 原文"
        trace_id = t1.get("trace_id") or ""
        assert trace_id.startswith("TRC-"), f"trace_id 缺失: {trace_id!r}"

        # ── Stage 2+3: Attention → WM（summary + trace_id 落 WM）──
        s3 = steps.get(3) or {}
        assert s3.get("wm_writes_from_attention", 0) >= 1, (
            "Attention 必须给用户消息分配 WM slot（DISMISSED 则断链）")

        keys = rt._wm_store.list_keys("attention:%")
        hit = None
        for k in keys:
            v = rt._wm_store.load(k) or {}
            if MARKER in (v.get("summary") or ""):
                hit = (k, v)
                break
        assert hit is not None, "WM 必须存在携带 marker 的观测条目"
        _, wm_val = hit
        assert wm_val.get("trace_id") == trace_id, (
            f"trace_id 必须全链同值: WM={wm_val.get('trace_id')!r} vs Step1={trace_id!r}")

        # ── Stage 4: Recall（MEM_CTX 观测召回 — R10-UNIFY 修复点）──
        artifacts = rt.learning_artifacts(f"汇总最新环境观测 {MARKER}")
        obs = [a for a in artifacts if a.get("type") == "observation"]
        assert obs, "MEM_CTX 必须召回 WM 观测（R10-UNIFY）"
        assert any(MARKER in (a.get("text") or "") for a in obs), (
            f"MEM_CTX 观测文本必须携带 marker: {obs}")
        assert any(trace_id in (a.get("artifact_id") or "") for a in obs), (
            "MEM_CTX 观测 artifact_id 必须携带同一 trace_id")

    def test_control_no_marker_anywhere(self, tmp_path):
        rt = _build_runtime(str(tmp_path / "r10_control.db"))

        rt.tick()  # 无注入

        # WM 无 marker
        for k in rt._wm_store.list_keys("attention:%"):
            v = rt._wm_store.load(k) or {}
            assert MARKER not in (v.get("summary") or "")

        # MEM_CTX 无 marker 观测
        artifacts = rt.learning_artifacts(f"汇总最新环境观测 {MARKER}")
        for a in artifacts:
            assert MARKER not in (a.get("text") or ""), (
                f"Control 组 MEM_CTX 不得出现 marker: {a}")

    def test_ab_divergence(self, tmp_path):
        """同一 runtime、同一询问 — 注入前后 MEM_CTX 因 marker 而不同。"""
        rt = _build_runtime(str(tmp_path / "r10_ab.db"))
        question = "汇总当前环境观测的关键标识"

        before = rt.learning_artifacts(question)
        before_marker = [a for a in before if MARKER in (a.get("text") or "")]

        rt.inject_user_message(MARKER_TEXT, sender="r10")
        rt.tick()

        after = rt.learning_artifacts(question)
        after_marker = [a for a in after if MARKER in (a.get("text") or "")]

        assert not before_marker, "注入前 MEM_CTX 不应有 marker"
        assert after_marker, "注入后 MEM_CTX 必须出现 marker（观测改变决策输入）"


class TestAnswerChainRecall:
    """行为级断点修复验证: 回答链 build_context 必须召回 WM 观测。

    R10 行为级 A/B 实锤 (2026-09-12): learning_artifacts 无生产调用方,
    WM 观测对回答链不可见 → 注入 marker 后回答 0/3 引用。修复后
    build_context 注入"最新感知观测(WM)"块。
    """

    def test_build_context_surfaces_wm_observation(self, tmp_path):
        from ocos.interaction.converse import ChatResponder
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db = str(tmp_path / "r10_ctx.db")
        wm = SQLiteWorkingMemory(db)
        wm.store(key="attention:environmental_scan:EV-ctx1", value={
            "event_id": "EV-ctx1", "slot": "environmental_scan",
            "attention_weight": 0.5, "decision": "QUEUED",
            "trace_id": "TRC-ctx1234abcd", "summary": f"User says: {MARKER}"})

        responder = ChatResponder(db_path=db)
        ctx = responder.build_context("汇总当前环境观测的关键标识")
        assert MARKER in ctx, "回答链上下文必须出现 WM 观测 marker"
        assert "TRC-ctx1234abcd" in ctx, "观测 trace_id 必须随上下文透出"

    def test_build_context_without_observations_is_clean(self, tmp_path):
        from ocos.interaction.converse import ChatResponder
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db = str(tmp_path / "r10_ctx_ctrl.db")
        SQLiteWorkingMemory(db)  # 空 WM
        responder = ChatResponder(db_path=db)
        ctx = responder.build_context("汇总当前环境观测的关键标识")
        assert MARKER not in ctx


class TestUserInputPriorityLane:
    """断点①修复验证: sensor 洪流下 USER_INPUT 不被 maxlen 挤兑饿死。

    生产行为级 A/B 实锤 (2026-09-12): Step1 每 tick ingest 10 条,
    sensor 事件灌满 deque(maxlen=1000) 后从头部挤掉排队中的用户消息
    (marker 注入 → WM 查无此事件)。
    """

    def test_user_input_survives_sensor_flood(self):
        from ocos.perception_bus import EventBus, RawEvent, EventSource

        bus = EventBus(max_pending=100)
        # 洪流: 500 条 sensor 事件灌满并挤兑通用车道
        for i in range(500):
            bus.push(RawEvent(source=EventSource.SYSTEM,
                              payload={"type": "cpu_spike", "seq": i}))
        # 用户消息排在洪流之后注入
        ce = bus.push_user_message(f"用户消息 {MARKER}", sender="r10")

        drained = bus.ingest(max_events=10)
        assert ce.event_id in [e.event_id for e in drained], (
            "USER_INPUT 必须优先于 sensor 洪流被消费（双车道）")
        assert any(MARKER in e.summary for e in drained)

    def test_fifo_order_within_lanes_preserved(self):
        from ocos.perception_bus import EventBus, RawEvent, EventSource

        bus = EventBus()
        bus.push(RawEvent(source=EventSource.SYSTEM,
                          payload={"type": "cpu_spike", "seq": 1}))
        ce_u1 = bus.push_user_message("第一条用户消息", sender="r10")
        ce_u2 = bus.push_user_message("第二条用户消息", sender="r10")

        drained = bus.ingest(max_events=10)
        ids = [e.event_id for e in drained]
        assert ids.index(ce_u1.event_id) < ids.index(ce_u2.event_id), (
            "同车道内保持 FIFO")


class TestRecallUnderNoise:
    """断点②修复验证: sensor 噪声淹没后 user_input 观测仍被召回。

    行为级 A/B 二轮实锤: recent(limit=2) 小窗口下 sensor 每 tick 10+
    条新观测, marker 几分钟即被挤出召回窗口 → MEM_CTX 看不到。
    行为级 A/B 三轮实锤 (2026-09-12): 生产 sensor 吞吐每秒数十条,
    recent(limit=20) 时间窗口内排序守不住 — marker 落库 3s 后即被
    冲出窗口 → T 0/3 引用。修复: recent_by_source 按信源保底召回。
    """

    def test_user_input_recalled_despite_sensor_noise(self, tmp_path):
        rt = _build_runtime(str(tmp_path / "r10_noise.db"))
        wm = rt._wm_store

        # 15 条 sensor 噪声（新）+ 1 条 user_input（更旧，被淹没）
        for i in range(15):
            wm.store(key=f"attention:environmental_scan:EV-noise{i}", value={
                "event_id": f"EV-noise{i}", "slot": "environmental_scan",
                "attention_weight": 0.18, "decision": "QUEUED",
                "trace_id": f"TRC-noise{i:04d}",
                "summary": f"System cpu_spike seq={i}",
                "source": "system"})
        wm.store(key="attention:environmental_scan:EV-marker", value={
            "event_id": "EV-marker", "slot": "environmental_scan",
            "attention_weight": 0.18, "decision": "QUEUED",
            "trace_id": "TRC-marker0000",
            "summary": f"User says: 环境观测通报 {MARKER}",
            "source": "user_input"})
        # 噪声之后又来 5 条（marker 距今更远）
        for i in range(15, 20):
            wm.store(key=f"attention:environmental_scan:EV-noise{i}", value={
                "event_id": f"EV-noise{i}", "slot": "environmental_scan",
                "attention_weight": 0.18, "decision": "QUEUED",
                "trace_id": f"TRC-noise{i:04d}",
                "summary": f"System cpu_spike seq={i}",
                "source": "system"})

        artifacts = rt.learning_artifacts("汇总当前环境观测的关键标识")
        obs = [a for a in artifacts if a.get("type") == "observation"]
        assert any(MARKER in (a.get("text") or "") for a in obs), (
            f"user_input 观测被噪声淹没后必须仍被召回: {obs}")
        # user_input 观测必须排在 sensor 噪声前
        if len(obs) > 1:
            assert MARKER in (obs[0].get("text") or ""), (
                f"user_input 观测必须排在噪声前: {[a.get('text') for a in obs]}")

    def test_user_input_recalled_after_window_flush(self, tmp_path):
        """三轮实锤回归: marker 落库后被 >20 条噪声冲出时间窗口，
        recent(limit=20) 已看不到 → recent_by_source 保底召回必须生效。
        """
        from ocos.interaction.converse import ChatResponder
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db = str(tmp_path / "r10_flush.db")
        wm = SQLiteWorkingMemory(db)
        wm.store(key="attention:environmental_scan:EV-user", value={
            "event_id": "EV-user", "slot": "environmental_scan",
            "attention_weight": 0.18, "decision": "QUEUED",
            "trace_id": "TRC-user000000",
            "summary": f"User says: 环境观测通报 {MARKER}",
            "source": "user_input"})
        # 25 条噪声把 marker 挤出 recent(limit=20) 窗口
        for i in range(25):
            wm.store(key=f"attention:environmental_scan:EV-f{i}", value={
                "event_id": f"EV-f{i}", "slot": "environmental_scan",
                "attention_weight": 0.18, "decision": "QUEUED",
                "trace_id": f"TRC-flush{i:03d}",
                "summary": f"Process started: sleep pid={i}",
                "source": "system"})

        assert not any(
            MARKER in str((o.get("value") or {}).get("summary", ""))
            for o in wm.recent(prefix="attention:", limit=20)), (
            "前置条件: marker 必须已被冲出时间窗口")

        responder = ChatResponder(db_path=db)
        ctx = responder.build_context("汇总当前环境观测的关键标识")
        assert MARKER in ctx, (
            "窗口冲刷后回答链上下文必须经 recent_by_source 保底召回 marker")


class TestEvictionProtectsUserInput:
    """断点③修复验证: LRU 驱逐不得清掉最新 user_input 观测。

    六轮 A/B 实锤 (2026-09-12): 生产 sensor 洪流 ~50 条/s，按 rowid 最老
    优先驱逐时用户消息 30s 内被清空 — marker T1 轮可召回、T2 轮已被
    驱逐（WM 内 0 条 R10ZEBRA）。修复: 最新 20 条 user_input 免驱逐。
    """

    def test_user_input_survives_lru_eviction(self, tmp_path):
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db = str(tmp_path / "r10_evict.db")
        wm = SQLiteWorkingMemory(db, max_entries=50)
        wm.store(key="attention:environmental_scan:EV-user-keep", value={
            "event_id": "EV-user-keep", "slot": "environmental_scan",
            "trace_id": "TRC-keep000000", "summary": f"User says: {MARKER}",
            "source": "user_input"})
        # 洪流灌满触发驱逐（50 上限，一次驱逐 5 条，60 条足以多轮触发）
        for i in range(60):
            wm.store(key=f"attention:environmental_scan:EV-e{i}", value={
                "event_id": f"EV-e{i}", "slot": "environmental_scan",
                "trace_id": f"TRC-evict{i:03d}", "summary": f"noise {i}",
                "source": "system"})

        kept = wm.load("attention:environmental_scan:EV-user-keep")
        assert kept is not None, "最新 user_input 观测必须免于 LRU 驱逐"
        assert MARKER in (kept.get("summary") or "")

    def test_old_user_input_beyond_cap_still_evictable(self, tmp_path):
        from ocos.storage.working_memory import SQLiteWorkingMemory

        db = str(tmp_path / "r10_evict_cap.db")
        wm = SQLiteWorkingMemory(db, max_entries=100)
        # 25 条旧 user_input（最老 5 条超出 20 条保护帽）+ 80 条 system
        # = 105 > 100 → 触发驱逐 10 条: 保护帽外的 5 条旧 user_input +
        # 5 条最老 system。保护帽内 20 条 user_input 必须存活。
        for i in range(25):
            wm.store(key=f"attention:environmental_scan:EV-u{i}", value={
                "event_id": f"EV-u{i}", "slot": "environmental_scan",
                "trace_id": f"TRC-u{i:03d}", "summary": f"user msg {i}",
                "source": "user_input"})
        for i in range(80):
            wm.store(key=f"attention:environmental_scan:EV-s{i}", value={
                "event_id": f"EV-s{i}", "slot": "environmental_scan",
                "trace_id": f"TRC-s{i:03d}", "summary": f"noise {i}",
                "source": "system"})

        keys = set(wm.list_keys("attention:%"))
        assert len(keys) <= 100, "驱逐后不得超容量"
        surviving_u = sorted(
            int(k.split("EV-u")[1]) for k in keys if "EV-u" in k)
        assert len(surviving_u) >= 20, (
            f"保护帽内 20 条 user_input 必须存活: {surviving_u}")
        assert all(i >= 5 for i in surviving_u), (
            f"被驱逐的必须只是保护帽外最老的 5 条: {surviving_u}")
