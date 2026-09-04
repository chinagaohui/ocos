"""OCOS InteractionContext 不变式测试。

Interaction Layer 权限边界：只读，无 save() 方法。
"""

import pytest
import tempfile
import os

from ocos.interaction.context import (
    InteractionContext,
    create_inmemory_context,
    create_persistent_context,
)


class TestInteractionContext:
    """上下文生命周期和惰性初始化。"""

    def test_inmemory_default(self):
        ctx = InteractionContext()
        assert ctx.db_path == ":memory:"

    def test_custom_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            ctx = InteractionContext(db_path=path)
            assert ctx.db_path == path
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_env_var_db_path(self):
        os.environ["OCOS_DB_PATH"] = "/tmp/test-ocos.db"
        try:
            ctx = InteractionContext()
            assert ctx.db_path == "/tmp/test-ocos.db"
        finally:
            del os.environ["OCOS_DB_PATH"]

    def test_no_save_method(self):
        """Interaction Layer 无写入能力。"""
        ctx = InteractionContext()
        assert not hasattr(ctx, "save") or not callable(getattr(ctx, "save", None))

    def test_context_manager(self):
        ctx = InteractionContext()
        with ctx as c:
            assert c is ctx
        # close() should not raise
        ctx.close()

    def test_episode_store_lazy_init(self):
        ctx = InteractionContext()
        store = ctx.ensure_episode_store()
        assert store is not None
        # second call returns same instance
        assert ctx.ensure_episode_store() is store

    def test_belief_store_lazy_init(self):
        ctx = InteractionContext()
        store = ctx.ensure_belief_store()
        assert store is not None
        assert ctx.ensure_belief_store() is store

    def test_identity_lazy_init(self):
        ctx = InteractionContext()
        identity = ctx.ensure_identity()
        assert identity is not None
        assert ctx.ensure_identity() is identity

    def test_query_memory_returns_list(self):
        ctx = InteractionContext()
        results = ctx.query_memory(limit=10)
        assert isinstance(results, list)

    def test_query_beliefs_returns_list(self):
        ctx = InteractionContext()
        results = ctx.query_beliefs(limit=20)
        assert isinstance(results, list)

    def test_identity_summary(self):
        ctx = InteractionContext()
        summary = ctx.identity_summary()
        assert "id" in summary
        assert "principles" in summary
        assert "evolution_constraints" in summary


class TestFactoryFunctions:
    def test_create_inmemory_context(self):
        ctx = create_inmemory_context()
        assert ctx.db_path == ":memory:"

    def test_create_persistent_context(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            ctx = create_persistent_context(path)
            assert ctx.db_path == path
        finally:
            if os.path.exists(path):
                os.unlink(path)
