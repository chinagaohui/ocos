# ADR-003: Contract Boundary

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: 全局，所有层

---

## 背景

层间直接导入导致耦合度不断上升。一个模块的内部数据结构的变更可能引发大范围修改。

## 决策

**层间通信必须通过 Contract 数据结构**。Contract 定义在 `contracts/` 层，只依赖 Python 标准库。

```
层 A → Contract → 层 B
```

当前 16 个 Contract：

| Contract | 用途 |
|----------|------|
| `event.py` | 事件数据结构 |
| `observation.py` | 观测数据 |
| `experience.py` | 经验记录 |
| `candidate.py` | LLM 输出的候选方案 |
| `reasoning_result.py` | 推理结果 |
| `pattern.py` | 模式匹配结果 |
| `principle.py` | 原则约束 |
| `capability_pattern.py` | Capability 能力描述 |
| `runtime.py` | 运行时上下文 |
| `adaptation.py` | 适应性和演化相关 |
| `evolution_proposal.py` | 演化提案 |
| `evolution_memory.py` | 演化记忆 |
| `performance.py` | 性能指标 |
| `validated_contract.py` | 验证后的合约包装 |
| `writer_contract.py` | 小说写作合约 |
| `narrative_contract.py` | 叙事合约 |

## 后果

### 获得
- 层间解耦
- Contract 变更可独立版本化
- 测试时可以 mock 任意层

### 代价
- 需要额外的数据转换代码
- Contract 变更需要多版本兼容

## 相关 ADR
- ADR-001: Decision-Based State Mutation
