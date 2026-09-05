"""Tests for ocos.interaction.cli.commands.self - 自我命令。"""
import pytest


class TestSelfCommands:
    def test_import_self_modification_agent(self):
        from ocos.interaction.cli.commands.self import SelfModificationAgent
        assert SelfModificationAgent is not None

    def test_import_cmd_self(self):
        from ocos.interaction.cli.commands.self import cmd_self
        assert callable(cmd_self)

    def test_import_cmd_self_review(self):
        from ocos.interaction.cli.commands.self import cmd_self_review
        assert callable(cmd_self_review)
