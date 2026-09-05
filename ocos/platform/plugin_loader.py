"""
D3 Plugin Loader — 动态发现、加载、执行插件。

职责：
1. discover()  — 扫描文件系统，发现 plugin.json 配置文件
2. load()      — 动态加载 Python 包，校验 PluginBase 接口，注册到 Sandbox
3. execute()   — 委托 Sandbox 在隔离环境中执行插件动作
4. unload()    — 卸载插件，清理 Sandbox 和实例资源

架构定位：
  PluginLoader 是 Plugin Framework 的加载管理层。
  底层隔离由 PluginSandbox (D2) 提供（import hook、超时终止、权限校验）。
  上层可选集成 CapabilityRegistry (D1) 注册插件能力。
"""

from __future__ import annotations

import importlib
import json
import warnings
from pathlib import Path
from typing import Any, Optional

from ocos.platform.plugin_base import PluginBase
from ocos.platform.plugin_manifest import PluginManifest, Permission, validate_manifest
from ocos.platform.plugin_sandbox import PluginSandbox, SandboxResult
from ocos.logging import get_logger

logger = get_logger(__name__)

# ── 错误码枚举 ─────────────────────────────────────────────────────────────────


class LoaderErrorCode(str):
    """PluginLoader 标准错误码。"""

    LOAD_OK = "load.ok"
    LOAD_FAILED = "load.failed"
    LOAD_FORBIDDEN_IMPORT = "load.forbidden_import"  # S1.4: AST 静态门拒绝
    LOAD_DUPLICATE = "load.duplicate"
    EXEC_OK = "exec.ok"
    EXEC_FAILED = "exec.failed"
    TIMEOUT = "exec.timeout"
    KILLED = "exec.killed"
    UNLOAD_OK = "unload.ok"
    UNLOAD_FAILED = "unload.failed"


# S1.4 (白皮书 P1-8): 插件静态门 — 沙箱 import hook 只能在"执行期"拦截
# 新 import，而 load 期的 importlib.import_module 会把插件模块完整加载进
# 宿主进程。因此在加载前对插件源码做 AST 扫描，高危模块一律拒绝。
FORBIDDEN_IMPORT_MODULES: frozenset[str] = frozenset({
    "os", "subprocess", "socket", "shutil", "ctypes", "signal",
    "multiprocessing", "importlib", "pickle",
})


def ast_forbidden_import_check(source: str) -> list[str]:
    """AST 扫描插件源码中的高危 import，返回违规列表（空 = 通过）。

    覆盖三种形态：`import X` / `from X import ...` /
    `__import__("X")`；`import a.b` 与 `from a.b import c` 按**顶层
    包名**判定（os.path 归 os）。
    """
    import ast
    violations: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SYNTAX_ERROR: {e}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_IMPORT_MODULES:
                    violations.append(f"IMPORT: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if node.level == 0 and top in FORBIDDEN_IMPORT_MODULES:
                    violations.append(f"FROM_IMPORT: {node.module}")
        elif isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id == "__import__"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                top = node.args[0].value.split(".")[0]
                if top in FORBIDDEN_IMPORT_MODULES:
                    violations.append(f"DYNAMIC_IMPORT: {node.args[0].value}")
    return violations


# ── 加载结果 ──────────────────────────────────────────────────────────────────


class LoadResult:
    """插件加载结果。"""

    def __init__(
        self,
        success: bool,
        plugin_id: str = "",
        code: str = LoaderErrorCode.LOAD_FAILED,
        message: str = "",
    ) -> None:
        self.success = success
        self.plugin_id = plugin_id
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return (
            f"LoadResult(success={self.success}, plugin_id={self.plugin_id!r}, "
            f"code={self.code!r}, message={self.message!r})"
        )


# ── Plugin Loader ─────────────────────────────────────────────────────────────


class PluginLoader:
    """Plugin 加载器——负责插件的全生命周期管理。

    使用方式：
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=["./plugins"])

        manifests = loader.discover()
        for m in manifests:
            result = loader.load(m)
            if result.success:
                exec_result = loader.execute(result.plugin_id, "run", {"key": "value"})
                loader.unload(result.plugin_id)
    """

    def __init__(
        self,
        sandbox: PluginSandbox,
        search_paths: Optional[list[str | Path]] = None,
    ) -> None:
        """
        Args:
            sandbox: PluginSandbox 实例（必须，提供隔离执行环境）
            search_paths: 插件扫描路径列表（字符串或 Path），
                          默认 ['plugins', './plugins']
        """
        self._sandbox = sandbox
        self._search_paths = [
            Path(p) for p in (search_paths or ["plugins", "./plugins"])
        ]
        # plugin_id → (PluginBase, PluginManifest)
        self._instances: dict[str, tuple[PluginBase, PluginManifest]] = {}
        # entry_point → plugin_id（重复加载检测）
        self._entry_point_index: dict[str, str] = {}
        # manifest 文件路径 → plugin_id（discover -> load 跟踪）
        self._discovered: list[PluginManifest] = []
        logger.debug("PluginLoader initialized",
                      component="plugin_loader",
                      search_paths=[str(p) for p in self._search_paths])

    # ── 属性 ─────────────────────────────────────────────────────────────────

    @property
    def sandbox(self) -> PluginSandbox:
        """底层的 PluginSandbox 实例。"""
        return self._sandbox

    @property
    def loaded_count(self) -> int:
        """当前已加载的插件数。"""
        return len(self._instances)

    @property
    def search_paths(self) -> list[Path]:
        """插件搜索路径列表（只读副本）。"""
        return list(self._search_paths)

    # ── 发现 ─────────────────────────────────────────────────────────────────

    def discover(self) -> list[PluginManifest]:
        """扫描所有搜索路径，发现 plugins.json 配置并解析为 PluginManifest。

        容错规则：
        - 不存在的路径 → 跳过
        - 没有 plugin.json 的子目录 → 跳过
        - 非法 JSON 或缺少必填字段 → 跳过并 warn
        - 无效的 entry_point 格式 → 跳过并 warn

        Returns:
            所有成功解析的 PluginManifest 列表
        """
        manifests: list[PluginManifest] = []

        for base_path in self._search_paths:
            resolved = Path(base_path).resolve()
            if not resolved.is_dir():
                continue

            for candidate in sorted(resolved.iterdir()):
                if not candidate.is_dir():
                    continue
                manifest_path = candidate / "plugin.json"
                if not manifest_path.is_file():
                    continue

                manifest = self._parse_manifest_file(manifest_path)
                if manifest is not None:
                    manifests.append(manifest)

        self._discovered = manifests
        logger.info("Plugin discovery completed",
                     component="plugin_loader",
                     discovered_count=len(manifests))
        return list(manifests)

    # ── 加载 ─────────────────────────────────────────────────────────────────

    def load(
        self,
        manifest: PluginManifest,
        config: Optional[dict[str, Any]] = None,
    ) -> LoadResult:
        """加载一个插件。

        流程：
        1. 验证 manifest（委托 validate_manifest）
        2. 重复加载检测（相同 entry_point 已存在则返回已有 plugin_id）
        3. importlib 动态加载入口模块
        4. 反射获取入口类，校验是否为 PluginBase 子类
        5. 实例化插件
        6. 注册到 PluginSandbox
        7. 将实例存入 Sandbox 的 _PluginSlot.plugin_instance
        8. 调用 plugin.on_load(config)

        Args:
            manifest: 插件声明清单
            config: 插件初始化配置（可选，传入 on_load）

        Returns:
            LoadResult
        """
        # 1. 验证 manifest
        reason = validate_manifest(manifest)
        if reason is not None:
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"Manifest 验证失败: {reason}",
            )

        # 2. 重复加载检测
        existing_pid = self._entry_point_index.get(manifest.entry_point)
        if existing_pid is not None:
            logger.info(
                "重复加载检测: entry_point '%s' 已被加载为 plugin_id='%s'，返回已有 ID",
                manifest.entry_point, existing_pid,
            )
            return LoadResult(
                success=True,
                plugin_id=existing_pid,
                code=LoaderErrorCode.LOAD_DUPLICATE,
                message=f"重复加载，返回已有 plugin_id: {existing_pid}",
            )

        # 3. 动态加载入口模块
        module_path, _, class_name = manifest.entry_point.rpartition(":")
        # S1.4: AST 静态门 — 高危 import 在进入宿主进程前拒绝
        try:
            spec = importlib.util.find_spec(module_path)
            if spec is not None and spec.origin and spec.origin != "builtins":
                source = Path(spec.origin).read_text(encoding="utf-8")
                violations = ast_forbidden_import_check(source)
                if violations:
                    logger.error(
                        "插件静态门拒绝加载: %s 违规 import %s",
                        module_path, violations[:5],
                    )
                    return LoadResult(
                        success=False,
                        code=LoaderErrorCode.LOAD_FORBIDDEN_IMPORT,
                        message=(f"禁止的 import（高危模块静态门）: "
                                 f"{violations[:5]}"),
                    )
        except (ImportError, OSError, AttributeError) as exc:
            # 源码定位失败不放大故障 — 交给后续 import 步骤诚实报错
            logger.debug("静态门跳过（无法定位源码）: %s (%s)",
                         module_path, exc)
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"导入模块失败 '{module_path}': {exc}",
            )

        # 4. 反射获取入口类
        plugin_class = getattr(module, class_name, None)
        if plugin_class is None:
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"模块 '{module_path}' 中未找到类 '{class_name}'",
            )

        # 5. 校验是否为 PluginBase 子类
        if not issubclass(plugin_class, PluginBase):
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=(
                    f"类 '{class_name}' 未继承 PluginBase。"
                    " 所有插件必须继承 ocos.platform.plugin_base.PluginBase"
                ),
            )

        # 6. 实例化
        try:
            plugin_instance = plugin_class(manifest=manifest)
        except Exception as exc:
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"插件实例化失败: {exc}",
            )

        # 7. 注册到 Sandbox
        try:
            plugin_id = self._sandbox.load(manifest)
        except (ValueError, RuntimeError) as exc:
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"Sandbox 注册失败: {exc}",
            )

        # 8. 将实例存入 Sandbox slot
        slot = getattr(self._sandbox, "_plugins", {}).get(plugin_id)
        if slot is not None:
            slot.plugin_instance = plugin_instance

        # 9. 调用 on_load
        try:
            plugin_instance.on_load(config or {})
        except Exception as exc:
            # on_load 失败：回滚 sandbox 注册
            self._sandbox.unload(plugin_id)
            return LoadResult(
                success=False,
                code=LoaderErrorCode.LOAD_FAILED,
                message=f"插件 on_load 回调执行失败: {exc}",
            )

        # 10. 记录实例和索引
        self._instances[plugin_id] = (plugin_instance, manifest)
        self._entry_point_index[manifest.entry_point] = plugin_id

        logger.info("Plugin loaded",
                     component="plugin_loader",
                     plugin_id=plugin_id,
                     plugin_name=manifest.name,
                     plugin_version=manifest.version)

        return LoadResult(
            success=True,
            plugin_id=plugin_id,
            code=LoaderErrorCode.LOAD_OK,
            message=f"插件 '{manifest.name}' (v{manifest.version}) 加载成功",
        )

    # ── 执行 ─────────────────────────────────────────────────────────────────

    def execute(
        self,
        plugin_id: str,
        action: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """在 Sandbox 隔离环境中执行插件动作。"""
        result = self._sandbox.execute(
            plugin_id=plugin_id,
            action=action,
            params=params or {},
            timeout=timeout,
        )
        logger.info("Plugin action executed",
                     component="plugin_loader",
                     plugin_id=plugin_id,
                     action=action,
                     success=result.success)
        return result

    # ── 卸载 ─────────────────────────────────────────────────────────────────

    def unload(self, plugin_id: str) -> bool:
        """卸载一个插件。

        流程：
        1. 调用 plugin.on_unload()
        2. 通知 Sandbox 释放资源（sandbox.unload）
        3. 从内部注册表中移除

        Returns:
            True 卸载成功，False 插件不存在
        """
        instance_data = self._instances.get(plugin_id)
        if instance_data is None:
            return False

        plugin_instance, manifest = instance_data

        # 1. 调用 on_unload
        try:
            plugin_instance.on_unload()
        except Exception:
            logger.warning(
                "插件 '%s' on_unload 回调异常", manifest.name, exc_info=True
            )

        # 2. 通知 Sandbox 释放资源
        self._sandbox.unload(plugin_id)

        # 3. 清理索引
        self._instances.pop(plugin_id, None)
        for ep, pid in list(self._entry_point_index.items()):
            if pid == plugin_id:
                del self._entry_point_index[ep]
                break

        logger.info("Plugin unloaded",
                     component="plugin_loader",
                     plugin_id=plugin_id,
                     plugin_name=manifest.name)

        return True

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get_instance(self, plugin_id: str) -> Optional[PluginBase]:
        """按 plugin_id 获取已加载的插件实例。"""
        data = self._instances.get(plugin_id)
        return data[0] if data is not None else None

    def find_by_name(self, name: str) -> Optional[PluginBase]:
        """按插件名称查找最新加载的实例。"""
        for pid in reversed(list(self._instances.keys())):
            inst, manifest = self._instances[pid]
            if manifest.name == name:
                return inst
        return None

    def list_loaded(self) -> list[tuple[str, str, str]]:
        """列出所有已加载插件：(plugin_id, name, version)。"""
        return [
            (pid, m.name, m.version)
            for pid, (_, m) in self._instances.items()
        ]

    # ── 集成 CapabilityRegistry（可选） ──────────────────────────────────────

    def register_to(
        self, registry: Any, manifests: Optional[list[PluginManifest]] = None
    ) -> list[str]:
        """将插件 Manifest 注册到 D1 CapabilityRegistry。

        对每个 manifest，注册一个 PLUGIN 类型的 CapabilityDescriptor。
        注册失败不影响其他插件。

        Args:
            registry: CapabilityRegistry 实例
            manifests: 要注册的 manifest 列表，默认使用最近 discover() 的结果

        Returns:
            成功注册的 capability_id 列表
        """
        from ocos.platform.capability_registry import CapabilityType

        targets = manifests if manifests is not None else self._discovered
        registered: list[str] = []

        for manifest in targets:
            try:
                cid = registry.register(
                    type=CapabilityType.PLUGIN,
                    name=manifest.name,
                    description=manifest.description,
                    version=manifest.version,
                    entry_point=manifest.entry_point,
                    metadata={
                        "timeout_seconds": manifest.timeout_seconds,
                        "required_permissions": [
                            p.value for p in manifest.required_permissions
                        ],
                        "allowed_imports": list(manifest.allowed_imports),
                    },
                )
                registered.append(cid)
            except Exception as exc:
                logger.warning("注册插件 '%s' 到 CapabilityRegistry 失败: %s", manifest.name, exc)

        return registered

    # ── 批量操作 ────────────────────────────────────────────────────────────

    def load_all(
        self,
        manifests: Optional[list[PluginManifest]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> list[LoadResult]:
        """批量加载所有发现的插件。"""
        targets = manifests if manifests is not None else self._discovered
        results: list[LoadResult] = []
        for manifest in targets:
            result = self.load(manifest, config=config)
            results.append(result)
        logger.info("Batch load completed",
                     component="plugin_loader",
                     target_count=len(targets),
                     success_count=sum(1 for r in results if r.success))
        return results

    def unload_all(self) -> int:
        """卸载所有已加载的插件。

        Returns:
            成功卸载的插件数量
        """
        count = 0
        for plugin_id in list(self._instances.keys()):
            if self.unload(plugin_id):
                count += 1
        logger.info("Batch unload completed",
                     component="plugin_loader",
                     unloaded_count=count)
        return count

    # ── 重置 ────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """重置 Loader 状态——卸载所有插件、清空索引、清空发现列表。"""
        self.unload_all()
        self._discovered.clear()
        self._sandbox.reset()
        logger.info("PluginLoader reset",
                     component="plugin_loader")

    # ── 内部 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_manifest_file(manifest_path: Path) -> Optional[PluginManifest]:
        """解析一个 plugin.json 文件，返回 PluginManifest 或 None（跳过）。"""
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warnings.warn(
                f"跳过非法 plugin.json '{manifest_path}': {exc}"
            )
            return None

        # 必填字段
        name = data.get("name", "")
        entry_point = data.get("entry_point", "")

        # 检查必填（尽早返回，不尝试构建无效 manifest）
        if not name or not entry_point:
            warnings.warn(
                f"跳过 plugin.json '{manifest_path}': "
                "缺少必填字段 'name' 或 'entry_point'"
            )
            return None

        # 解析权限
        raw_perms = data.get("required_permissions", [])
        permissions: tuple[Permission, ...] = ()
        if isinstance(raw_perms, list):
            perm_list: list[Permission] = []
            for rp in raw_perms:
                try:
                    perm_list.append(Permission(rp))
                except ValueError:
                    warnings.warn(
                        f"plugin.json '{manifest_path}' 中有未知权限 '{rp}'，跳过"
                    )
            permissions = tuple(perm_list)

        manifest = PluginManifest(
            name=name,
            version=data.get("version", "0.1.0"),
            entry_point=entry_point,
            description=data.get("description", ""),
            required_permissions=permissions,
            timeout_seconds=data.get("timeout_seconds", 30),
            allowed_imports=tuple(data.get("allowed_imports", [])),
            capability_id=data.get("capability_id", ""),
            metadata={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "name",
                    "version",
                    "entry_point",
                    "description",
                    "required_permissions",
                    "timeout_seconds",
                    "allowed_imports",
                    "capability_id",
                )
            },
        )

        # 最终验证
        reason = validate_manifest(manifest)
        if reason is not None:
            warnings.warn(
                f"跳过 plugin.json '{manifest_path}': {reason}"
            )
            return None

        return manifest
