"""Tests for ocos.interaction.tui - 终端交互界面。"""
import pytest


class TestTUI:
    def test_import_app(self):
        from ocos.interaction.tui import App
        assert App is not None

    def test_import_chat_screen(self):
        from ocos.interaction.tui import ChatScreen
        assert ChatScreen is not None

    def test_import_run_tui(self):
        from ocos.interaction.tui import run_tui
        assert run_tui is not None

    def test_create_chat_screen(self):
        from ocos.interaction.tui import ChatScreen
        screen = ChatScreen()
        assert screen is not None
