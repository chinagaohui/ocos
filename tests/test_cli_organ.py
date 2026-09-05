"""Tests for ocos.interaction.cli.commands.organ - 组织命令。"""
import pytest


class TestOrganCommands:
    def test_import_organ_client(self):
        from ocos.interaction.cli.commands.organ import OrganClient
        assert OrganClient is not None

    def test_import_cmd_organ_generate(self):
        from ocos.interaction.cli.commands.organ import cmd_organ_generate
        assert callable(cmd_organ_generate)

    def test_import_cmd_organ_status(self):
        from ocos.interaction.cli.commands.organ import cmd_organ_status
        assert callable(cmd_organ_status)

    def test_import_organ_errors(self):
        from ocos.interaction.cli.commands.organ import OrganClientError
        assert OrganClientError is not None
