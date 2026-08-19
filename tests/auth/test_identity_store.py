"""IdentityStore 测试。"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from ocos.auth.identity_store import AgentIdentityRecord, IdentityStore


@pytest.fixture
def id_store():
    db_path = os.path.join(tempfile.gettempdir(), f"test_identity_{datetime.now().timestamp()}.db")
    store = IdentityStore(db_path)
    yield store
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_save_and_load(id_store):
    record = AgentIdentityRecord(agent_id="agent-001", name="OCOS")
    saved_id = id_store.save(record)
    assert saved_id == "agent-001"

    loaded = id_store.load("agent-001")
    assert loaded is not None
    assert loaded.agent_id == "agent-001"
    assert loaded.name == "OCOS"


def test_load_nonexistent(id_store):
    loaded = id_store.load("agent-nonexistent")
    assert loaded is None


def test_update_last_boot(id_store):
    record = AgentIdentityRecord(agent_id="agent-002")
    id_store.save(record)
    assert id_store.load("agent-002").last_boot is None

    id_store.update_last_boot("agent-002")
    loaded = id_store.load("agent-002")
    assert loaded.last_boot is not None


def test_verify_identity(id_store):
    assert id_store.verify_identity("agent-003") is False
    id_store.save(AgentIdentityRecord(agent_id="agent-003"))
    assert id_store.verify_identity("agent-003") is True


def test_list(id_store):
    id_store.save(AgentIdentityRecord(agent_id="a1"))
    id_store.save(AgentIdentityRecord(agent_id="a2"))
    records = id_store.list()
    assert len(records) == 2
    assert {r.agent_id for r in records} == {"a1", "a2"}


def test_delete(id_store):
    id_store.save(AgentIdentityRecord(agent_id="to-delete"))
    assert id_store.delete("to-delete") is True
    assert id_store.load("to-delete") is None
    assert id_store.delete("to-delete") is False


def test_persistence_across_instances(id_store):
    id_store.save(AgentIdentityRecord(agent_id="persist-test"))
    db_path = id_store._db_path
    id_store.close()

    store2 = IdentityStore(db_path)
    loaded = store2.load("persist-test")
    assert loaded is not None
    assert loaded.agent_id == "persist-test"
    store2.close()
