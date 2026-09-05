"""Tests for ocos.interaction.cli.commands.growth - 成长命令。"""
import pytest


class TestGrowthCommands:
    def test_import_growth_engine(self):
        from ocos.interaction.cli.commands.growth import GrowthEngine
        assert GrowthEngine is not None

    def test_import_growth_analyzer(self):
        from ocos.interaction.cli.commands.growth import GrowthAnalyzer
        assert GrowthAnalyzer is not None

    def test_import_cmd_growth(self):
        from ocos.interaction.cli.commands.growth import cmd_growth
        assert callable(cmd_growth)

    def test_import_cmd_growth_analyze(self):
        from ocos.interaction.cli.commands.growth import cmd_growth_analyze
        assert callable(cmd_growth_analyze)
