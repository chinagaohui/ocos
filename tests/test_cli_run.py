"""Tests for ocos.interaction.cli.commands.run - CLI run命令。"""
import pytest


class TestRunCommands:
    def test_import_cmd_run(self):
        from ocos.interaction.cli.commands.run import cmd_run
        assert callable(cmd_run)

    def test_import_resolve_db_path(self):
        from ocos.interaction.cli.commands.run import resolve_db_path
        assert callable(resolve_db_path)

    def test_default_db(self):
        from ocos.interaction.cli.commands.run import DEFAULT_DB
        assert DEFAULT_DB is not None
