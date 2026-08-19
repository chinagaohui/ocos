# ADR-006: Capability as Feature

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 5 Capability

---

## 背景

外部能力（LLM 调用、API 接入、工具执行）在传统架构中常被内联到业务逻辑中，导致能力变更需要修改核心代码。

## 决策

**Capability 作为独立可拔插的特征接入系统。**

- 每个 Capability 必须有明确的输入/输出 Contract
- Capability 只能提供计算，不能修改状态
- Capability 的输出必须经过 Candidate 转换才能进入系统

```
Capability Registry
├── LLM Caller        (ParsedCandidate → Candidate)
├── Tool Executor     (执行结果 → Candidate)
└── API Bridge        (外部请求/响应 → Candidate)
```

Capability 只能被以下模块调用：
- Reasoning（通过 Candidate）
- Pipeline（通过 Runtime）
- 不允许直接被 Knowledge 层调用

## 后果

### 获得
- 新增/替换 Capability 不影响核心
- 所有外部能力接入统一经过 Contract 检查
- 能力可以独立进行版本化

### 代价
- 每个能力接入需要额外适配层
- 能力输出不能直接作为"事实"

## 相关 ADR
- ADR-002: Capability Output Isolation
- ADR-003: Contract Boundary
