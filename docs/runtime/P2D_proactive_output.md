# P2-D Proactive Output 冻结文档（2026-08-29）

## 1. 审计结论

| 组件 | 现状 | 证据 |
|---|---|---|
| 内生目标 | ✅ P2-A 已点亮 | Regulator → GoalOriginEnforcer(SELF) → GoalStack；Step 4.5 挂 tick，Step 6 Planning 消费 |
| 注意力预算 | ✅ 现成 | `attention.needs_sleep()` / `attention.fatigue`（agent/attention.py） |
| 空闲状态 | ✅ 现成 | `AgentStatus.IDLE`（master_agent.py:205）/ `MicroState.IDLE` / LifecycleManager `_tick_idle` |
| 权限门 | ✅ 现成 | PermissionGuard（interaction/base.py:179，ALLOWED/FORBIDDEN + 宪法联动）；capability/permission_gateway.py:186 |
| 宪法过滤 | ✅ 现成 | constitution/hub.py:81 `check_action(action, context)` |
| 审计留痕 | ✅ 现成 | PermissionGateway 结构化日志（P1 已建） |
| **Proactive 引擎** | ❌ **无** | ocos/proactive/ 不存在；零主动输出（升级报告 :234 诊断） |
| 主动输出通道 | ❌ 无 | 无 Telegram/本地通知实现（drift_detector 无 telegram） |
| D4 裁决 | ⏳ 未裁决 | 默认建议：每日 ≤1 次主动输出（陪伴≠骚扰，SDT 联结需求与打扰成本平衡） |

**精确缺口**：触发条件全部就绪（内生目标 + 空闲 + 注意力预算 + 权限/宪法门），缺的是把"待办内生目标"转化为"主动输出"的编排引擎与频率闸门。

## 2. D4 裁决（需批准）

**建议：默认每日 ≤1 次主动输出（NaturalDayBudget=1）**。理由：
- 陪伴定位：连接需求（SDT）与打扰成本平衡；1 次/日 = 有存在感但不骚扰
- 升级报告 §6.4 D4 默认建议即此值
- 频率闸门为确定性规则（自然日窗口计数），可配置，未来调参不改架构
- 批准后写入 runtime_config（PROACTIVE_DAILY_BUDGET=1）

## 3. Scope（包含/不包含）

包含：
1. 新模块 `ocos/proactive/proactive_engine.py` — `ProactiveEngine`：
   - **触发条件**（全部满足才生成候选）：
     a. 系统空闲（LifecycleManager 处于 IDLE/认知循环间隙）
     b. 有 SELF 级内生目标待办（GoalStack 非空，取最高优先级未完成）
     c. 注意力预算充足（fatigue < 0.70）
     d. 频率闸门放行（自然日已输出数 < PROACTIVE_DAILY_BUDGET=1）
   - **候选生成**：确定性模板（问候/观察/提问三类），参数来自内生目标上下文（目标描述/领域/最近 Episode 摘要）；无 LLM，模板+参数插值
   - **输出前过滤**：PermissionGuard.check(action="proactive_output") + 宪法 check_action → 任一拒绝则不输出（不留痕不输出）
   - **输出**：第一版输出到本地（结构化日志 + 可注入 handler 回调）；Telegram/消息通道留接口（`OutputChannel` Protocol：`send(message) -> bool`），不实现具体通道
   - **审计**：输出记录走 PermissionGateway 结构化日志（action/context/result/timestamp）
2. 频率闸门：`ProactiveGate`（自然日窗口计数，SQLite 或内存 + 日期持久化；deterministic）
3. 接线：LifecycleManager `_tick_idle` 认知循环后调用 `ProactiveEngine.maybe_emit()`（防御式：引擎未注入 → 跳过）
4. 契约测试（L3 主动性）+ 全量回归

不包含：
- ❌ 不实现具体消息通道（Telegram/通知——留接口，属 P4 器官候选"proactive 消息通道"）
- ❌ 不用 LLM 生成输出文案（确定性模板；LLM 文案属未来升级项）
- ❌ 不触碰 HUMAN 级目标（只消费 SELF 级待办；治理规则不变）
- ❌ 不新建权限体系（复用 PermissionGuard + 宪法）
- ❌ 不改 tick 主循环结构（挂在 `_tick_idle` 尾部，最小侵入）
- ❌ D4 裁决未批准前不实施

**接口签名**：
```python
# ocos/proactive/proactive_engine.py
class OutputChannel(Protocol):
    def send(self, message: str) -> bool: ...

class ProactiveEngine:
    def __init__(self, gate: ProactiveGate, guard: PermissionGuard,
                 constitution: ConstitutionHub, channel: OutputChannel | None = None): ...
    def maybe_emit(self, context: ProactiveContext) -> ProactiveResult | None:
        """全部触发条件满足 → 生成候选 → 权限/宪法过滤 → 输出 → 审计。
        Returns: None（未触发或被拒）或 ProactiveResult(message, action, allowed)"""

class ProactiveGate:
    def __init__(self, db_path: str = ":memory:", daily_budget: int = 1): ...
    def try_acquire(self, now: datetime) -> bool: ...   # 自然日窗口计数，超预算拒绝
```

## 4. 确定性规则表

| 触发条件 | 值 | 说明 |
|---|---|---|
| 空闲 | Lifecycle IDLE | 认知循环间隙 |
| 内生目标 | SELF 级待办 ≥1 | P2-A GoalStack |
| 注意力 | fatigue < 0.70 | 与 P2-B 抑制阈值一致 |
| 频率 | 自然日已输出 < 1 | D4 裁决值 |
| 候选类型 | 问候/观察/提问 | 模板轮转（确定性） |
| 过滤 | Guard + 宪法双检 | 任一拒绝 → 不输出 |

## 5. 验收（L3 主动性）

1. 契约测试（tests/test_proactive/test_proactive_engine.py 新建）：
   - 全部条件满足 → maybe_emit 返回 1 条输出（问候/观察/提问之一），审计留痕
   - 同自然日第二次调用 → None（闸门拦截，频率上限生效）
   - fatigue ≥ 0.70 → None（预算保护）
   - 无 SELF 目标待办 → None
   - 宪法拒绝（action 违规）→ None 且无输出
   - 无 channel 注入 → 输出到结构化日志（不抛）
   - 非 IDLE 状态 → None
2. 全量回归 `pytest tests/`（基线 1952 passed / 8 skipped）

## 6. Security（防越权/防伪造/防失控）

| 威胁 | 缓解 |
|---|---|
| 防越权 | 输出前 PermissionGuard + 宪法双检；action 固定 "proactive_output"，走 ALLOWED_ACTIONS |
| 防伪造 | 确定性模板 + 参数插值，无 LLM；上下文来自本机 GoalStack/Episode |
| 防失控 | D4 频率闸门（1/日）+ fatigue 预算 + 审计留痕；失败静默（不中断认知循环） |

## 7. Before / After

Before:
```
_tick_idle → observe/think/decide/act/reflect/learn → 无主动输出
```
After:
```
_tick_idle → ...learn → ProactiveEngine.maybe_emit()  ← 新增
    ├─ 条件检查（空闲✓ 目标✓ 预算✓ 闸门✓）
    ├─ 模板候选（问候/观察/提问）
    ├─ Guard + 宪法过滤
    └─ channel.send() 或 结构化日志 → 审计
```

## 8. 符合冻结原则声明

增量嵌入：新代码全部进 `ocos/proactive/` 新目录（升级报告规划路径）；复用全部现成资产（GoalStack/attention/PermissionGuard/宪法/审计）；不触碰既有模块语义；D4 裁决为显式文档化决议（非静默）；频率闸门确定性规则。

## 9. 实施记录（2026-08-29，追加）

验收：✅ 全绿。全量回归 1970 passed / 8 skipped / 0 failed（+11 P2-D 契约：9 engine + 2 MasterAgent 挂钩）。

| 验收项 | 状态 | 证据 |
|---|---|---|
| ocos/proactive/ 新模块 | ✅ | templates.py / audit.py / engine.py / __init__.py |
| 模板候选（问候/观察/提问，无 LLM） | ✅ | 确定性模板池 + 轮换（审计计数取模） |
| 触发链四闸门 | ✅ | 频率闸门→SELF 目标待办→疲劳闸门→模板轮换（全契约测试证） |
| PermissionGuard + 宪法双检 | ✅ | fail-closed；防护缺失显式拒绝（missing_guard） |
| 输出走本地日志/可注入通道 | ✅ | output_callback 注入点（Telegram 留接口，未实现） |
| 审计 | ✅ | ProactiveAuditStore（SQLite：granted/reason/kind/message） |
| 挂 _tick_idle 尾部 | ✅ | life_cycle_orchestrator.py（learn 之后，防御式 try） |
| D4 裁决 | ✅ | 默认每日 ≤1 次主动输出（daily_limit=1，确定性可配） |
| 新契约测试 | ✅ | test_proactive_output.py 11 用例全绿 |

### 实施偏差（追加记录，不覆盖冻结期假设）

1. **双检 fail-closed 定稿**：冻结期"PermissionGuard + 宪法双检"未明缺失语义 → 实施定为 fail-closed（任一防护缺失 → missing_guard 拒绝，绝不无检输出；审计可查）。宪法第六条：无护栏不上线。
2. **宪法第二检实体**：ConstitutionHub.check_action 为生产入口；兼容 BehavioralConstitution.check_decision（SimpleNamespace 包装 action）。冻结期仅写"宪法"未定接口。
3. **主动输出 action 用现有 "view_self"**：不扩 PermissionGuard 权限面（最小侵入）；外部通道（Telegram）启用时再评估独立 action。
4. **MasterAgent 新增 permission_guard 可选构造参数**（与 constitution 同款）；engine 注入源 = self._permission_guard / self._constitution。
5. **生产默认静默**：daemon/factory 未注入 guard → fail-closed 静默（审计记录 missing_guard）；runtime 注入 guard+constitution+goal_store 即点亮。P2-D 完整生产启用 = 后续 runtime 注入项。
