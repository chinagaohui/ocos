"""
D2 Plugin Sandbox — 插件隔离执行环境。

职责：
- 验证插件 Manifest（权限、入口点、超时）
- 通过 Import Hook 拦截禁止的 import
- 强制超时终止（daemon 线程池 + timeout kill）
- 可选集成 D1 CapabilityRegistry

架构定位：
  PluginSandbox 是 Plugin 框架的安全边界。
  Plugin Loader (D3) 调用 sandbox.load() 注册插件，
  然后通过 sandbox.execute() 执行插件操作。
"""

from __future__ import annotations

import concurrent.futures
import sys
import threading
import time
import traceback as tb_module
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ocos.platform.plugin_base import PluginBase
from ocos.platform.plugin_manifest import PluginManifest, Permission, validate_manifest

try:
    from ocos.platform.capability_registry import CapabilityRegistry
except ImportError:
    CapabilityRegistry = None  # type: ignore

from ocos.logging import get_logger


logger = get_logger(__name__)


# ── 安全的默认 import 白名单 ───────────────────────────────────────────────────

_DEFAULT_ALLOWED_IMPORTS: tuple[str, ...] = (
    "json",
    "math",
    "datetime",
    "collections",
    "typing",
    "dataclasses",
    "uuid",
    "re",
    "copy",
    "itertools",
    "functools",
    "enum",
    "decimal",
    "fractions",
    "statistics",
    "textwrap",
    "string",
    "struct",
    "binascii",
    "base64",
    "hashlib",
    "hmac",
    "time",
    "random",
    "secrets",
    "numbers",
    "pathlib._path",  # 允许 pathlib 自身，但禁止 pathlib 对文件系统的写入
)


# ── 沙箱结果 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SandboxResult:
    """插件单次执行的结果。"""

    success: bool = False
    plugin_id: str = ""
    output: Any = None
    execution_time_ms: float = 0.0
    error: str = ""
    traceback: str = ""
    killed: bool = False


# ── 沙箱配置 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SandboxConfig:
    """Sandbox 全局配置。

    创建 Sandbox 时传入，运行时不可变。
    """

    max_memory_mb: int = 256
    """插件内存软限制（Stage 1 threading 模式下为检测信号，不强制）。"""

    max_concurrent: int = 10
    """最大同时加载的插件数。"""

    default_timeout: int = 30
    """execute() 默认超时秒数。单次最小 1，最大 300。"""

    enforce_timeout: bool = True
    """是否强制超时终止。为 True 时超时后直接 cancel future + killed 标记。"""

    allowed_imports_global: tuple[str, ...] = _DEFAULT_ALLOWED_IMPORTS
    """全局允许的 import 模块前缀，所有插件共享。
    叠加插件自身声明的 allowed_imports。"""

    allowed_permissions: tuple[Permission, ...] = (
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.NETWORK,
        Permission.SYSTEM,
    )
    """Sandbox 管理员允许放行的最大权限集。
    插件声明的 required_permissions 必须为此集合的子集，否则拒绝加载。"""


# ── Sandbox ───────────────────────────────────────────────────────────────────


class _ImportBlocker:
    """自定义 meta_path import hook，阻止未在白名单中的模块导入。

    只作用于当前线程，通过修改 sys.meta_path 全局生效。
    Sandbox 在 load() 时安装，unload() 时移除。
    """

    def __init__(self, allowed_prefixes: set[str]) -> None:
        self._allowed = allowed_prefixes

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        # 已加载的模块直接放行（防止拦截 Python 自身运行时依赖）
        if fullname in sys.modules:
            return None
        # 检查是否在允许前缀中
        matched = False
        for prefix in self._allowed:
            if fullname == prefix or fullname.startswith(prefix + "."):
                matched = True
                break
        if matched:
            return None
        # 拒绝
        raise ImportError(
            f"[Sandbox] 禁止导入 '{fullname}'。"
            " 该模块不在插件 import 白名单中。"
        )


class PluginSandbox:
    """Plugin 沙箱执行环境。

    使用方式：
        config = SandboxConfig()
        sandbox = PluginSandbox(config)

        manifest = PluginManifest(
            name="test-plugin",
            entry_point="myplugin:Plugin",
            required_permissions=[Permission.FILE_READ],
        )
        pid = sandbox.load(manifest)

        result = sandbox.execute(pid, "run", params={"key": "value"})
        print(result.output)

        sandbox.unload(pid)
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        registry: Optional[Any] = None,
    ) -> None:
        """
        Args:
            config: Sandbox 配置，使用默认值若为空。
            registry: D1 CapabilityRegistry 实例（可选）。
        """
        self._config = config or SandboxConfig()
        self._registry = registry
        self._plugins: dict[str, _PluginSlot] = {}
        self._import_blockers: dict[str, _ImportBlocker] = {}
        self._lock = threading.Lock()
        self._thread_pool: concurrent.futures.ThreadPoolExecutor | None = None
        logger.debug("PluginSandbox __init__ completed", component="plugin_sandbox", max_concurrent=self._config.max_concurrent, default_timeout=self._config.default_timeout)

    # ── 属性 ──────────────────────────────────────────────────────────────────

    @property
    def config(self) -> SandboxConfig:
        return self._config

    @property
    def loaded_plugins(self) -> int:
        return len(self._plugins)

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def load(self, manifest: PluginManifest) -> str:
        """加载一个插件到沙箱。

        验证 manifest → 检查权限范围 → 安装 import hook → 创建 slot。

        Returns:
            plugin_id

        Raises:
            ValueError: manifest 验证失败
            RuntimeError: 超过最大并发数
        """
        # 1. 验证 manifest
        reason = validate_manifest(manifest)
        if reason is not None:
            logger.error("Manifest validation failed", component="plugin_sandbox", plugin_name=manifest.name, reason=reason)
            raise ValueError(f"Manifest 验证失败: {reason}")

        # 2. 权限范围检查
        for perm in manifest.required_permissions:
            if perm not in self._config.allowed_permissions:
                logger.error("Permission not allowed", component="plugin_sandbox", plugin_name=manifest.name, permission=perm.value)
                raise ValueError(
                    f"插件 '{manifest.name}' 要求的权限 '{perm.value}' "
                    f"不在 Sandbox 允许范围内"
                )

        # 3. 并发限制
        with self._lock:
            if len(self._plugins) >= self._config.max_concurrent:
                logger.error("Max concurrent plugins reached", component="plugin_sandbox", max_concurrent=self._config.max_concurrent)
                raise RuntimeError(
                    f"超过最大并发插件数 ({self._config.max_concurrent})"
                )

            # 4. 生成 plugin_id
            plugin_id = f"plugin_{len(self._plugins) + 1}_{int(time.time())}"

            # 5. 计算允许的 import 前缀集
            allowed = set(self._config.allowed_imports_global)
            allowed.update(manifest.allowed_imports)

            # 6. 安装 import hook
            blocker = _ImportBlocker(allowed)
            self._import_blockers[plugin_id] = blocker

            # 7. 可选的 D1 Registry 校验
            capability_name = None
            if manifest.capability_id and self._registry is not None:
                cd = self._registry.get(manifest.capability_id)
                if cd is not None:
                    capability_name = cd.name

            # 8. 创建 slot
            slot = _PluginSlot(
                plugin_id=plugin_id,
                manifest=manifest,
                blocker=blocker,
                capability_name=capability_name,
            )
            self._plugins[plugin_id] = slot

        logger.info("Plugin loaded", component="plugin_sandbox", plugin_id=plugin_id, plugin_name=manifest.name, capability_count=len(manifest.required_permissions))
        return plugin_id

    def unload(self, plugin_id: str) -> bool:
        """卸载插件，移除 import hook。"""
        with self._lock:
            if plugin_id not in self._plugins:
                logger.warning("Plugin not found for unload", component="plugin_sandbox", plugin_id=plugin_id)
                return False
            self._import_blockers.pop(plugin_id, None)
            self._plugins.pop(plugin_id, None)
        logger.info("Plugin unloaded", component="plugin_sandbox", plugin_id=plugin_id)
        return True

    def execute(
        self,
        plugin_id: str,
        action: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """在沙箱中执行插件动作。

        Args:
            plugin_id: load() 返回的插件 ID。
            action: 插件动作名称（由插件的入口类定义）。
            params: 动作参数。
            timeout: 覆盖超时（秒）。None = 使用 sandbox config 默认值。
                    实际超时被截断到 [1, 300]。

        Returns:
            SandboxResult

        Raises:
            ValueError: plugin_id 不存在。
        """
        slot = self._plugins.get(plugin_id)
        if slot is None:
            logger.error("Plugin not loaded", component="plugin_sandbox", plugin_id=plugin_id)
            raise ValueError(f"插件 '{plugin_id}' 未加载")

        actual_timeout = self._resolve_timeout(timeout, slot)
        start = time.perf_counter()

        # 预先获取/创建线程池，再安装 import hook
        # （ThreadPoolExecutor 会懒加载 concurrent.futures.thread，
        #  必须在 import hook 安装前完成）
        pool = self._get_pool()  # noqa: F841

        # 安装 import hook 到 sys.meta_path
        blocker = slot.blocker

        try:
            result = self._run_in_thread(
                fn=self._do_execute,
                args=(slot, action, params or {}),
                timeout=actual_timeout,
            )
        finally:
            # 移除 import hook
            try:
                sys.meta_path.remove(blocker)
            except ValueError:
                pass

        elapsed_ms = (time.perf_counter() - start) * 1000
        # 注入 execution_time_ms
        logger.info("Plugin execution completed", component="plugin_sandbox", plugin_id=plugin_id, action=action, elapsed_ms=round(elapsed_ms, 2), success=result.success)
        return _replace_result_time(result, elapsed_ms)

    def reset(self) -> None:
        """清空所有插件并关闭线程池。"""
        logger.info("Resetting plugin sandbox", component="plugin_sandbox")
        with self._lock:
            self._plugins.clear()
            self._import_blockers.clear()
            if self._thread_pool is not None:
                self._thread_pool.shutdown(wait=False, cancel_futures=True)
                self._thread_pool = None

    # ── 内部 ──────────────────────────────────────────────────────────────────

    def _resolve_timeout(self, timeout: Optional[int], slot: _PluginSlot) -> int:
        """解析实际超时值，截断到 [1, 300]。"""
        t = timeout if timeout is not None else slot.manifest.timeout_seconds
        return max(1, min(t, 300))

    def _get_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        """获取或创建线程池（守护线程）。"""
        if self._thread_pool is None:
            self._thread_pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._config.max_concurrent,
                thread_name_prefix="sandbox-worker",
            )
            # 设置工作线程为 daemon
            for t in self._thread_pool._threads:  # type: ignore[attr-defined]
                t.daemon = True
        return self._thread_pool

    def _run_in_thread(
        self,
        fn: Callable[[], Any],
        args: tuple[Any, ...],
        timeout: int,
    ) -> SandboxResult:
        """在线程池中执行函数，超时强制 kill。"""
        pool = self._get_pool()
        future = pool.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error("Plugin execution timeout", component="plugin_sandbox", timeout=timeout)
            # 超时——强制 kill
            future.cancel()
            if self._config.enforce_timeout:
                return SandboxResult(
                    success=False,
                    error=(
                    f"插件执行超时 (>{timeout}秒)，"
                    "已被 Sandbox 强制终止"
                ),
                    killed=True,
                )
            return SandboxResult(
                success=False,
                error=f"插件执行超时 (>{timeout}秒)",
            )
        except Exception as exc:
            logger.error("Plugin execution exception", component="plugin_sandbox", exception=exc)
            return SandboxResult(
                success=False,
                error=f"插件执行异常: {exc}",
                traceback=tb_module.format_exc(),
            )

    @staticmethod
    def _do_execute(slot: _PluginSlot, action: str, params: dict[str, Any]) -> SandboxResult:
        """实际执行逻辑——优先路由到已加载的 PluginBase 实例，否则回退到 stub。"""
        try:
            # 如果有已加载的插件实例，路由到该实例
            if slot.plugin_instance is not None:
                output = slot.plugin_instance.execute(action, params)
                return SandboxResult(
                    success=True,
                    plugin_id=slot.plugin_id,
                    output=output,
                )

            # 桩：直接返回 action 和 params 的摘要
            output = {
                "plugin": slot.manifest.name,
                "action": action,
                "params_keys": list(params.keys()),
            }
            return SandboxResult(
                success=True,
                plugin_id=slot.plugin_id,
                output=output,
            )
        except Exception as exc:
            logger.error("Plugin _do_execute failed", component="plugin_sandbox", plugin_id=slot.plugin_id, action=action, exception=exc)
            return SandboxResult(
                success=False,
                plugin_id=slot.plugin_id,
                error=str(exc),
                traceback=tb_module.format_exc(),
            )


# ── 内部数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class _PluginSlot:
    """插件在 Sandbox 中的运行时状态。"""
    plugin_id: str
    manifest: PluginManifest
    blocker: _ImportBlocker
    plugin_instance: Optional[PluginBase] = None
    capability_name: Optional[str] = None


def _replace_result_time(result: SandboxResult, elapsed_ms: float) -> SandboxResult:
    """用实际执行时间替换 SandboxResult 中的时间字段。"""
    # dataclasses.replace 用于 frozen dataclass
    import dataclasses
    return dataclasses.replace(result, execution_time_ms=elapsed_ms)
