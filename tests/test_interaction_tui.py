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

    def test_session_picker_import(self):
        from ocos.interaction.tui import SessionPicker
        assert SessionPicker is not None

    def test_new_bindings_present(self):
        from ocos.interaction.tui import ChatScreen
        actions = {b.action for b in ChatScreen.BINDINGS}
        assert {'abort', 'session_picker'} <= actions

    def test_new_commands_registered(self):
        from ocos.interaction.tui import COMMANDS, ALIASES
        for name in ("new", "reset", "abort"):
            assert name in COMMANDS
        assert ALIASES.get("stop") == "abort"


class TestSessionPickerBehavior:
    def test_picker_lists_and_filters(self, tmp_path):
        from pathlib import Path
        from ocos.interaction.tui import SessionStore, SessionPicker
        store = SessionStore(db_path=Path(tmp_path) / "s.db")
        a = store.create_session()
        store.rename(a, "网络调研")
        store.add_message(a, "user", "你好")
        b = store.create_session()
        picker = SessionPicker(store, current=a)
        # 未过滤：列出全部
        assert [r["id"] for r in picker._session_rows("")] == [b, a]
        # 过滤：按标题关键字
        assert [r["id"] for r in picker._session_rows("网络")] == [a]
        # 过滤：按 id 前缀（短尾唯一）
        assert [r["id"] for r in picker._session_rows(b[-6:])] == [b]

    def test_store_clear_session(self, tmp_path):
        from pathlib import Path
        from ocos.interaction.tui import SessionStore
        store = SessionStore(db_path=Path(tmp_path) / "s.db")
        sid = store.create_session()
        store.add_message(sid, "user", "hi")
        assert store.count_messages(sid).get("user", 0) == 1
        store.clear_session(sid)
        assert store.count_messages(sid) == {}
