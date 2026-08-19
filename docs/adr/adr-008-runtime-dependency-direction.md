# ADR-008: Runtime Dependency Direction

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 7 Runtime 及所有 service/ 层模块

---

## 背景

Phase 7 删除验证中发现 `service/_generation.py`, `_structure.py`, `_repair.py`, `_fallback.py` 及 `service/__init__.py` 存在对 `runtime` 的静态导入。这些导入中 `RuntimeBundle` 和 `build_runtime` 在 `opentale/` 下无实际引用，属于死导入。这暴露了一个架构方向问题：service 层不应直接依赖 runtime 层。

## 决策

**Allowed**: `service → runtime.adapter` (通过可选的适配器接口)
**Forbidden**:
- `runtime → service`
- `runtime → pipeline`
- `runtime → decision`

Runtime 是编排层，应只依赖 Contract 和下层认知模块，不应依赖上层业务逻辑。

## 后果

### 获得
- Runtime 层保持纯净，不绑定任何具体业务
- 未来替换 Runtime 实现不影响 service 层
- 删除 Runtime 时不会残留死导入

### 代价
- service 层需要显式传入 Runtime 依赖，而非静态导入

## 实施

- 新增 AST 检查 `test_no_runtime_leak()` 加入 CI
- `service/` 下的 runtime 导入改为惰性导入或依赖注入

## 相关 ADR
- ADR-007: Runtime Orchestration
