"""FIX-22: 多步主循环 — act→observe→reason 受预算约束的多轮循环测试。

场景:
  直接回答       → 零额外 LLM 调用（零回归）
  多轮取数       → 观察累积回注，直到 LLM 终答
  预算耗尽       → 强制收尾（总 LLM 调用 ≤ max_rounds+1）
  动作被拒       → 拒绝块如实回注，循环不空转
  无执行器       → 单次调用（与从前一致）
"""
import pytest

from ocos.interaction.converse import ChatResponder


class _ScriptedProvider:
    name = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[str] = []

    async def generate(self, prompt, system_prompt=None,
                       temperature=0.6, max_tokens=2000):
        self.calls.append(prompt)
        if self.script:
            return self.script.pop(0)
        return "（脚本耗尽）"


def _responder(tmp_path, monkeypatch, script, executor=None):
    r = ChatResponder(db_path=str(tmp_path / "ocos.db"))
    monkeypatch.setattr(r, "_has_real_llm", lambda: True)
    monkeypatch.setattr(r, "_style_profile", lambda: "默认")
    monkeypatch.setattr(r, "_remember_conversation", lambda *a, **k: None)
    prov = _ScriptedProvider(script)
    fake_tg = type("FakeTG", (), {"_provider": prov})()
    import ocos.engines.text_generator as tgmod
    monkeypatch.setattr(tgmod, "TextGenerator", lambda: fake_tg)
    if executor is not None:
        r._tool_executor = executor
    return r, prov


def test_direct_answer_no_extra_calls(tmp_path, monkeypatch):
    r, prov = _responder(tmp_path, monkeypatch, ["你好呀"],
                         executor=lambda n, p: "OBS")
    out = r.respond("你好", session_id="s")
    assert out["reply"] == "你好呀"
    assert len(prov.calls) == 1  # 无动作行 → 不多花一次调用


def test_two_tool_rounds_then_answer(tmp_path, monkeypatch):
    script = [
        'USE|shell|{"command": "df -h"}',
        'USE|fs_read|{"path": "/etc/os-release"}',
        "最终回答：系统一切正常",
    ]
    r, prov = _responder(
        tmp_path, monkeypatch, script,
        # 与真实 make_default_tool_executor 契约一致: 返回 dict
        executor=lambda n, p: {"ok": True, "stdout": f"OBS({n})"})
    obs_flags: list[bool] = []
    orig = prov.generate

    async def gen(prompt, **kw):
        obs_flags.append("【工具观察】" in prompt)
        return await orig(prompt, **kw)

    prov.generate = gen
    out = r.respond("看看系统状态", session_id="s")
    assert out["reply"] == "最终回答：系统一切正常"
    assert len(prov.calls) == 3
    # 第1轮无观察，第2/3轮观察已回注
    assert obs_flags == [False, True, True]
    assert "OBS(shell)" in prov.calls[1]
    assert "OBS(fs_read)" in prov.calls[2]  # 观察累积而非覆盖


def test_budget_cap_forces_final_answer(tmp_path, monkeypatch):
    script = ['USE|shell|{"command": "df"}', 'USE|shell|{"command": "free"}',
              "被强制收尾的回答"]
    r, prov = _responder(
        tmp_path, monkeypatch, script,
        executor=lambda n, p: {"ok": True, "stdout": "OBS"})
    out = r.respond("狂取数据", session_id="s")
    assert out["reply"] == "被强制收尾的回答"
    assert len(prov.calls) == 3  # max_rounds=2 → 总调用 ≤3（防失控）
    assert "预算已用尽" in prov.calls[2]


def test_rejected_action_feeds_back_and_stops(tmp_path, monkeypatch):
    script = ['USE|fs_write|{"path": "/tmp/x"}', "写操作需转目标管线执行"]
    r, prov = _responder(tmp_path, monkeypatch, script,
                         executor=lambda n, p: "OBS")
    out = r.respond("帮我写个文件", session_id="s")
    assert out["reply"] == "写操作需转目标管线执行"
    assert len(prov.calls) == 2
    assert "拒绝" in prov.calls[1]  # 拒绝块如实回注


def test_no_executor_single_call(tmp_path, monkeypatch):
    script = ['USE|shell|{"command": "df -h"}']
    r, prov = _responder(tmp_path, monkeypatch, script, executor=None)
    r._tool_executor = None
    out = r.respond("磁盘还剩多少", session_id="s")
    assert len(prov.calls) == 1  # 无执行器 → 单次调用，不进循环
    assert "USE|" not in out["reply"]  # 协议行不进对话流
