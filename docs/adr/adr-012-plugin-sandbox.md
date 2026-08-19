# ADR-012: Plugin Sandbox (D2 — 隔离执行环境)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: Platform D2, Plugin Loader, Capability Registry

---

## 背景

插件直接调用 Python import 可以绕过系统约束，访问文件系统、网络、系统命令等。如果不加限制，恶意或有缺陷的插件可能破坏系统状态。需要一层强制执行的安全边界。

## 决策

**建立 PluginSandbox** 作为插件的执行隔离层。

### 隔离手段

1. **Import Hook 白名单** — 拦截 `__import__`，只允许白名单内模块导入（`json`, `math`, `datetime`, `collections`, `typing`, `dataclasses`, `uuid`, `re`, `copy`, `itertools`, `functools`, `enum`, `decimal`）
2. **Permission 系统** — 插件 manifest 声明 `required_permissions`（如 `ACCESS_FILE_SYSTEM`, `ACCESS_NETWORK`, `RUN_SUBPROCESS`, `MODIFY_SYSTEM_STATE`），超出声明则拒绝加载
3. **强制超时终止** — daemon 线程池 + `concurrent.futures` timeout，Sandbox 层面直接回收超时线程，不依赖插件自身响应
4. **并发上限** — `max_concurrent` 配置限制同时执行的插件数

### 数据类型

```python
@dataclass(frozen=True)
class SandboxResult:
    success: bool
    data: Any | None          # 执行结果
    error: str | None         # 错误消息
    execution_time: float     # 实际执行耗时
    permissions_used: frozenset[Permission]
```

### 生命周期

```
sandbox = PluginSandbox()
sandbox.load(manifest, plugin_instance)   # 注册验证
sandbox.execute(pid, action, params)     # 执行（含超时）
sandbox.unload(pid)                      # 清理
sandbox.reset()                          # 完全重置
```

### 可选集成 D1

CapabilityRegistry 接入后可自动注册/注销插件能力。

## 后果

### 获得
- Python 级 import 隔离（不依赖 OS 级容器）
- 超时终止从默认行为变为强制行为
- Permission 声明即契约，manifest 可审计

### 代价
- import 白名单需要维护（插件需要新库时需更新白名单）
- 不是 OS 级隔离（不防止子进程滥用；如需 OS 级隔离需后续扩展 namespace/容器）
- 超时终止可能导致插件状态不一致

## 相关 ADR
- ADR-013: Plugin Loader (D3)
- ADR-006: Capability as Feature
