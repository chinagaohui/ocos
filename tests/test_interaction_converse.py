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
        assert hasattr(coro, 'cr_code') or hasattr(coro, '__await__')

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
