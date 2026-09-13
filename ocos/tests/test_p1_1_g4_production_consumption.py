"""P1-1 G4 Scope Amendment — 生产 Thinking 消费验证（P-E1~P-E6）。

Human Gate 终裁（G4 Scope Amendment = GO）指出的唯一缺口：G4-E 只在测试内
deterministic consumer 上证明消费，未证明**生产 Thinking 真正消费 W1**。

本文件把消费链挂到真实生产宿主 ChatResponder（ocos/interaction/converse.py）：

    committed W1 → SelfProjectionAccessor → WorldViewReadAdapter
        → ThinkingContextProvider → ChatResponder.build_context()
        → 生产 Thinking Context / Prompt
        → ChatResponder 真实 reasoning path（fake provider 挂载点，P-E1 允许）

执行标准（P-E1~P-E6）：
  P-E1 生产 Reasoning Consumer：deterministic fake provider 挂在真实
       ChatResponder.respond() 路径上，消费的是生产 prompt（含 build_context 产物）。
  P-E2 生产 Prompt 差分：Prompt(W0) ≠ Prompt(W1)，且唯一新增变量可定位 =
       committed worldview block（剥离块后逐字节相等）。
  P-E3 零影响基线：无 W1 → 生产 context 逐字节不变（G4 注入完全惰性）。
  P-E4 Authority Boundary：生产 Thinking 消费后 committed S2 全等（version /
       hash / update_history / worldview）——消费能力 ≠ Self Mutation Authority。
  P-E5 I2 溯源：生产 context / prompt 中的 worldview 行携带 claim_id / evidence
       计数，与 committed 块一致。
  P-E6 回归：既有 context 块（身份/认知引擎/真实能力）与回复结构不受影响。

「无 W1」与「消费失败」严格区分：无 W1 → 块为空、context 不变、无日志；
accessor/adapter/assembly 异常 → logger.error（不得静默降级成"没有 worldview"）。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ocos.engines.text_generator import LLMProvider
from ocos.interaction.converse import ChatResponder
from ocos.self.self_evidence import EvidenceObservation, S1Evidence, SelfEvidencePipeline
from ocos.self.self_state import SelfStateManager, register_self_projection

AGENT = "g4-prod-agent"
REAL_HASH = "hash-real-g4-prod"

WV_HEADER = "世界观（committed，结构化投影）:"
MSG = "你好，帮我看看现在的情况"


# ── 真实 Experience 解析器（与 G3/G4 同协议，W1 一律经 G3 frozen 链形成）───────


class _Episode:
    def __init__(self, eid, identity_ref, data_hash, n_obs):
        self.eid = eid
        self.identity_ref = identity_ref
        self.data_hash = data_hash
        self.associated_observations = list(range(n_obs))


class _Resolver:
    def __init__(self, episodes):
        self._eps = {e.eid: e for e in episodes}

    def resolve(self, episode_id):
        return self._eps.get(episode_id)


def _wv_evidence(data_hash, domain, expected, actual, trigger_episode) -> S1Evidence:
    meta = tuple(sorted({
        "domain": domain,
        "expected": expected,
        "actual": actual,
        "trigger_episode": trigger_episode,
    }.items()))
    obs = EvidenceObservation(key="wv.experience", value=f"ep:{trigger_episode}",
                              meta=meta)
    return S1Evidence(
        evidence_id=f"E-{uuid.uuid4().hex[:8]}",
        source="runtime",
        observed_at=datetime.now(timezone.utc),
        s1_version=1,
        s1_content_hash="sh",
        data_hash=data_hash,
        observations=(obs,),
    )


# ── 生产宿主接线辅助 ────────────────────────────────────────────────────────


def _boot(db: str):
    """boot S2 + 注册唯一 accessor（模拟 AgentRuntime boot），返回 manager。"""
    m = SelfStateManager(db)
    m.boot(AGENT)
    register_self_projection(db, m.accessor)
    return m


def _make_w1(m) -> SelfEvidencePipeline:
    """经 G3 frozen 链形成 committed W1（FIRST / NOVEL_PATTERN）。"""
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    committed = pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                             "EP-NOVEL"))
    assert len(committed) == 1, "真实经历必须产出 1 条 committed W1 delta"
    return pipeline


class _FakeProvider(LLMProvider):
    """挂在真实 ChatResponder.respond() 路径上的 deterministic fake provider。

    只记录生产 prompt（respond 组装产物，内嵌 build_context 输出）并返回固定
    回答；不伪造推理、不触碰 S2。P-E1/P-E2 的生产证据采集点。
    """

    def __init__(self) -> None:
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "fake"

    async def generate(self, prompt, system_prompt=None, temperature=0.8,
                       max_tokens=2000) -> str:
        self.prompts.append(prompt)
        return "收到。我会基于当前上下文与既有经验理解这个问题。"


def _hook_fake_provider(responder: ChatResponder, monkeypatch) -> _FakeProvider:
    """让 respond() 走真实 provider 分支，且 provider = fake（P-E1 允许）。"""
    fake = _FakeProvider()
    monkeypatch.setattr(responder, "_has_real_llm", lambda: True)
    monkeypatch.setattr("ocos.engines.text_generator.TextGenerator",
                        lambda: SimpleNamespace(_provider=fake))
    return fake


def _strip_wv_block(text: str) -> str:
    """剥离 worldview 消费块（G4 接线的唯一新增变量），用于 P-E2 差分归因。"""
    out: list[str] = []
    skipping = False
    for ln in text.split("\n"):
        if ln.startswith(WV_HEADER):
            skipping = True
            continue
        if skipping:
            if ln.startswith("  ["):
                continue
            skipping = False
        out.append(ln)
    return "\n".join(out)


_S2_VERSION_RE = re.compile(r"(SelfState )v\d+")


def _mask_s2_version(text: str) -> str:
    """把 L4-2 S2 投影中的版本号归一化（该行属 frozen G3 链，非 G4 接线）。"""
    return _S2_VERSION_RE.sub(r"\1vN", text)


@pytest.fixture(autouse=True)
def _clean_s2_registry(tmp_path):
    """每个用例结束后清理进程级 accessor 注册表（防串库）。"""
    yield
    from ocos.self.self_state import _S2_ACCESSOR_REGISTRY

    for k in [k for k in _S2_ACCESSOR_REGISTRY if str(tmp_path) in str(k)]:
        _S2_ACCESSOR_REGISTRY.pop(k, None)


# ───────────────────────── P-E1 生产 Reasoning Consumer ─────────────────────


def test_p_e1_production_reasoning_consumer(tmp_path, monkeypatch):
    """fake provider 挂在真实 respond() 路径：W0/W1 生产 prompt 可区分。"""
    db = str(tmp_path / "prod-e1.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)

    fake = _hook_fake_provider(responder, monkeypatch)

    # W0：无 worldview → 生产 prompt 不含 worldview 块
    out0 = responder.respond(MSG, session_id="s")
    assert out0["provider"] == "fake", "必须走真实 respond() 的 provider 分支"
    assert len(fake.prompts) == 1
    assert WV_HEADER not in fake.prompts[0]
    assert out0["reply"].strip()

    # W1：committed W1 形成后 → 生产 prompt 含 worldview 块
    _make_w1(m)
    out1 = responder.respond(MSG, session_id="s")
    assert out1["provider"] == "fake"
    assert len(fake.prompts) == 2
    assert WV_HEADER in fake.prompts[1]
    assert out1["reply"].strip()

    # 差分：同一 respond() 路径，W1 存在与否 → 生产 prompt 不同且归因到块
    assert fake.prompts[0] != fake.prompts[1]


# ───────────────────────── P-E2 生产 Prompt 差分 ────────────────────────────


def test_p_e2_production_prompt_diff(tmp_path, monkeypatch):
    """Prompt(W0) ≠ Prompt(W1)；唯一新增变量 = committed worldview block。"""
    db = str(tmp_path / "prod-e2.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)

    # W0 基线（同一内存态，无写操作夹在中间）
    ctx_w0 = responder.build_context(MSG)
    assert WV_HEADER not in ctx_w0

    # W1 形成 → 生产 context 出现 worldview 块
    _make_w1(m)
    ctx_w1 = responder.build_context(MSG)
    assert WV_HEADER in ctx_w1
    assert ctx_w1 != ctx_w0

    # 唯一新增变量定位：G4 接线只新增 worldview 块；剥离块后与 W0 仅剩
    # L4-2 S2 投影的版本号差异（v1→v2 是 W1 commit 后 frozen G3 链对
    # committed 状态的既有反映，非 G4 接线引入的变量）→ 归一化后逐字节相等。
    assert _mask_s2_version(_strip_wv_block(ctx_w1)) == _mask_s2_version(ctx_w0)

    # 生产 prompt 层（respond 组装产物）：W1 prompt 携带块 + I2 溯源
    fake = _hook_fake_provider(responder, monkeypatch)
    responder.respond(MSG, session_id="s")
    prompt_w1 = fake.prompts[0]
    assert WV_HEADER in prompt_w1
    block = m.accessor.get_committed_worldview()[0]
    assert f"claim={block['claim_id']}" in prompt_w1
    assert f"evidence={len(block['evidence_ids'])}" in prompt_w1


# ───────────────────────── P-E3 零影响基线 ──────────────────────────────────


def test_p_e3_zero_impact_baseline(tmp_path, monkeypatch):
    """无 W1 → G4 注入完全惰性：生产 context 逐字节不变。"""
    from ocos.self.worldview_read_adapter import ThinkingContextProvider

    db = str(tmp_path / "prod-e3.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)

    # 真实链：无 W1 → committed 无 worldview → provider 产出空块（G4-B 生产级）
    assert m.accessor.get_committed_worldview() == []
    provider = ThinkingContextProvider(m.accessor)
    assert provider.build(base_self_context="")["worldview"] == []

    ctx_normal = responder.build_context(MSG)
    assert WV_HEADER not in ctx_normal

    # 惰性化：把 provider 替换为恒空块（与真实"无 W1"输出等价）→ G4 接线
    # 对生产上下文贡献 0 字节 → 与真实运行逐字节一致（零影响基线成立）。
    def _empty_build(self, base_self_context=""):
        return {"self": base_self_context, "worldview": []}

    monkeypatch.setattr(ThinkingContextProvider, "build", _empty_build)
    ctx_inert = responder.build_context(MSG)
    assert ctx_inert == ctx_normal


# ───────────────────────── P-E4 Authority Boundary ──────────────────────────


def test_p_e4_authority_boundary(tmp_path, monkeypatch):
    """生产 Thinking 消费 ≠ Self Mutation Authority：S2 全等。"""
    from ocos.self.self_state import serialize_state

    db = str(tmp_path / "prod-e4.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)
    _make_w1(m)

    def _snapshot():
        s = m.current
        _, h = serialize_state(s)
        return (m.version, h, list(s.update_history or ()),
                dict(s.worldview.judgments))

    before = _snapshot()
    fake = _hook_fake_provider(responder, monkeypatch)
    out = responder.respond(MSG, session_id="s")
    assert WV_HEADER in fake.prompts[0], "Thinking 必须真实消费 W1（先证明消费）"
    assert out["reply"].strip()

    after = _snapshot()
    assert after == before, (
        "生产消费后 committed S2（version/hash/update_history/worldview）必须全等")
    assert set(m.current.worldview.judgments) == {"tool"}
    assert m.current.worldview.judgments["tool"].claim_id == before[3]["tool"].claim_id
    assert m.version == before[0]


# ───────────────────────── P-E5 I2 溯源 ─────────────────────────────────────


def test_p_e5_i2_trace_in_production(tmp_path, monkeypatch):
    """生产 context / prompt 中的 worldview 行携带 committed 块同源 claim/evidence。"""
    db = str(tmp_path / "prod-e5.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)
    _make_w1(m)

    block = m.accessor.get_committed_worldview()[0]
    assert block["claim_id"] and block["evidence_ids"]

    ctx = responder.build_context(MSG)
    assert f"claim={block['claim_id']}" in ctx
    assert f"evidence={len(block['evidence_ids'])}" in ctx
    assert f"[{block['domain']}]" in ctx
    assert block["judgment"] in ctx  # 块内容 = committed 判断原样投影

    fake = _hook_fake_provider(responder, monkeypatch)
    responder.respond(MSG, session_id="s")
    assert f"claim={block['claim_id']}" in fake.prompts[0]


# ───────────────────────── P-E6 回归 ────────────────────────────────────────


def test_p_e6_regression(tmp_path):
    """既有 context 块与回复结构不受 G4 接线影响。"""
    db = str(tmp_path / "prod-e6.db")
    m = _boot(db)
    responder = ChatResponder(db_path=db)

    # 无 W1：既有块完整
    ctx = responder.build_context(MSG)
    for marker in ("身份:", "认知引擎:", "真实能力:"):
        assert marker in ctx

    # 回复结构不变（无 LLM → 诚实 mock 路径）
    out = responder.respond(MSG)
    assert "reply" in out and "provider" in out

    # 有 W1：S2 投影仍在 + worldview 块追加（互不干扰）
    _make_w1(m)
    ctx2 = responder.build_context(MSG)
    assert "SelfState v" in ctx2
    assert WV_HEADER in ctx2
    assert "身份:" in ctx2

    # accessor 既有方法正常
    assert "SelfState v" in m.accessor.render()
    assert isinstance(m.accessor.brief(), str)
    assert isinstance(m.accessor.project(), dict)
