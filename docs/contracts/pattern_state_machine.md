# Phase14.3 — Pattern Lifecycle State Machine

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)

## 1. 状态图

```
                ┌──────────┐
                │  Mining  │
                └────┬─────┘
                     │
                     ▼
              ┌──────────────┐
              │   Candidate  │
              └──┬────────┬──┘
          ┌──────┘        └──────┐
          ▼                      ▼
   ┌────────────┐        ┌──────────────┐
   │  Validated  │        │   Rejected   │
   └──┬──────┬──┘        └──────┬───────┘
      │      │                  │
      ▼      ▼                  ▼
   ┌──────────────┐     ┌──────────────┐
   │   Archived   │◄────│   Archived   │
   └──┬───────────┘     └──────────────┘
      │
      ▼
   ┌──────────────┐
   │  Invalidated │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │   Archived   │
   └──────────────┘
```

## 2. 合法转换

| 源状态 | 目标状态 | 条件 | 描述 |
|--------|----------|------|------|
| (Mining) | Candidate | 首次发现 | Mining Engine 输出原始候选 |
| Candidate | Validated | 统计验证通过 | 满足 frequency + stability + counter-evidence 阈值 |
| Candidate | Rejected | 统计验证未通过 | 未达到阈值 |
| Candidate | Archived | 主动归档 | 算法版本升级等 |
| Validated | Archived | 历史保存 | 不再参与当前 Pattern Discovery |
| Validated | Invalidated | 新 Evidence 不支持 | 曾经成立,但新增样本不再复现 |
| Archived | Invalidated | 新 Evidence 不支持 | 归档模式被证伪 |
| Invalidated | Archived | 最终归档 | Invalidated 模式的终点 |

## 3. 非法转换 (永久禁止)

| 源状态 → 目标状态 | 原因 |
|-------------------|------|
| Candidate → Candidate | 禁止自循环 |
| Rejected → Candidate | 统计未满足的条件不能重新进入管线;如需重试,需重新 Mining |
| Rejected → Validated | 跳过重新 Mining 直接通过验证,违反审计链 |
| Invalidated → Validated | 被证伪的模式不能复活 |
| Invalidated → Candidate | 被证伪的模式不能重新进入管线 |
| Archived → Validated | 归档模式不能跳过重新验证直接通过 |
| Archived → Candidate | 归档模式不能重新进入管线 |

## 4. 禁止状态值

以下值**不得**作为 Pattern 或 PatternCandidate 的状态:

```
good       bad        useful
effective  preferred  recommended
high       medium     low
excellent  poor       average
```

## 5. 状态机约束

| 规则 | 描述 |
|------|------|
| SM1 | 状态转换必须遵循合法转换表 |
| SM2 | 禁止状态值不得出现在 status 字段 |
| SM3 | 每个转换必须记录时间戳和原因 |
| SM4 | Archived 是唯一最终状态 (Invalidated 也必须最终进入 Archived) |
