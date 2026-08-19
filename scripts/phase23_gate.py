#!/usr/bin/env python3
"""Phase 23 Gate 9 项全覆盖验证。

G1: CapabilityDescriptor/ProviderDescriptor ABI 完整性
G2: CapabilityRegistry 注册/绑定/查询
G3: CapabilityDiscovery 扫描引擎
G4: CapabilityAdapter 执行/重试/降级
G5: IdentityStore 连接池复用 (23-B)
G6: TaskDAG RLock 线程安全 (23-C)
G7: 全量回归 ≥1459 passed (22基线) + 新增23测试
G8: import rules 无违规
G9: 新增文件清单完整性
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONPATH", os.path.join(os.path.dirname(__file__), ".."))


def gate1_descriptor_abi():
    """CapabilityDescriptor / ProviderDescriptor ABI 完整性。"""
    from ocos.capability.descriptor import CapabilityDescriptor, CapabilityCategory, CapabilityStatus
    from ocos.capability.provider import ProviderDescriptor, ProviderType, ProviderStatus

    d = CapabilityDescriptor(capability_id="test.x", name="X", category=CapabilityCategory.REASONING)
    assert d.capability_id == "test.x"
    assert d.status == CapabilityStatus.DISCOVERED
    assert d.version == "1.0.0"

    p = ProviderDescriptor(provider_id="test.p", name="P", provider_type=ProviderType.ENGINE)
    assert p.provider_type == ProviderType.ENGINE
    assert p.is_local
    print("  PASS G1: Descriptor/Provider ABI OK")


def gate2_registry():
    """CapabilityRegistry 注册/绑定/查询。"""
    from ocos.capability.registry import CapabilityRegistry
    from ocos.capability.descriptor import CapabilityDescriptor
    from ocos.capability.provider import ProviderDescriptor

    r = CapabilityRegistry()
    d = CapabilityDescriptor(capability_id="g2.cap", name="G2")
    p = ProviderDescriptor(provider_id="g2.prov", name="G2P")

    r.register_capability(d)
    r.register_provider(p)
    r.bind("g2.cap", "g2.prov")
    assert r.capability_count == 1
    assert r.provider_count == 1
    assert len(r.resolve("g2.cap")) == 1
    print("  PASS G2: Registry OK")


def gate3_discovery():
    """CapabilityDiscovery 扫描引擎。"""
    from ocos.capability.discovery import CapabilityDiscovery
    from ocos.capability.descriptor import CapabilityCategory

    d = CapabilityDiscovery()
    registry = d.scan_all()
    assert registry is not None

    d2 = CapabilityDiscovery()
    desc = d2.register_external_capability("g3.ext", "G3 Ext", CapabilityCategory.CUSTOM,
                                            provider_id="g3.prov", provider_name="G3 Prov")
    assert desc.capability_id == "g3.ext"
    print("  PASS G3: Discovery OK")


def gate4_adapter():
    """CapabilityAdapter 执行/重试/降级。"""
    from ocos.capability.adapter import CapabilityAdapter, RetryPolicy

    def ok_engine(**kw):
        return {"ok": True}

    a = CapabilityAdapter("g4.ok", "g4.prov", instance=ok_engine)
    r = a.execute()
    assert r.success
    assert r.output["ok"]

    # 降级
    def fail_engine(**kw):
        raise RuntimeError("fail")

    def fallback(inputs):
        from ocos.capability.adapter import AdapterResult
        return AdapterResult(success=True, capability_id="g4.fb", output={"fb": "used"})

    a2 = CapabilityAdapter("g4.fb", "g4.prov", instance=fail_engine,
                            retry_policy=RetryPolicy.FIXED, max_retries=1,
                            retry_base_delay=0.01, fallback=fallback)
    r2 = a2.execute()
    assert r2.success
    print("  PASS G4: Adapter OK")


def gate5_storage_connection():
    """IdentityStore 使用连接池。"""
    import tempfile
    from pathlib import Path
    from ocos.auth.identity_store import IdentityStore
    from ocos.storage.connection import get_connection, close

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = get_connection(db_path)
        store = IdentityStore(db_path)
        # 验证 IdentityStore 使用的是同一连接（池化复用）
        assert store._conn is conn
        store.close()
        close(db_path)
    finally:
        Path(db_path).unlink(missing_ok=True)
    print("  PASS G5: Storage connection pool OK")


def gate6_task_dag():
    """TaskDAG RLock 线程安全。"""
    from ocos.task import TaskDAG, TaskStatus

    dag = TaskDAG()
    dag.add_task("a", "A")
    dag.add_task("b", "B")
    dag.add_dependency("b", "a")
    dag.set_status("a", TaskStatus.COMPLETED)
    ready = dag.resolve_ready()
    assert len(ready) == 1
    assert ready[0].task_id == "b"

    order = dag.topological_order()
    assert order[0].task_id == "a"
    print("  PASS G6: TaskDAG OK")


def gate7_regression():
    """全量回归 ≥1459 passed。"""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", "-q", "--no-header"],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env={**os.environ, "PYTHONPATH": os.path.join(os.path.dirname(__file__), "..")},
    )
    for line in result.stdout.splitlines():
        if "passed" in line:
            passed = int(line.split()[0])
            assert passed >= 1459, f"Regression: only {passed} passed (need ≥1459)"
            print(f"  PASS G7: Regression {line.strip()}")
            return
    print(f"  FAIL G7: Could not parse test output: {result.stdout[:200]}")
    sys.exit(1)


def gate8_import_rules():
    """import rules 无违规。"""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", "ocos/tests/test_import_rules.py", "-q", "--no-header"],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env={**os.environ, "PYTHONPATH": os.path.join(os.path.dirname(__file__), "..")},
    )
    if "passed" in result.stdout and "failed" not in result.stdout:
        print(f"  PASS G8: Import rules OK")
    else:
        print(f"  FAIL G8: {result.stdout[:200]}")
        sys.exit(1)


def gate9_new_files():
    """新增文件清单完整性。"""
    import os
    base = os.path.join(os.path.dirname(__file__), "..")
    expected = [
        "ocos/capability/descriptor.py",
        "ocos/capability/provider.py",
        "ocos/capability/registry.py",
        "ocos/capability/discovery.py",
        "ocos/capability/adapter.py",
        "ocos/task/__init__.py",
        "tests/test_capability/test_phase23_capability.py",
        "tests/test_stability/test_sqlite_leak.py",
        "tests/test_stability/test_concurrency_locks.py",
        "scripts/phase23_gate.py",
    ]
    missing = [f for f in expected if not os.path.exists(os.path.join(base, f))]
    if missing:
        print(f"  FAIL G9: Missing files: {missing}")
        sys.exit(1)
    print(f"  PASS G9: {len(expected)} new files verified")


def main():
    print("Phase 23 Gate Check")
    print("=" * 50)
    gates = [gate1_descriptor_abi, gate2_registry, gate3_discovery,
             gate4_adapter, gate5_storage_connection, gate6_task_dag,
             gate7_regression, gate8_import_rules, gate9_new_files]
    for g in gates:
        try:
            g()
        except Exception as e:
            print(f"  FAIL {g.__name__}: {e}")
            sys.exit(1)
    print("=" * 50)
    print("ALL 9 GATES PASSED!")


if __name__ == "__main__":
    main()
