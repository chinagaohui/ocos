# EXECUTION THEORY v1.0 (Frozen)

**状态**: ❄️ 冻结
**日期**: 2026-07-22
**所属架构层**: 概念层
**前置冻结**: Information Theory ✅, Process Theory ✅, Goal Theory ✅, Decision Theory ✅
**后续**: Cross-Theory Audit（全局一致性审计）
**上游约束**: Decision Invariant 3（Decision 是 Action 的唯一授权来源）

---

## 1. 本体定义

### 一句话定义

> **Execution 是将 Decision 承诺转化为世界状态变化的过程。**

### 核心否定（已冻结）

| 命题 | 结论 |
|------|------|
| Execution 是 Action？ | **否**。Execution 管理 Action 的整体执行。Action 是最小世界交互单位。Execution ≠ Action。 |
| Execution 是 ProcessType？ | **否**。Execution 不是认知 Process（不做推理/决策）。Execution 是过程性概念。 |
| Execution 是 Scheduler？ | **否**。Scheduler 是调度机制（什么时候执行）。Execution 是执行本身（如何执行）。 |
| Execution 是 Tool？ | **否**。Tool 是 Action 的载体。Execution 使用 Tool，但 Execution ≠ Tool。 |
| Execution 是 Engine？ | **否**。Engine 是 Plugin 容器。Execution 不特定于某个 Engine。 |

---

## 2. 三个不变量

### Invariant 1 — Execution 必须引用一个已提交的 Decision

Execution 的唯一合法输入是 `status = committed` 的 Decision。

```
Decision(status=committed)
    │
    ▼
Execution
```

**推论**:
- Execution 不接受 Goal（Goal 在 Decision 阶段已结束）
- Execution 不接受直接 Reasoning/Preference（属于 Decision 阶段）
- PolicyEngine 的 `decision_id` 检查扩展到 `decision.status == committed`

### Invariant 2 — Execution 不修改 Commitment

Execution 执行 Decision 所选方案，但 Execution 不修改 Decision 自身。

```
Execution:
    ├── 读取 Decision.selected_option ✓
    ├── 执行 Action ✓
    └── 修改 Decision.status ✗ （Decision.status 由 Decision 生命周期管理）
```

**推论**:
- Decision 的 Revoked / Superseded 由外部触发（新 Decision / 创建者撤销），非 Execution 触发
- Execution 失败时，由 Observation → Reasoning 迭代决定是否创建新 Decision（Goal Invariant 2）

### Invariant 3 — Execution 必须产生至少一个 Observation

没有 Observation，说明没有真正执行。Operation → Observation 是闭环的完整性要求。

```
Execution
    │
    ├── Action 1 → Observation 1 ✓
    ├── Action 2 → Observation 2 ✓
    └── 至少产生一个 Observation（完整闭环条件）
```

**推论**:
- 所有 Action 必须被观测（Constitution Rule 3: `ALL_INPUTS_MUST_BE_OBSERVED`）
- Execution 完成时，至少一个 Observation 被 emit 到 EventBus
- 不出 Observation 的 Execution 视为无效

---

## 3. 输入与输出

### 输入（已冻结）

Execution 的唯一规范输入：

```
Decision（已提交 / committed）
```

Execution 不接受的输入：

```
Goal             ✗（Goal 在 Decision 阶段已结束）
Reasoning Result ✗（属于 Decision 阶段）
Preference       ✗（属于 Decision 阶段）
Raw Observation  ✗（属于 Observation 层）
```

### 输出（已冻结）

Execution 的规范输出：

```
Observation(s)
```

形成完整闭环：

```
Observation → Reasoning → Decision Making → Decision → Execution → Observation
     ↑                                                        │
     └────────────────────────────────────────────────────────┘
```

---

## 4. Execution 不负责什么

| Execution 不负责 | 归属 |
|-----------------|------|
| 重新推理 | Reasoning Process（Observation 驱动） |
| 修改 Goal | Goal 生命周期管理（Agent / User） |
| 修改 Decision | Decision 生命周期管理（外部触发 Revoked / Superseded） |
| 判断执行成功 | Evaluation / Verification（读 Observation 判断） |
| 调度执行顺序 | Scheduler（什么时候执行） |
| 选择执行策略 | Execution 选择工具/参数，但不重选方案 |

Execution 唯一负责：

```
尝试兑现 Decision（Try to fulfill the commitment）
```

---

## 5. 生命周期（仅语义）

只定义 Execution 的规范状态。

```
Pending
    ↓
Running
    ├── Succeeded       （所有 Action 完成）
    ├── Failed          （Action 执行失败）
    ├── Interrupted     （外部干预暂停）
    └── Cancelled       （被取消）
```

**状态转换规则**:
- **Pending → Running**: 初始化完成，开始执行
- **Running → Succeeded**: 所有 Action 成功完成
- **Running → Failed**: 任一 Action 失败且不可恢复
- **Running → Interrupted**: 外部干预（可恢复，但 v1.0 不定义恢复语义）
- **{Pending, Running} → Cancelled**: 被明确取消
- **终止态不可逆**

**不冻结**:
- 线程模型
- Scheduler 集成
- Tool 的具体实现

---

## 6. Execution 与 Action 的关系

这是 Execution Theory 的核心关系。

```
Decision (Committed)
    │
    ▼
Execution
    │
    ├── Action 1  ←── Tool A / API A / File Write / Memory Write / ... → Observation 1
    ├── Action 2  ←── Tool B / API B / Robot Command / ...           → Observation 2
    ├── Action 3  ←── ...                                             → Observation 3
    │
    └── [Succeeded | Failed | Interrupted | Cancelled]
```

### 层级定义

| 层级 | 定义 | 例子 |
|------|------|------|
| **Execution** | 管理 Action 的整体执行过程。拥有生命周期。 | `执行地图扫描方案` |
| **Action** | 最小世界交互单位。可观测。不可中断（原子）。 | `调用 scan_api(coords)` |
| **Tool** | Action 的载体/适配器。无状态。可替换。 | `ScanAPI`, `FileWriter`, `RobotArm` |

### 已冻结

- Execution 拥有独立生命周期（§5）
- Action 是最小交互单位（原子）
- 每个 Action 必须产生 Observation（Invariant 3）
- Tool 是可替换的 Action 载体（属 Plugin 层）

### 未冻结

- Action 的数据模型（属 Execution Model 实现）
- Tool 的实现接口（属 Plugin / 集成层）
- Action 的并发/顺序策略（属 Implementation）

---

## 7. 与其他概念的关系

只定义关系语义，不定义实现。

```
Goal（规范性承诺）
    │
    ▼
Decision Making（Process）
    │
    └── produces → Decision（选择承诺）
                        │
                        ▼
                    Execution
                        │
                    ┌───┴───┐
                Action 1  Action 2 ...
                    │        │
                    ▼        ▼
                Observation  Observation
                        │        │
                        ▼        ▼
                    Information（描述性事实）
                        │
                        ▼
                    Reasoning（认知过程）
                        │
                        └──→ next Decision Making
```

---

## 8. Success/Failure

Execution 自己的成功/失败语义仅限于"承诺是否被兑现"。

```
Execution.Succeeded = 所有 Action 完成，Decision 的承诺已兑现
Execution.Failed     = 至少一个 Action 失败，承诺不可兑現
```

**已冻结**:
- Execution 的 Success = Action 序列成功完成
- Execution 的 Failure = Action 执行失败
- Execution 不判断 Goal 是否达成（属于 Evaluation）
- Execution 失败 → Agent 获取 Observation → 新的一轮 Reasoning → 可能创建新 Decision

**Agent 闭环示例**:

```
Goal: 逃离星球
    │
    ├── Decision A: 方案 A（修理飞船）
    │   │
    │   ├── Execution A: 尝试修理 → Failed（缺少零件）
    │   │
    │   └── Observation → Reasoning → Decision B: 方案 B（建造逃生舱）
    │       │
    │       ├── Execution B: 建造 → Succeeded
    │       │
    │       └── Goal: Completed ✅
    │
    Goal 不变，Decision 迭代，Execution 执行
```

---

## 9. Impact：OCOS 主认知闭环冻结

Execution Theory 冻结后，OCOS 六层核心闭环完整：

```
Goal（规范性承诺 — 世界应该变成什么）
    │
    ▼
Decision Making（Process — 认知过程）
    │
    └── produces → Decision（选择承诺 — 选定方案）
                        │
                        ▼
                    Execution（过程 — 将承诺转化为世界变化）
                        │
                    ┌───┴───┐
                Action → Observation（世界状态描述）
                                    │
                                    ▼
                                Information（描述性事实）
                                    │
                                    ▼
                                Reasoning（认知过程）
                                    │
                                    └──→ next Decision Making
```

### 六层支柱冻结状态

| 理论 | 状态 | 冻结日期 |
|------|------|---------|
| Information Theory | ❄️ 冻结 | Phase 14 |
| Process Theory | ❄️ 冻结 | Phase 15 |
| Goal Theory | ❄️ 冻结 | 2026-07-22 |
| Decision Theory | ❄️ 冻结 | 2026-07-22 |
| Execution Theory | ❄️ 冻结 | 2026-07-22 |
| Cross-Theory Audit | ⏳ 下一步 | — |

---

## 10. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | ❄️ 冻结。本体定义 + 三不变量 + 输入输出 + 不负责清单 + 生命周期 + Execution↔Action 关系 + 闭环完整 |
