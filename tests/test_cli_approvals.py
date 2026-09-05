"""Tests for ocos.interaction.cli.commands.approvals - CLI approvals命令。"""
import pytest


class TestApprovalsCommands:
    def test_import_cmd_approvals_approve(self):
        from ocos.interaction.cli.commands.approvals import cmd_approvals_approve
        assert callable(cmd_approvals_approve)

    def test_import_cmd_approvals_deny(self):
        from ocos.interaction.cli.commands.approvals import cmd_approvals_deny
        assert callable(cmd_approvals_deny)

    def test_import_cmd_approvals_list(self):
        from ocos.interaction.cli.commands.approvals import cmd_approvals_list
        assert callable(cmd_approvals_list)
