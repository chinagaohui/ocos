"""OCOS REPL — status/say 命令（UX-P2: 与 CLI 共用同一命令核心）。"""

from __future__ import annotations

from types import SimpleNamespace

from ocos.interaction.base import InteractionSession


class ReplStatusCommand:
    """/status — 一屏总览（复用 CLI cmd_status，消除双实现漂移）。"""

    def __init__(self, session: InteractionSession, ctx):
        self._session = session
        self._ctx = ctx

    def execute(self, arg: str):
        from ocos.interaction.cli.commands.status import cmd_status
        cmd_status(SimpleNamespace(db=self._ctx.db_path), self._session)


class ReplSayCommand:
    """/say <message> — 给运行中的认知引擎投递消息（复用 CLI cmd_say）。"""

    def __init__(self, session: InteractionSession, ctx):
        self._session = session
        self._ctx = ctx

    def execute(self, arg: str):
        from ocos.interaction.cli.commands.say import cmd_say
        cmd_say(SimpleNamespace(message=arg, db=self._ctx.db_path),
                self._session)
