"""Tests for ocos.interaction.cli.commands.status - CLI status命令。"""
import pytest


class TestStatusCommands:
    def test_import_cmd_status(self):
        from ocos.interaction.cli.commands.status import cmd_status
        assert callable(cmd_status)

    def test_import_interaction_session(self):
        from ocos.interaction.cli.commands.status import InteractionSession
        assert InteractionSession is not None
