"""Tests for ocos.knowledge.store.registry."""

import pytest


class TestAccessMatrix:

    def test_import_accessmatrix(self):
        from ocos.knowledge.store.registry import AccessMatrix
        assert AccessMatrix is not None

