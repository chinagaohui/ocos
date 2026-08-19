# OCOS Naming Convention (Frozen)

**版本**: v1.0
**状态**: Frozen
**冻结日期**: 2026-07-22
**对应宪法**: `../docs/OCOS_CORE_CONSTITUTION.md`

## 包命名

| 层级 | 命名规则 | 示例 |
|------|----------|------|
| 顶级包 | 全小写 | `ocos` |
| 子系统 | 全小写，单数 | `ocos.kernel`, `ocos.runtime` |
| 引擎 | 全小写，名词 | `ocos.engines.reasoning`, `ocos.engines.attention` |
| 插件 | 全小写 | `ocos.plugins.opentale` |
| 子模块 | 全小写下划线 | `ocos.events.event_store` |

## 类命名

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 核心对象 (不可变) | PascalCase | `Observation`, `Memory`, `Decision` |
| Event 类型 | PascalCase + `Event` 后缀 | `ObservationReceivedEvent`, `DecisionExecutedEvent` |
| Engine | PascalCase + `Engine` 后缀 | `ReasoningEngine`, `AttentionEngine` |
| 配置 | PascalCase + `Config` 后缀 | `KernelConfig`, `EventBusConfig` |
| 异常 | PascalCase + `Error` 后缀 | `ConstitutionViolationError`, `ABIVersionMismatchError` |

## 函数/方法命名

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 方法 | snake_case | `def process_observation()` |
| 属性 | snake_case | `def observation_count` |
| 私有 | snake_case + `_` 前缀 | `def _validate_invariants()` |

## 模块命名前缀

所有核心模块以 `Ocos` 为前缀（仅在类的上下文中）：
- `OcosKernel`, `OcosRuntime`
- 内部引擎不使用前缀

## 文件命名

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| Python 模块 | snake_case | `constitution.py`, `event_schema.py` |
| 测试 | `test_` 前缀 | `test_constitution.py`, `test_import_rules.py` |
| 合约文档 | 全大写 + 下划线 | `META_CONTROL_OWNERSHIP.md` |
