# ADR-013: Plugin Loader (D3 — 动态加载管理层)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: Platform D3, Plugin Sandbox, Capability Registry

---

## 背景

插件需要动态发现、加载、卸载，且必须经过 Sandbox 隔离。如果插件管理逻辑与隔离逻辑耦合在一起，未来更换隔离策略（如切换到 OS 容器）需要重写整个插件框架。

## 决策

**PluginLoader 与 PluginSandbox 职责分离**：

```
PluginLoader  (D3) → 管理插件生命周期
PluginSandbox (D2) → 隔离执行环境
```

### Loader 职责

1. `discover(path)` — 扫描文件系统，读取 `plugin.json` 配置文件，组装 PluginManifest
2. `load(manifest)` — 动态加载 Python 包，校验 `PluginBase` 子类实现，注册到 Sandbox
3. `execute(pid, action, params)` — 委托 Sandbox 执行（不直接调用插件实例）
4. `unload(pid)` — 卸载插件，清理 Sandbox 和实例资源

### 错误码系统

```python
class LoaderErrorCode(str):
    LOAD_OK / LOAD_FAILED / LOAD_DUPLICATE
    EXEC_OK / EXEC_FAILED / TIMEOUT / KILLED
    UNLOAD_OK / UNLOAD_FAILED
```

所有加载操作返回 `LoadResult` 结构化结果，包含 success、error_code、plugin_id、message。

### 标准接口校验

Loader 在 load 时检查插件类是否实现了 `PluginBase` 的 5 个接口：
- `get_actions()`
- `execute(action, params)`
- `get_status()`
- `on_load(context)`
- `on_unload()`

### 身份保持

已加载的插件保持 `plugin_id` 不变，即使卸载后重新加载同一 manifest。

## 后果

### 获得
- Loader 与 Sandbox 解耦，可独立升级隔离策略
- 结构化错误码，调用方可精确处理异常
- PluginBase 接口校验在加载时完成，执行时无额外检查开销

### 代价
- 增加一个抽象层（Loader 不直接执行操作，需要委托 Sandbox）
- manifest 文件（`plugin.json`）必须存在且格式正确

## 相关 ADR
- ADR-012: Plugin Sandbox (D2)
- ADR-009: Trace Engine (C1)
