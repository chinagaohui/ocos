"""Tests for ocos.opentale_bridge.organ_client."""

import pytest


class TestOrganClient:

    def test_import_organclient(self):
        from ocos.opentale_bridge.organ_client import OrganClient
        assert OrganClient is not None

