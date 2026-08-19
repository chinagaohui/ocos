"""Phase 55: Capability Reality Layer — Tests.

验收:
    CR55-01: Capability ≠ Execution
    CR55-02: Adapter Isolation
    CR55-03: Execution Recorded
    CR55-04: Capability Discovery
"""

import pytest
import os
import tempfile
import uuid

from ocos.capability_reality.adapter_types import (
    AdapterHealth, ExecutionStatus, CapabilityCategory,
    CapabilityDescriptor, ExecutionContext, AdapterConfig, AdapterStatus,
)
from ocos.capability_reality.capability_registry import CapabilityRegistry
from ocos.capability_reality.capability_selector import CapabilitySelector
from ocos.capability_reality.capability_adapter import CapabilityAdapter
from ocos.capability_reality.adapter_fs import FilesystemAdapter
from ocos.capability_reality.adapter_shell import ShellAdapter
from ocos.capability_reality.adapter_discovery import AdapterDiscovery
from ocos.capability_reality.capability_validator import (
    CapabilityValidator, ValidationDecision, ValidationResult,
)


def make_ctx(name="test", sandboxed=True, **params) -> ExecutionContext:
    return ExecutionContext(
        execution_id=f"ex-{uuid.uuid4().hex[:8]}",
        capability_name=name,
        params=params,
        sandboxed=sandboxed,
    )


class MinimalAdapter(CapabilityAdapter):
    """最小化适配器用于测试。"""
    def __init__(self, **kw):
        desc_kw = {k: v for k, v in kw.items()
                   if k in ("name", "category", "risk_level", "description", "permissions")}
        desc_name = desc_kw.pop("name", None) or kw.pop("name", None) or "minimal"
        desc_category = desc_kw.pop("category", None) or kw.pop("category", None) or CapabilityCategory.CUSTOM
        required_params = kw.pop("required_params", ["action"])
        risk_level = kw.pop("risk_level", 1)

        descriptor = CapabilityDescriptor(
            name=desc_name,
            category=desc_category,
            risk_level=risk_level,
            required_params=required_params,
            **desc_kw,
        )
        self._return_value = kw.pop("return_value", "ok")
        self._should_fail = kw.pop("should_fail", False)
        super().__init__(descriptor=descriptor)

    def _do_execute(self, ctx):
        if self._should_fail:
            raise RuntimeError("simulated failure")
        return self._return_value

    def _do_health_check(self):
        return AdapterHealth.HEALTHY


# ══════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════

class TestRegistry:
    def test_register_and_get(self):
        reg = CapabilityRegistry()
        desc = CapabilityDescriptor("test_cap", CapabilityCategory.CUSTOM)
        reg.register(desc, executor=lambda ctx: "result")
        assert reg.has("test_cap")
        assert reg.get("test_cap").descriptor == desc

    def test_unregister(self):
        reg = CapabilityRegistry()
        desc = CapabilityDescriptor("test_cap", CapabilityCategory.CUSTOM)
        reg.register(desc)
        assert reg.unregister("test_cap") is True
        assert not reg.has("test_cap")

    def test_list_by_category(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityDescriptor("fs1", CapabilityCategory.FILESYSTEM))
        reg.register(CapabilityDescriptor("fs2", CapabilityCategory.FILESYSTEM))
        reg.register(CapabilityDescriptor("sh1", CapabilityCategory.SHELL))

        assert len(reg.list_by_category(CapabilityCategory.FILESYSTEM)) == 2
        assert len(reg.list_by_category(CapabilityCategory.SHELL)) == 1

    def test_healthy_count(self):
        reg = CapabilityRegistry()
        d = CapabilityDescriptor("healthy", CapabilityCategory.CUSTOM)
        reg.register(d)
        reg.mark_health("healthy", AdapterStatus(adapter_id="healthy", health=AdapterHealth.HEALTHY))
        assert reg.healthy_count() == 1

    def test_count_and_clear(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityDescriptor("a", CapabilityCategory.CUSTOM))
        reg.register(CapabilityDescriptor("b", CapabilityCategory.CUSTOM))
        assert reg.count() == 2
        reg.clear()
        assert reg.count() == 0


# ══════════════════════════════════════════════════
# Selector
# ══════════════════════════════════════════════════

class TestSelector:
    def test_exact_match(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityDescriptor("fs_read", CapabilityCategory.FILESYSTEM))
        reg.register(CapabilityDescriptor("shell", CapabilityCategory.SHELL))

        sel = CapabilitySelector(reg)
        result = sel.select("fs_read")
        assert result.matched
        assert result.capability.descriptor.name == "fs_read"

    def test_category_match(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityDescriptor("fs_write", CapabilityCategory.FILESYSTEM,
                                          risk_level=3))
        reg.register(CapabilityDescriptor("fs_read", CapabilityCategory.FILESYSTEM,
                                          risk_level=1))

        sel = CapabilitySelector(reg)
        result = sel.select("file_op", CapabilityCategory.FILESYSTEM)
        assert result.matched
        # 低风险优先
        assert result.capability.descriptor.name == "fs_read"

    def test_no_match(self):
        reg = CapabilityRegistry()
        sel = CapabilitySelector(reg)
        result = sel.select("nonexistent")
        assert not result.matched

    def test_intent_read(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityDescriptor("fs_read", CapabilityCategory.FILESYSTEM,
                                          risk_level=1))
        sel = CapabilitySelector(reg)
        result = sel.select_by_intent("读取文件内容")
        assert result.matched
        assert result.capability.descriptor.name == "fs_read"


# ══════════════════════════════════════════════════
# Adapter basics
# ══════════════════════════════════════════════════

class TestAdapter:
    def test_cr55_01_capability_not_execution(self):
        """CR55-01: 注册不代表已执行。"""
        reg = CapabilityRegistry()
        desc = CapabilityDescriptor("test", CapabilityCategory.CUSTOM)
        reg.register(desc)
        # 注册了但没有 executor
        assert reg.find_executable("test") is None

    def test_adapter_execute_ok(self):
        adapter = MinimalAdapter(return_value="done")
        ctx = make_ctx(action="do")
        result = adapter.execute(ctx)
        assert result.ok
        assert result.output == "done"
        assert result.status == ExecutionStatus.SUCCESS

    def test_cr55_02_isolation(self):
        """CR55-02: 适配器失败不影响调用方。"""
        adapter = MinimalAdapter(should_fail=True)
        ctx = make_ctx(action="do")
        result = adapter.execute(ctx)
        assert not result.ok
        assert result.status == ExecutionStatus.FAILED
        assert "simulated" in result.error
        # 不抛出异常

    def test_health_check(self):
        adapter = MinimalAdapter()
        health = adapter.health_check()
        assert health == AdapterHealth.HEALTHY

    def test_validate_missing_param(self):
        adapter = MinimalAdapter(required_params=["action", "target"])
        ctx = make_ctx(action="do")  # missing 'target'
        validator = CapabilityValidator()
        result = validator.validate_pre(ctx, adapter.descriptor)
        assert result.decision == ValidationDecision.REJECT

    def test_cr55_03_event_callback(self):
        """CR55-03: 执行产生事件回调。"""
        events = []
        adapter = MinimalAdapter(return_value="ok")
        adapter.on_event = lambda r: events.append(r)
        ctx = make_ctx(action="do")
        result = adapter.execute(ctx)
        assert len(events) == 1
        assert events[0] is result

    def test_adapter_register_to_registry(self):
        reg = CapabilityRegistry()
        adapter = MinimalAdapter()
        adapter.register_to(reg)
        assert reg.has("minimal")


# ══════════════════════════════════════════════════
# Filesystem Adapter (real I/O)
# ══════════════════════════════════════════════════

class TestFilesystemAdapter:
    def test_read_file(self):
        fs = FilesystemAdapter()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\n")
            tmp = f.name

        try:
            ctx = make_ctx(operation="read", path=tmp)
            result = fs.execute(ctx)
            assert result.ok
            assert "hello world" in result.output["content"]
        finally:
            os.unlink(tmp)

    def test_write_file(self):
        fs = FilesystemAdapter()
        tmp = os.path.join(tempfile.gettempdir(), f"ocos-test-{uuid.uuid4().hex[:8]}.txt")

        try:
            ctx = make_ctx(operation="write", path=tmp, content="test content")
            result = fs.execute(ctx)
            assert result.ok
            assert os.path.exists(tmp)
            with open(tmp) as f:
                assert f.read() == "test content"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_list_dir(self):
        fs = FilesystemAdapter()
        ctx = make_ctx(operation="list", path="/tmp")
        result = fs.execute(ctx)
        assert result.ok
        assert "entries" in result.output

    def test_exists(self):
        fs = FilesystemAdapter()
        ctx = make_ctx(operation="exists", path="/tmp")
        result = fs.execute(ctx)
        assert result.ok
        assert result.output["exists"] is True

    def test_missing_file(self):
        fs = FilesystemAdapter()
        ctx = make_ctx(operation="read", path="/tmp/__nonexistent_ocos_test__")
        result = fs.execute(ctx)
        assert result.status == ExecutionStatus.FAILED

    def test_health_check(self):
        fs = FilesystemAdapter()
        health = fs.health_check()
        assert health == AdapterHealth.HEALTHY


# ══════════════════════════════════════════════════
# Shell Adapter (real execution)
# ══════════════════════════════════════════════════

class TestShellAdapter:
    def test_simple_command(self):
        sh = ShellAdapter()
        ctx = make_ctx(command="echo hello")
        result = sh.execute(ctx)
        assert result.ok
        assert "hello" in result.output["stdout"]

    def test_command_fails(self):
        sh = ShellAdapter()
        ctx = make_ctx(command="ls /__nonexistent_dir_ocos_test__", timeout=5)
        result = sh.execute(ctx)
        # 命令失败但适配器不崩溃
        assert result.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)
        if result.status == ExecutionStatus.SUCCESS:
            assert not result.output["ok"]

    def test_dangerous_command_blocked(self):
        sh = ShellAdapter()
        ctx = make_ctx(command="rm -rf /")
        result = sh.execute(ctx)
        assert result.status == ExecutionStatus.FAILED
        assert "blocked" in result.error.lower() or "dangerous" in result.error.lower()

    def test_health_check(self):
        sh = ShellAdapter()
        health = sh.health_check()
        assert health == AdapterHealth.HEALTHY


# ══════════════════════════════════════════════════
# Validator
# ══════════════════════════════════════════════════

class TestValidator:
    def test_approve_low_risk(self):
        v = CapabilityValidator()
        desc = CapabilityDescriptor("low", CapabilityCategory.CUSTOM, risk_level=1,
                                     required_params=[])
        ctx = make_ctx()
        result = v.validate_pre(ctx, desc)
        assert result.decision == ValidationDecision.APPROVE

    def test_reject_high_risk_no_sandbox(self):
        v = CapabilityValidator()
        desc = CapabilityDescriptor("high", CapabilityCategory.SHELL, risk_level=4,
                                     required_params=["command"])
        ctx = make_ctx(command="ls", sandboxed=False)
        result = v.validate_pre(ctx, desc)
        assert result.decision == ValidationDecision.REJECT

    def test_needs_review_medium_risk(self):
        v = CapabilityValidator(auto_approve_risk_below=2)
        desc = CapabilityDescriptor("med", CapabilityCategory.CUSTOM, risk_level=3,
                                     required_params=[])
        ctx = make_ctx()
        result = v.validate_pre(ctx, desc)
        assert result.decision == ValidationDecision.NEEDS_REVIEW

    def test_missing_required_param(self):
        v = CapabilityValidator()
        desc = CapabilityDescriptor("test", CapabilityCategory.CUSTOM,
                                     required_params=["path"])
        ctx = make_ctx()  # no 'path'
        result = v.validate_pre(ctx, desc)
        assert result.decision == ValidationDecision.REJECT

    def test_post_validate_failure(self):
        from ocos.capability_reality.adapter_types import ExecutionResult
        v = CapabilityValidator()
        result = ExecutionResult(
            context=make_ctx(),
            status=ExecutionStatus.FAILED,
            error="boom",
        )
        post = v.validate_post(result)
        assert post.decision == ValidationDecision.REJECT


# ══════════════════════════════════════════════════
# Discovery
# ══════════════════════════════════════════════════

class TestDiscovery:
    def test_cr55_04_discover(self):
        """CR55-04: 发现真实可用的工具。"""
        discovery = AdapterDiscovery()
        registry, report = discovery.run()

        # 应该发现 filesystem 和 shell
        assert "filesystem" in report.available_tools
        assert "shell" in report.available_tools
        assert registry.has("filesystem")
        assert registry.has("shell")
        assert registry.count() >= 2

    def test_discovery_report(self):
        discovery = AdapterDiscovery()
        registry, report = discovery.run()

        assert report.filesystem  # 文件系统信息
        assert report.shell        # shell 信息
        assert report.python_modules  # Python 模块
        assert "python3" in report.available_tools

    def test_registered_adapters_executable(self):
        discovery = AdapterDiscovery()
        registry, report = discovery.run()

        # 已注册的适配器应该可执行
        fs = registry.find_executable("filesystem")
        assert fs is not None
        sh = registry.find_executable("shell")
        assert sh is not None


# ══════════════════════════════════════════════════
# Integration: full pipeline
# ══════════════════════════════════════════════════

class TestIntegration:
    def test_full_pipeline(self):
        """完整管线: Discover → Select → Validate → Execute → Record。"""
        discovery = AdapterDiscovery()
        registry, report = discovery.run()

        selector = CapabilitySelector(registry)
        validator = CapabilityValidator()

        # Select
        sel = selector.select_by_intent("列出 /tmp 目录")
        assert sel.matched

        # Validate
        ctx = make_ctx(operation="list", path="/tmp")
        pre_result = validator.validate_pre(ctx, sel.capability.descriptor)
        assert pre_result.decision in (ValidationDecision.APPROVE, ValidationDecision.NEEDS_REVIEW)

        # Execute
        result = sel.capability.executor(ctx)
        assert result.ok
        assert "entries" in result.output

    def test_selection_then_execute(self):
        """Select → Execute 端到端。"""
        reg = CapabilityRegistry()
        adapter = MinimalAdapter(return_value="pipeline-ok")
        adapter.register_to(reg)

        sel = CapabilitySelector(reg)
        result = sel.select("minimal")
        assert result.matched

        ctx = make_ctx(action="test")
        exec_result = result.capability.executor(ctx)
        assert exec_result.output == "pipeline-ok"
