"""Tests for ocos.interaction.converse."""

import pytest


class TestChatResponder:

    def test_import_chatresponder(self):
        from ocos.interaction.converse import ChatResponder
        assert ChatResponder is not None

