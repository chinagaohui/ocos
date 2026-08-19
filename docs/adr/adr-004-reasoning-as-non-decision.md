# ADR-004: Reasoning as Non-Decision

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 4 Reasoning, Phase 5 Capability

---

## 背景

传统 AI 系统中推理引擎直接输出决策。这导致系统无法区分"思考过程"和"最终结论"，也无法对推理结果进行独立的 Governance 审查。

## 决策

**Reasoning 只产生候选方案和权衡分析，不做最终选择。**

铁律约束：
- 铁律 29：Reasoning 不排名（Tradeoff 不排序）
- 铁律 30：Reasoning 是一次性的（不缓存）
- 铁律 33：LLM 产出可能性，不是真理
- 铁律 34：LLM 输出不可信

```
Reasoning Input → Candidates → Tradeoff → ReasoningResult
                                                    ↓
                                           Workspace (临时)
                                                    ↓
                                           Decision (外部层)
```

## 后果

### 获得
- 推理过程可审查
- Decision 来源可追溯
- 支持多候选方案的 A/B 测试

### 代价
- 需要额外的 Decision 层执行选择
- 推理结果不会立即生效

## 相关 ADR
- ADR-001: Decision-Based State Mutation
- ADR-002: Capability Output Isolation
