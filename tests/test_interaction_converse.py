"""Tests for ocos.interaction.converse - 对话响应器。"""
import pytest
import asyncio


class TestChatResponder:
    def test_import(self):
        from ocos.interaction.converse import ChatResponder
        assert ChatResponder is not None

    def test_create(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        assert responder is not None

    def test_build_context(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.build_context(message="hello")
        assert isinstance(result, str)

    def test_compile_goal(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.compile_goal("帮我查询数据")
        assert isinstance(result, dict)

    def test_respond(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.respond("你好")
        assert isinstance(result, dict)

    def test_respond_async(self):
        """respond_async返回协程，需await。"""
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        coro = responder.respond_async("你好")
        # 协程对象本身是有效的
        assert coro is not None

    def test_generate_stream_emits_non_protocol(self):
        """流式单轮：非协议行实时 emit，协议行(USE|)被过滤。"""
        from types import SimpleNamespace
        from ocos.interaction.converse import ChatResponder

        class FakeProvider:
            async def generate_stream(self, prompt, system_prompt=None,
                                      temperature=0.8, max_tokens=2000,
                                      on_chunk=None):
                # 首块是协议行，其余是正文（模拟工具轮+最终回答）
                on_chunk("USE|shell|{\"command\":\"echo hi\"}\n")
                on_chunk("你好，我已")
                on_chunk("完成。\n")

        responder = ChatResponder(db_path=":memory:")
        tg = SimpleNamespace(_provider=FakeProvider())
        emitted: list[str] = []
        result = responder._generate_stream(tg, "prompt", emitted.append)
        assert "USE|shell" in result  # 完整轮文本保留协议行（供工具检测）
        assert "你好" in result
        joined = "".join(emitted)
        assert "USE|" not in joined  # emit 不带协议行
        assert "你好" in joined

    def test_llm_failure_no_raw_exception_leak(self, monkeypatch):
        """P1 修复（2026-09-07）: LLM 调用失败时异常细节不直泄对话流。

        缺陷史: Invalid http_client 原文曾以（LLM 调用失败: ...）前缀
        直泄用户；且降级头部误称"未配置 LLM key"（实为已配置但调用失败）。
        """
        import asyncio
        from types import SimpleNamespace
        from ocos.interaction.converse import ChatResponder

        class BrokenProvider:
            name = "broken"

            async def generate(self, prompt, system_prompt=None,
                               temperature=0.6, max_tokens=2000):
                raise RuntimeError(
                    "Invalid `http_client` argument; Expected an instance "
                    "of `httpx.AsyncClient` but got <class 'x'>")

        # asyncio.run 在 pytest 线程内需可用 — 直接驱动协程亦可，此处
        # respond 内部 asyncio.run；monkeypatch TextGenerator 注入坏 provider
        import ocos.engines.text_generator as tgmod
        monkeypatch.setattr(
            tgmod, "TextGenerator",
            lambda: SimpleNamespace(_provider=BrokenProvider()),
            raising=False)

        responder = ChatResponder(db_path=":memory:")
        responder._has_real_llm = lambda: True   # 已配置 key 的机器路径
        responder._remember_conversation = lambda *a, **k: None
        if getattr(responder, "_session_manager", None) is not None:
            responder._session_manager = None
        try:
            result = responder.respond("查看根分区磁盘使用率")
        except RuntimeError as e:
            if "asyncio.run() cannot be called" in str(e):
                asyncio.run(responder.respond_async("查看根分区磁盘使用率"))
                return
            raise
        reply = result["reply"]
        assert "http_client" not in reply          # 原文不泄漏
        assert "Invalid" not in reply
        assert "模型暂不可用" in reply              # 干净降级文案
        assert result["mock"] is True
        assert "未配置 LLM key" not in reply        # 不再误标

    def test_state_reply_degraded_headers(self):
        """两种降级头部语义分明: 无 key vs 调用失败。"""
        from ocos.interaction.converse import ChatResponder
        r = ChatResponder(db_path=":memory:")
        mock = r._state_reply("m", "ctx")
        assert "未配置 LLM key" in mock["reply"]
        deg = r._state_reply("m", "ctx", degraded=True)
        assert "模型暂不可用" in deg["reply"]
        assert "未配置 LLM key" not in deg["reply"]

    def test_respond_auto(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.respond_auto("你好")
        assert isinstance(result, dict)

    def test_build_introspection(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.build_introspection()
        assert isinstance(result, dict)

    def test_apply_self_upgrade(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.apply_self_upgrade("测试变更")
        assert isinstance(result, str)

    def test_self_improve(self):
        from ocos.interaction.converse import ChatResponder
        responder = ChatResponder(db_path=":memory:")
        result = responder.self_improve()
        assert isinstance(result, dict)
