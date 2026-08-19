# KNOWLEDGE MODEL v1.0

**版本**: v1.0
**状态**: Frozen ❄️
**冻结日期**: 2026-07-22
**层次定位**: Layer 3 — 知识的形式化定义与组织模型
**前置依赖**: [INFORMATION_THEORY.md](./INFORMATION_THEORY.md), [INFORMATION_LIFECYCLE.md](./INFORMATION_LIFECYCLE.md)

---

## 第一章：Knowledge 的定义

### 1.1 什么是 Knowledge

> **Knowledge = Verified + Generalizable + Stable Information**

Knowledge 不是独立概念。它是 Information 在满足三个条件时的特化形态：

| 条件 | 含义 | 反面示例 |
|------|------|----------|
| **Verified** | 通过了验证流程（格式校验、完整性检查、冲突检测、证据链确认） | 一个未被核实的 Observation、未经验证的 Pattern |
| **Generalizable** | 能够迁移到新场景，指导未来行为，而非仅描述特定实例 | "这个角色在场景 A 说了这句话"（Memory，不可泛化）|
| **Stable** | 不会随时间自动衰减或过期（Persistence ≥ Stable） | 当前会话的临时偏好（Session 级别，会自动遗忘）|

### 1.2 不是 Knowledge 的 Information

| 类型 | 为什么不是 Knowledge |
|------|---------------------|
| **Observation** | 未验证，未泛化。仅代表一次感知。 |
| **Memory** | 可能是已验证的（例如记下的电话号码），但未泛化——它描述的是过去，不是一般规则。 |
| **Trace** | 不是 Information（见 INFORMATION_THEORY 附录 C）。 |
| **Goal** | 描述期望状态，不要求验证和泛化。 |
| **Decision** | 描述已做选择，不一定已验证或泛化。 |

### 1.3 Knowledge 与 Information Theory 的关系

```
INFORMATION_THEORY
  │
  ├── Information (Layer 0: 所有认知对象的底层定义)
  │     │
  │     ├── Knowledge = Verified + Generalizable + Stable Information
  │     │     └── 本文档
  │     │
  │     ├── Memory = 可被 Retain 和 Access 的 Information
  │     ├── Goal = 描述期望状态的 Information
  │     └── ...（Identity, Policy, Decision）
  │
  ├── Information Lifecycle (Layer 2: 生命周期契约)
  │
  └── Information Graph (Layer 1: 关系网络)
```

---

## 第二章：Knowledge 的原子单元

### 2.1 KnowledgeUnit

```python
@dataclass(frozen=True)
class KnowledgeUnit:
    unit_id: str
    level: KnowledgeLevel
    content: dict
    evidence_chain: list[str]   # source Information IDs
    confidence: float
    status: KnowledgeStatus
    created_at: str
    updated_at: str
    version: int
    source: str
    owner: str
```

### 2.2 KnowledgeLevel（提升链）

```
Observation → Evidence → Pattern → Principle → Policy
```

| 层级 | 含义 | 验证程度 | 示例 |
|------|------|----------|------|
| **Observation** | 原始感知输入 | 最低 | "用户修改了第 3 章开头" |
| **Evidence** | 支持/反驳某个结论的事实 | 格式和来源校验 | "用户过去 10 次修改中有 7 次在开头 200 字" |
| **Pattern** | 多个 Evidence 提炼的可重复结构 | 统计显著性 | "用户倾向于在章节开头做高频微调" |
| **Principle** | 跨越多个 Pattern 的通用规律 | 多域验证 | "创作质量取决于前 200 字的密度" |
| **Policy** | 系统应遵守的行为约束 | 最高（Governance 审批） | "章节开头修改必须保留原始 3 个版本" |

### 2.3 KnowledgeStatus

```
CANDIDATE → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
```

与 INFORMATION_LIFECYCLE 的 8 阶段对齐。

---

## 第三章：提升（Elevation）规则

| 从 → 到 | 条件 | 是否需要 Governance |
|---------|------|-------------------|
| Observation → Evidence | 格式校验 + 来源可信 | 否 |
| Evidence → Pattern | 重复 ≥ 3 次 + 无矛盾证据 | 否 |
| Pattern → Principle | 多域验证 + PromotionRuleEngine 检查 | 是（Pattern→Principle 需要审批） |
| Principle → Policy | Governance 审批 + 冲突检测 | 是（强制性） |

---

## 第四章：Knowledge 的操作契约

所有 Knowledge 操作（创建、提升、验证、降级、归档）必须：
1. 通过 KnowledgeABI 接口
2. 发射 Information 事件（INFORMATION_STATUS_CHANGED, KNOWLEDGE_PROMOTED 等）
3. 记录到 Trace（不限于 WorkingMemory）

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | 初始冻结。Knowledge = Verified + Generalizable + Stable Information (ADR-018) |
