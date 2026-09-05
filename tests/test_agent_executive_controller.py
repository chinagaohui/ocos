"""Tests for ocos.agent.executive_controller."""

import pytest


class TestExecutiveController:

    def test_import_executivecontroller(self):
        from ocos.agent.executive_controller import ExecutiveController
        assert ExecutiveController is not None

