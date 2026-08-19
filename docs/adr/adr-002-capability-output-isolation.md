# ADR-002: Capability Output Isolation

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 5 Capability, Phase 4 Reasoning

---

## 背景

LLM 输出直接进入知识层会导致无法区分的污染——系统无法判断一个"知识"来自经验积累还是外部模型。

## 决策

**所有 Capability 输出必须经过 Candidate 转换**，且 Candidate 只能进入 Reasoning 空间，不能直接进入 Knowledge 层。

```
LLM → ParsedCandidate → Candidate (Contract)
     ↓
Reasoning → Tradeoff → Result (不含选择)
     ↓
Decision (外部层执行)
```

## 后果

### 获得
- 知识来源可追溯
- LLM 可以输出多候选项，但不做选择
- 知识层只存储经验证的知识

### 代价
- 每个 Capability 输出需要显式的 Candidate 转换
- 无法直接将外部输出作为"事实"写入

## 相关 ADR
- ADR-006: Capability as Feature
