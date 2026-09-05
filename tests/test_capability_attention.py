"""Tests for ocos.capability.attention - 注意力管理。"""
import pytest


class TestAttention:
    def test_import_attention_manager(self):
        from ocos.capability.attention import AttentionManager
        assert AttentionManager is not None

    def test_import_cognitive_controller(self):
        from ocos.capability.attention import CognitiveAttentionController
        assert CognitiveAttentionController is not None

    def test_import_attention_mode(self):
        from ocos.capability.attention import AttentionMode
        assert AttentionMode is not None

    def test_create_attention_manager(self):
        from ocos.capability.attention import AttentionManager
        mgr = AttentionManager()
        assert mgr is not None

    def test_create_cognitive_controller(self):
        from ocos.capability.attention import CognitiveAttentionController
        ctrl = CognitiveAttentionController()
        assert ctrl is not None
