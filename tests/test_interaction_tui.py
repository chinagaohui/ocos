"""Tests for ocos.interaction.tui - 终端交互界面（重点覆盖主要类）。"""
import pytest


class TestTUIComponents:
    def test_import_app(self):
        from ocos.interaction.tui import App
        assert App is not None

    def test_import_chat_screen(self):
        from ocos.interaction.tui import ChatScreen
        assert ChatScreen is not None

    def test_import_session_store(self):
        from ocos.interaction.tui import SessionStore
        assert SessionStore is not None

    def test_import_text_area(self):
        from ocos.interaction.tui import TextArea
        assert TextArea is not None

    def test_app_has_bindings(self):
        from ocos.interaction.tui import App
        assert hasattr(App, 'BINDINGS')
        assert len(App.BINDINGS) > 0

    def test_chat_screen_exists(self):
        from ocos.interaction.tui import ChatScreen
        # ChatScreen should be a class with compose method
        assert hasattr(ChatScreen, 'compose')
