# OCOS Allowed Dependencies / Import Rules (Frozen)

**版本**: v1.0
**状态**: Frozen
**冻结日期**: 2026-07-22

## 依赖方向总则

```
                                ocos.kernel
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
        ocos.events           ocos.runtime          ocos.models
               │                    │
               └──────────┬─────────┘
                          │
                    ocos.engines
                          │
                    ocos.plugins
```

## 详细规则

| 源包 | 可用依赖 | 禁止依赖 |
|------|----------|----------|
| `ocos` (root) | — | 任何子包 |
| `ocos.kernel` | Python 标准库 | `ocos.*` 任何包（Kernel 零依赖） |
| `ocos.events` | `ocos.kernel` | `ocos.runtime`, `ocos.engines`, `ocos.plugins` |
| `ocos.runtime` | `ocos.kernel`, `ocos.events` | `ocos.engines`, `ocos.plugins` |
| `ocos.models` | `ocos.kernel` | `ocos.runtime`, `ocos.engines`, `ocos.plugins` |
| `ocos.engines.*` | `ocos.kernel`, `ocos.events`, `ocos.models` | `ocos.runtime`（禁止反向依赖）|
| `ocos.plugins.*` | `ocos.kernel`, `ocos.events`, `ocos.engines.*` | `ocos.runtime`（插件不可操作运行时）|

## 通信规则

- **禁止** `ocos.engines` 之间直接 import 或函数调用
- **唯一通信通道**: Event Bus（`ocos.events`）
- **唯一动作源**: Decision（`ocos.runtime` 或通过 Event Bus 调度）
- **Plugin 不可改变系统状态**（只读注入 + 事件输出）

## 特殊例外

- 单元测试可依赖测试工具链（pytest, mock）
- 架构测试（`tests/`）可导入所有包进行合法性验证
- 以上例外必须在测试文件中显式标注 `# pragma: allow-import-for-testing`
