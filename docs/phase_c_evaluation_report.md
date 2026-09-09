# Phase C — ER-2 Phase 4 触发清单评估报告

**日期**：2026-09-09
**前置条件**：Phase A（生产级 C 类闭环）✅ + Phase B（纵向自进化量化）✅ 全部通过
**评估对象**：ER-2 Phase 4 检查清单 5 项（C0-C4）
**最终裁决**：**NOT TRIGGERED** ⏸ — 5 项全 AND 不满足，永久维持

---

## C0 · B 类负效应统计定量 ✅ PASS

**证据来源**：`docs/ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md`（ER-2 原始决策文档）

ER-2 三代复现数据：

| 实验 | Group B (Passive Warning/Lesson) | 读取执行 |
|---|---|---|
| R4 初验 | 0/10 = 0% | 行动抑制 |
| 二代扩展 | 0/10 = 0% | 行动抑制复现 |
| Phase 3 终验 | 0/10 = 0% | 行动抑制复现 |

**结论**：B 类 Passive Warning/Lesson 三代复现 0/10，行动抑制可复现副作用。Phase A 正确跳过 B 类，全部走 C 类生产路径。

---

## C1 · 独立可枚举 BehaviorCandidate 对象存在？ ❌ FAIL

**ER-2 要求**：Candidate 层必须有独立于 Lesson/Policy 的 BehaviorCandidate 数据类，可被枚举、持久化。

**代码级证据**：

```bash
$ grep -rn "class.*BehaviorCandidate\|class.*ActionCandidate" ocos/ --include="*.py"
# (零结果 — 不存在 BehaviorCandidate 类)
```

现有 Candidate 类（全是其他层概念）：
- `ExtensionCandidate` — 扩展插件发现候选（`extension/discovery_engine.py:26`）
- `InteractionCandidate` — 交互调度队列（`interaction/interaction_scheduler.py:39-41`）

**不匹配**：ExtensionCandidate 是插件发现层概念，InteractionCandidate 是交互调度队列——都不是 Action 层的 BehaviorCandidate（ER-2 定义为"被 DecisionBridge 消费的候选动作实体"）。

**裁定**：FAIL — 不存在符合 ER-2 Phase 4 定义的 BehaviorCandidate 类。

---

## C2 · Candidate 有独立产生路径与持久化？ ❌ FAIL

**ER-2 要求**：Candidate 必须有独立于 Lesson 合成的产生路径（如 `generate_candidate()`），且有独立的持久化表/Store。

**代码级证据**：

```bash
$ grep -rn "generate_candidate\|Candidate.*factory\|Candidate.*producer" ocos/ --include="*.py"
# (零结果 — 无独立产生路径)

$ grep -rn "CREATE TABLE.*candidate\|candidate.*table\|Candidate.*store" ocos/ --include="*.py"
# (零结果 — 无独立持久化)
```

Lesson 合成路径存在（`LessonsSynthesizer._extract_failure_pattern`），但 Candidate 合成路径**不存在**。Candidate 持久化表**不存在**（所有学习产物都是 `source='lesson'` 的 Episode）。

**裁定**：FAIL — Candidate 无独立产生路径，无独立持久化。

---

## C3 · Candidate 被 DecisionBridge 输入侧消费？ ❌ FAIL

**ER-2 要求**：DecisionBridge 在决策链输入端（`_failure_prior_hint` / `_handler_fs_read` 等）消费 Candidate 实体，而非 Lesson。

**代码级证据**：

```bash
$ grep -n "candidate\|Candidate" ocos/execution/bridge.py
927: path_candidates = sorted(...)    # ← bridge 内部路径匹配局部变量
932: if path_candidates:
933:     return self._exec_fs("stat", path_candidates[0])
```

唯一的 "candidate" 出现在 `_exec_fs_stat_helper()` 的路径匹配临时变量——**不是** DecisionBridge 输入端消费的持久化实体。

DecisionBridge 当前输入侧消费的**全部是 Lesson**（via `_failure_prior_hint` → `episodes(source='lesson')` + `learning.jsonl(lesson_prior_injected)`）。

```python
# bridge.py 真实消费路径（Phase A3 动态增强后）:
cause_to_procedure(cause, goal_pattern) → 读取 learning.jsonl lesson_prior_injected
# 完全没有 Candidate 消费路径
```

**裁定**：FAIL — DecisionBridge 无 Candidate 消费路径，全部消费 Lesson。

---

## C4 · 消费行为造成稳定可测差异（C vs D）？ ❌ FAIL

**ER-2 要求**：Candidate 层被消费后，必须在行为上产生可测差异（如执行率、失败率的统计显著变化）。

**间接证据**（ER-2 原始数据）：

ER-2 Phase 3 终验 Group D（Explicit Candidate Identity）= 5/10，C（Executable Procedure）= 6/10，差 1/10 = **噪声级**。

无 Candidate 的消费路径（C3 FAIL）自然不可能有任何行为差异。

**裁定**：FAIL — Candidate 无消费路径（C3 FAIL），且 ER-2 实测 D=5 vs C=6 差 1/10 噪声级。

---

## 最终裁决：NOT TRIGGERED ⏸

| 检查项 | 裁定 | 证据 |
|---|---|---|
| C0 · B 类负效应定量 | ✅ PASS | ER-2 三代复现 B=0/10 |
| C1 · BehaviorCandidate 类存在 | ❌ FAIL | grep 零结果 |
| C2 · 独立产生+持久化 | ❌ FAIL | grep 零结果 |
| C3 · Bridge 消费 Candidate | ❌ FAIL | bridge.py 仅 lesson 消费 |
| C4 · 可测行为差异 | ❌ FAIL | C3 FAIL + ER-2 D=5/C=6 噪声级 |

**全 AND 条件**：5 项中仅 C0 PASS，C1-C4 全部 FAIL → **不满足**。

**永久维持 ⏸**：路线图明确规定"任一未通过 → 永久维持 NOT TRIGGERED"。

---

## 架构结论

Phase A 的 C 类 Executable Procedure 已经是 OCOS 学习闭环的**最有效表达形式**（ER-2 C=6/10 vs B=0/10 vs D=5/10）。

Candidate 层（BehaviorCandidate 类 + 独立产生路径 + Bridge 消费）属于"为架构而架构"——在 ER-2 实测中它没有提供独立行为增量（D=5 vs C=6 差 1/10 噪声级），却会：
- 新增 BehaviorCandidate 类（违反"15 个 Engine 已足够"约束）
- 新增 Candidate 持久化表（零新表原则）
- 改写 bridge 消费路径（Runtime 权限变更）
- 引入 Phase A 已避开的生产复杂度

**最终架构保持**：Lesson（Executable Procedure 格式）→ Bridge 直接消费，无 Candidate 层。

---

## 禁止项（路线图 Phase C 明确禁止）

- ❌ 不创建 BehaviorCandidate / ActionCandidate 类
- ❌ 不改 DecisionBridge 权限
- ❌ 不绕 ER-2 预注册的闸门语义
- ❌ 不创建 Candidate 持久化表
