# ADR-014: Release Gate (E4 — 冻结准入标准)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: 全局，所有冻结模块

---

## 背景

Phase E 之前，模块冻结缺乏统一的准入标准。Phase14/15/16 各用不同的审计方式，导致冻结深度不一致：有的仅有证书，有的附带全审计。需要标准化 Release Gate 流程，确保每个模块冻结前经过相同的 14 维检查。

## 决策

**建立 Release Gate 四步流程**，基于 AFP (Architecture Freeze Protocol) 的 F1-F14 全部覆盖。

### 四步流程

```
RC Build → Architecture Audit → Stress Audit → Compatibility Audit → Freeze
```

| 步骤 | 验证 | 工具 |
|------|------|------|
| 1. RC 构建 | 版本号锁定，manifest 冻结，依赖固化 | 手工 |
| 2. 架构审计 | F1-F14 全扫描 | `release_gate_audit.py` |
| 3. 压力审计 | 24h 稳定性指标检查 | E2 套件 |
| 4. 兼容性审计 | ABI 向后兼容 + 回滚能力 | E3 套件 |

### 14 维审计指标（AFP 映射）

| 维度 | AFP 映射 | 检查点 |
|------|----------|--------|
| F1 ABI 完整性 | Constitution Part 3 | ABI 接口全部实现，frozen dataclass schema_version |
| F2 Ownership | Constitution Part 5 | 文件 Ownership 声明明确 |
| F3 生命周期 | Constitution Part 6 | 状态机合法转换 |
| F4 超时恢复 | 安全需求 | 超时机制可正确恢复 |
| F5 隔离性 | Constitution Part 4 | 禁止直接 import，强制 Event Bus |
| F6 依赖方向 | A0 冻结 | 包依赖方向矩阵 |
| F7 禁止操作 | 宪法 8 条规则 | 不可变规则未被违反 |
| F8 确定性 | 安全需求 | 相同输入产生相同输出 |
| F9 身份保持 | D3 | 插件/组件 ID 不变 |
| F10 透明性 | Constitution Part 7 | Trace 记录可查询 |
| F11 无副作用 | 安全需求 | 核心路径无系统状态变更 |
| F12 OpenTale 边界 | D4 | 第一个真实插件接入验证 |
| F13 演化审计 | AFP 10 阶段 | 5 道架构漂移检查 |
| F14 可替换性 | AFP 10 阶段 | 7 项量化替换性指标 |

### 输出

- `release_gate_audit.py` — 自动化审计脚本（83 项检查）
- `e4_platform_release_gate_certificate.md` — 冻结证书

## 后果

### 获得
- 所有模块经过统一 14 维检查，冻结深度一致
- 审计脚本可重复执行，CI 中可集成
- Freeze Certificate 作为唯一权威来源，替代分散的检查清单

### 代价
- 冻结前需要运行完整审计套件（~5s 完成 83 项检查）
- 新增模块需要补充 14 维中部分维度的检查项

## 相关 ADR
- AFP: `docs/ARCHITECTURE_FREEZE_PROTOCOL.md`
- ADR-013: Plugin Loader (D3)
- ADR-012: Plugin Sandbox (D2)
