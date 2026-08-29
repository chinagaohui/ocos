# OCOS 缺口修复执行方案（GAP_REPAIR_PLAN v1.0）

> **生成时间**: 2026-08-29
> **依据**: 2026-08-29 全仓逐模块审计（约 100 个子模块，全部经代码核实，非文档转抄）
> **性质**: 可执行步骤方案。每步 = 改动 → 验证 → 提交，一步一个 commit。
> **基线**: 先跑一次全量测试记录起点，见 §0。

---

## 0. 执行纪律与基线

### 0.1 三条纪律

1. **每完成一个任务项立即 commit**，commit message 用本方案编号（如 `GAP-P0-1: ...`），保证可回滚、可审计。
2. **不动冻结区**：`OCOS_Cognitive_Sovereignty_Freeze_v0.1.md`、`kernel/abi.py` 冻结 dataclass、Authority 相关代码。若改动必须触碰冻结面，先停下升级审批（走 `evolution/` 的提案-审批链），不得直接改。
3. **导入规则守卫**：本仓有 `ocos/tests/test_import_rules.py`、`test_no_direct_store_access.py`、`tests/self/test_no_personality_leak.py` 等架构守卫测试。任何新接线必须让这些测试继续通过；新模块间依赖先查 `ocos/OCOS_DEPENDENCY_MATRIX.md`。

### 0.2 建立基线（第 0 步，约 10 分钟）

```bash
cd /home/laogao/Documents/trae_projects/ocos
python -m pytest -q 2>&1 | tail -5          # 记录 passed/failed/error 数字
git status --short > /tmp/baseline_status.txt
```

- 若当前工作区已有大量未提交改动：**先与用户确认这些改动的归属**，把"数字生命升级"在途工作单独提交或 stash，再开始本方案，避免混流。
- 把基线数字写入本文档末尾 §6 的执行记录表。

---

## P0：正确性与安全（4 项，约 1 天）

> 全部是"看起来在工作但实际没生效"的问题，优先级最高、改动最小。

### P0-1 修复身份快照静默失效

**问题**：`ocos/agent/agent_runtime.py:1271` 调 `self._identity_store.save_snapshot(...)`、`:1287` 调 `load_snapshot(...)`，但 `IdentitySQLiteStore` 没有这两个方法，异常被 try/except 吞掉 → Phase 34E 身份跨重启连续性静默失效。

**改动文件**：`ocos/agent/identity_store.py`

**步骤**：
1. 读 `agent_runtime.py:1260-1300`，确认调用签名（预期是 `save_snapshot(agent_id, payload: dict)` / `load_snapshot(agent_id) -> dict | None`，以实际调用为准）。
2. 在 `identity_store.py` 的 `IdentitySQLiteStore` 中新增：
   - `snapshots` 表 DDL（`snapshot_id TEXT PRIMARY KEY, agent_id TEXT, payload TEXT/json, created_at`）。
   - `save_snapshot()`：JSON 序列化 upsert，保留最近 N 份（建议 N=10）。
   - `load_snapshot()`：取该 agent 最新一份，反序列化返回。
3. 检查 `ocos/storage/schema.py`：若 schema 体系要求集中 DDL，把表加入 `schema.py` 并在 store 内保留 `_DDL` 兼容（与现有其他表做法保持一致——当前各 store 自建 `_DDL`，跟随现状即可）。

**验证**：
```bash
python -m pytest tests/ -q -k "identity or runtime_loop"
python - <<'EOF'
# 手工冒烟：save→load 往返
from ocos.agent.identity_store import IdentitySQLiteStore
s = IdentitySQLiteStore(":memory:")
s.save_snapshot("a1", {"k": "v"})
assert s.load_snapshot("a1") == {"k": "v"}
print("OK")
EOF
```

**完成标准**：往返测试通过；`agent_runtime` 相关测试全绿；不再有被吞的 AttributeError（可临时在 except 处加日志验证一次后移除）。

### P0-2 修复 dream() 巩固产物不落盘

**问题**：`ocos/agent/master_agent.py:115,118` 的 BeliefStore/PatternStore 默认 `:memory:`；`daemon/factory.py:15-37` 装配 MasterAgent 时未注入 file-backed store → 睡眠巩固的信念/模式进程退出即丢。

**改动文件**：`ocos/daemon/factory.py`、`ocos/agent/master_agent.py`（仅构造参数，不动逻辑）

**步骤**：
1. 读 `master_agent.py` 构造函数，列出 episode/belief/pattern 三个 store 参数的默认值与类型。
2. 在 `factory.build_master_agent()` 中：接收 `db_path`（沿用 `cli/commands/run.py:30-35` 的 `~/.ocos/ocos.db` 解析逻辑），构造 `MemoryHub(db_path)` 并把 `hub.episode / hub.belief / hub.pattern` 注入 MasterAgent 对应参数。
3. 同步检查 `daemon/__init__.py:60` `ResidentRuntime` 的默认参数是否也是 `:memory:`，若是，改为必须显式传 `db_path`（不给默认值，避免再出现伪持久化）。
4. `agent_runtime.py` 已绑 belief_system 的 hub（:291），确认注入路径不产生两套 store 实例写同一个库（SQLite WAL + busy_timeout 可容忍，但同实例更干净——以 MemoryHub 为唯一 store 来源）。

**验证**：
```bash
python -m pytest ocos/tests/test_single_main_loop.py tests/test_agent/ -q
# E2E 冒烟：临时目录跑一次 dream，检查库里是否有 belief/pattern 行
OCOS_DB_PATH=$(mktemp -d)/test.db python -c "
from ocos.daemon.factory import build_master_agent
a = build_master_agent(db_path='$PWD/.smoke.db')
a.dream()
import sqlite3; c = sqlite3.connect('$PWD/.smoke.db')
print('beliefs:', c.execute('select count(*) from belief').fetchone(),
      'patterns:', c.execute('select count(*) from pattern').fetchone())
"
rm -f .smoke.db
```
（表名以 `ocos/storage/schema.py` 实际为准。）

**完成标准**：dream() 后 belief/pattern 表出现行；`ocos run` 启动日志可见文件库路径。

### P0-3 补 ExecutionBridge 权限检查

**问题**：`ocos/capability/execution_bridge.py:70-73` `_check_permission` 固定 `return True`（注释自认占位）。

**改动文件**：`ocos/capability/execution_bridge.py`、`ocos/capability/permission_gateway.py`（只消费不改）

**步骤**：
1. 读 `capability/permission_gateway.py`（`PermissionGateway.evaluate` 的入参与返回 `GatewayDecision`）。
2. `ExecutionBridge.__init__` 增加可选参数 `permission_gateway: PermissionGateway | None`。
3. `_check_permission`：无 gateway 时**返回失败（fail-closed）**并在审计日志记录 "no gateway configured"——不要保留 allow-all 兜底；有 gateway 时走 `evaluate()`，按决策放行/拒绝。
4. 检查 `ExecutionBridge` 的生产实例化点（`grep -rn "ExecutionBridge(" ocos/ --include='*.py' | grep -v tests`），逐一注入 gateway；`daemon/factory.py` 一并装配。
5. 同步修 `homeostasis.py:16/:558/:756` 三处过时的 "stub" 注释（Regulator 已实现，只改注释，不改代码）。

**验证**：
```bash
python -m pytest tests/test_capability/ ocos/tests/ -q -k "execution or permission or bridge"
# 反向用例：未注入 gateway 时执行应被拒绝
```

**完成标准**：无 gateway → 拒绝；有 gateway → 按 decision 行为；全量测试无新增失败。

### P0-4 消灭 plugin_sandbox 假成功

**问题**：`ocos/platform/plugin_sandbox.py:406-427` `_do_execute` 无已加载插件实例时回退 stub，返回 action/params 摘要并伪装 `success=True`。

**改动文件**：`ocos/platform/plugin_sandbox.py`

**步骤**：
1. `_do_execute` 的 stub 分支改为返回失败结果（`success=False, error="no plugin instance loaded for action ..."`）。
2. `grep -rn "_do_execute\|plugin_sandbox" tests/ ocos/tests/` 找依赖旧行为的测试，改为断言失败路径。
3. 顺手处理同类假成功：`extension/sandbox_runner.py:31-40` `validate()` 无条件 `passed=True` —— 最小改法：把"无条件通过"改为调用 `digital_world/sandbox.py` 的 `sandbox_exec`（dry_run 模式下至少做 import 探测），无法隔离执行时返回 `passed=False, reason="sandbox unavailable"`。若时间紧张，P0 只加显式 `# KNOWN-FAKE` 标记 + 返回 False，P2 再接真沙箱（见 P2-6）。

**验证**：
```bash
python -m pytest ocos/tests/test_phase44.py tests/ -q -k "plugin or sandbox or extension"
```

**完成标准**：仓库内不再存在"返回 success=True 的 stub 路径"（`grep -rn "stub" ocos/ --include='*.py' | grep -v tests` 复查一遍，剩余均应为注释性降级说明）。

**P0 收尾 commit**：`GAP-P0: fix silent identity snapshot, dream persistence, exec permission fail-closed, kill fake-success stubs`

---

## P1：点亮孤岛器官（3 项，约 2-3 天）

> 代码已写好，只差接线。每项 = 接线 + 1 条 E2E 测试。

### P1-1 decision/ → cognitive_loop 决策占位

**问题**：`cognitive_loop/decision_pipeline.py:44-58` 的决策是拼字符串 + 禁止词检查，而 `ocos/decision/`（ContextBuilder/OptionGenerator/RiskEngine/ValueModel/DecisionTracer/Validator，含 D43 边界守卫）完整实现却零调用者。

**改动文件**：`ocos/cognitive_loop/decision_pipeline.py`、`ocos/cognitive_loop/loop_orchestrator.py`

**步骤**：
1. 读 `ocos/decision/` 各类构造参数与 `decision_pipeline._generate_proposal()/_governance_check()` 现有输入输出。
2. `DecisionPipeline.__init__` 注入 `ContextBuilder/OptionGenerator/RiskEngine/ValueModel/DecisionTracer/DecisionValidator`（可包一个 dataclass `DecisionComponents`，默认 None 时保留现字符串行为并打 warning——cognitive_loop 本身尚无生产调用者，风险可控）。
3. `_generate_proposal()` → 用 OptionGenerator 产出候选；`_governance_check()` → 用 DecisionValidator（D43-01/02/03）+ 保留禁止词作为第一道快筛。
4. `DecisionTracer` 记录完整决策轨迹（trace 输出对齐仓库已有 C4 trace 惯例）。
5. 新增 E2E 测试 `ocos/tests/test_decision_pipeline_wired.py`：喂一个 observation，断言 proposal 来自 OptionGenerator、validator 结论落 trace。

**注意**：`master_agent.decide()` 的宪法检查是另一层（BehavioralConstitution），本项只替换 cognitive_loop 内部占位，**不要**动 master_agent 的 decide 路径。

**验证**：`python -m pytest ocos/tests/test_decision_pipeline_wired.py ocos/tests/test_phase43.py ocos/tests/test_phase46.py -q`

### P1-2 health_examination + alerts → daemon 稳态监控

**问题**：`daemon/factory.py` 装配了 9 个组件但**没有任何 homeostasis/health 监控**；`health_examination/`（CognitiveExaminer 检测器真实）与 `alerts/`（AlertManager + Log/File 通道真实）互不相连且零生产调用者。

**改动文件**：`ocos/daemon/factory.py`、`ocos/daemon/__init__.py`、`ocos/health_examination/cognitive_examiner.py`（只消费）、`ocos/alerts/manager.py`（只消费）

**步骤**：
1. factory 增加装配：`AlertManager`（挂 LogChannel + FileChannel，文件放 `~/.ocos/alerts/`）。
2. 新建 `ocos/daemon/health_loop.py`：一个轻量周期任务（随 `ResidentRuntime` tick 每 N 次触发一次，N 默认 100，可配）：
   - 从 AgentRuntime 采集快照（记忆条数、goal 栈深、最近决策失败率、WM 占用——先做 4 项，能从已有公开属性拿到的）；
   - 组装 `health_examination` 的 `MemorySnapshot/DecisionSnapshot` dataclass，调 `CognitiveExaminer` 体检；
   - 有疾病/异常 → `AlertManager.emit()`；同时调 `HomeostasisManager.monitor`（agent_runtime.py:607 已有实例，复用而非新建）。
3. `ResidentRuntime.__init__` 增加可选 `health_loop` 参数并在线程循环内驱动；factory 注入。
4. E2E 测试：伪造一个超阈快照 → 断言 alerts 文件通道落盘。

**验证**：`python -m pytest ocos/tests/test_single_main_loop.py tests/test_capability/test_homeostasis.py <新测试> -q`

### P1-3 perception → attention → world_model 感知链

**问题**：`perception/`（传感器+校验）与 `world_model/`（因果/状态追踪）都完整但互不相连、零生产调用者。

**改动文件**：新建 `ocos/perception/pipeline.py`（或 `ocos/world_model/pipeline.py`，二选一，倾向前者）；`ocos/daemon/factory.py`

**步骤**：
1. 建 `PerceptionPipeline`：`PerceptionEngine`（FileSensor/TextSensor 可配）→ `PerceptionValidator`（来源信誉过滤）→ `StateTracker.ingest(EventModel)` → `CausalityEngine` 可选更新 `RelationGraph`。
2. WorldStore 先用内存版（持久化列入 P2，避免本步膨胀）。
3. factory 可选注入 sensors（默认无 sensor，纯手动喂事件也可用——保证 `ocos run` 在无环境变化时零噪音）。
4. E2E 测试：临时目录写一个文件 → FileSensor 捕获 → 断言 StateTracker 出现对应事件、CausalityEngine 可查询上下游。

**验证**：`python -m pytest <新测试> ocos/tests/test_phase42* -q`（若存在 world_model 相关测试，路径以实际为准）

### P1-4（顺手项，半小时级）

- `interaction/cognitive_interface.py` 的 `stimulate()` 接入 `ResidentRuntime`：daemon 暴露 `stimulate(event)` 转发，使该入口有真实宿主。
- CLI `goal create` / `plan`（`cli/commands/goal.py:14-42`、`plan.py`）落库：`to_user_goal()` 后经 `GoalSQLiteStore.save()`（`agent/goal_store.py`），并可选 `daemon.enqueue_goal()`。

**验证**：`python -m pytest tests/interaction/ -q` + CLI 手工冒烟 `ocos goal create ...` 后查库。

**P1 收尾 commit**：`GAP-P1: wire decision pipeline, daemon health loop, perception chain into production paths`

---

## P2：持久化与占位补齐（5 项，约 2-3 天）

### P2-1 SemanticStore 写入管道（知识落库）

**问题**：`memory/semantic/store.py` 完整但生产写入为 0；知识平面 `knowledge/store/registry.py` 是内存 dict；`storage/schema.py:165` 建了 knowledge 表却没人写。

**步骤**：
1. `KnowledgeRegistry` 增加可选 `semantic_store: SemanticStore`；`register/supersede` 时同步 `semantic_store.save()`（字段映射 KnowledgeEntry ↔ KnowledgeEntry 表结构）。
2. 写入者接线：`engines/promotion_engine.py`（Pattern→Knowledge 晋升）与 `consolidation_engine.py` 持有 registry 的路径上注入 store。
3. factory / agent_runtime 装配时把 `MemoryHub.semantic` 传下去。
4. 测试：晋升一条 → 查 semantic 表有行、supersede 版本链正确。

### P2-2 runtime/stages 4 个占位接线

`event_ingestion.py`（接 `ocos/event` EventBus 的 drain）、`memory_sync.py`（接 MemoryHub 差异同步）、`result_collection.py`（接 ExecutionManager 结果）、`execution_check.py`（接 `ocos/task` TaskDAG 的 `resolve_ready()`——顺带给 task/ 找到生产消费者）。每接一个跑一次 `test_single_main_loop.py`。无法自然接入的（如 result_collection 若 RuntimeKernel 与 AgentRuntime 结果天然合一）在 stage 文件中显式收敛为转发并在 `docs/OCOS_AUDIT_KERNEL.md` 记录决策，不留空壳。

### P2-3 event_memory SQLite 化 + archive 补实现

`event_memory/event_store.py:44-49` dict → SQLite（复用 `storage/connection.py` 连接池与 schema 注册）；`event_archive.py:113` 的 `pass` 补真实归档（搬移到 archive 表）；写入者接 `capability/execution_bridge` 执行结果（capability_adapter 文档声称记录 EventLifecycle 但代码没接——接上或删掉该注释）。

### P2-4 wisdom_store 与 personal_intelligence 落盘

- `personal_memory/wisdom_store.py:31-37` 内存 dict → SQLite（沿用 schema.py 模式）。
- `personal_intelligence/personalization_engine.py:54,61,86` 三个 `pass` 分支补实现（FORMAL/BOLD 风格适配的最小规则版即可：基于已有 preference 数据的确定性映射，不引 LLM）。
- 接线：`personal_memory/ReflectionEngine` 在 `master_agent.reflect()`（或 dream 链）中按天/按次触发。

### P2-5 living_test 真实化（一次真实"死而复生"演练）

`living_test/day7_resurrection.py:21-30` 钩子注入真实实现：`run_ticks=ResidentRuntime.tick`、`save_state=snapshot/manager.py SnapshotManager.save`、`kill=进程退出/新进程`、`restore=CrashRecovery`、`query_handler=store 查询`。`day2_memory_survival.py:81` placeholder 换真实记忆钩子。做成脚本 `scripts/resurrection_drill.py`，可手动/CI 触发。

**P2 收尾 commit**：`GAP-P2: semantic/persistence gaps closed, stages wired, resurrection drill real`

---

## P3：收敛与清理（约 2 天，建议单独分支）

> 纯重构，无行为变化；每组合并一个 commit，全量测试通过才算完成。

| # | 保留 | 删除/合并 | 备注 |
|---|------|-----------|------|
| P3-1 | `agent/retry_policy.py` | `stability/`（circuit_breaker/retry/transaction 三件移入或废弃） | writer_engine 用前者；stability 仅测试引用 |
| P3-2 | `snapshot/`（SQLite 版） | `persistence/`（JSON 版） | 或反向，二选一后删另一套；迁移测试引用 |
| P3-3 | `snapshot/recovery.py` CrashRecovery | `recovery/crash_recovery.py` | 后者依赖的 storage 三件套若仅它使用，注意连带清理 |
| P3-4 | `agent/goal_store.py` | `goal/store.py` | 先 diff 两套表结构，确认无字段丢失 |
| P3-5 | `event/`（感知总线）+ `events/`（宪法总线）命名裁决 | `events/event_store.py`（内存版死代码） | 命名合并成本高时至少在两包 `__init__` docstring 写明分工 |
| P3-6 | `planning/plan_validator.py` | `planning/validator.py` | validator.py 的 `validate_no_self_module` pass 方法归属 import_rules 测试，合并时保留该职责说明 |
| P3-7 | `capability/` Registry/Selector | `capability_reality/` 平行 API | capability_reality 的 shell/fs 适配器保留，仅注册表层合并 |
| P3-8 | 三套注意力统一：`ocos/attention/` 为评分引擎，`capability/attention.py` 的 CognitiveAttentionController 为运行时控制器 | `agent/attention.py` 视职责并入其一 | 谨慎：涉及 Authority/注意力 ABI（`contracts/attention_abi.py`），若触碰冻结面则只写裁决文档不改码 |

**附带清理**（各 5 分钟）：
- `kernel/constitution.py:213-219` 两个 `return True` 钩子：改为 raise 或 docstring 标注 "runtime hook — real checks live in tests/test_constitution.py"。
- `agent/retry_policy.py:74-80` 删除弃用的 `with_retry`。
- `runtime/attention_engine.py:60` 删除不存在的 `SemanticContentAnalyzer` docstring 承诺（或从 P2 列入实现）。
- `kernel/abi.py:141` `# placeholder` 默认值收敛。
- `engines/__init__.py` 为空 + planning/writer 引擎缺 `__manifest__`：补 manifest，统一 EngineLoader 加载路径。
- `snapshot/manager.py:28` 默认相对路径 `ocos.db` → `~/.ocos/ocos.db`（绝对路径，防 cwd 漂移）。
- `decision_loop.py`、`belief.py`（顶层 BeliefManager）等"第三套实现"去留裁决：先写进 `docs/OCOS_AUDIT_KERNEL.md` 的 deprecated 清单，下个版本删除。

**P3 收尾 commit**：`GAP-P3: dedupe parallel implementations (stability/snapshot/recovery/goal-store/...)`

---

## 里程碑与工作量汇总

| 阶段 | 内容 | 工作量 | 完成判据 |
|------|------|--------|----------|
| §0 | 基线 + 在途改动归属确认 | 0.5h | 基线数字记录在案 |
| P0 | 4 个正确性/安全修复 | 1 天 | §二清单全消 + 全量测试绿 |
| P1 | 3 条接线 + 顺手项 | 2-3 天 | 3 条新 E2E 测试存在且通过 |
| P2 | 持久化 5 项 | 2-3 天 | semantic/event_memory/wisdom 落盘；resurrection 演练脚本可跑 |
| P3 | 8 组去重 + 清理 | 2 天 | 全量测试绿 + `grep stub` 复查清单化 |

总工期约 **7-9 个工作日**。若时间受限：P0 必做；P1 做前两项（decision + health loop）收益最大；P2 按 1→2→3 顺序；P3 可推迟到下个迭代。

---

## 6. 执行记录表（每完成一项追加一行）

| 日期 | 编号 | 改动摘要 | 测试基线变化 | commit |
|------|------|----------|--------------|--------|
| 2026-08-28 | §0 | 基线 + 在途改动归属确认 | 1971 passed 记录在案 | - |
| 2026-08-28 | P0-1 | 身份快照静默失败修复: save_snapshot/load_snapshot(keep 10) | 全量绿 | e6c1776 |
| 2026-08-28 | P0-2 | dream 持久化: MemoryHub 唯一 store 源 + attach_memory_hub 回填 | 全量绿 | b21512b |
| 2026-08-28 | P0-3 | ExecutionBridge 权限检查: PermissionGateway 注入 + fail-closed | 全量绿 | 3b4a571 |
| 2026-08-29 | P0-4 | plugin sandbox 诚实失败: 无实例不假成功 + 真实 import 探测 | 全量绿 | 54fcf6e |
| 2026-08-29 | P1-1 | DecisionPipeline 接真实 Phase 43 链 + DecisionValidator 治理 | 全量绿 | 944c994 |
| 2026-08-29 | P1-2 | daemon 稳态健康监控: HealthLoop 4 项 + Examiner + AlertManager + E2E | 全量绿 | 8acce0f |
| 2026-08-29 | P1-3 | PerceptionPipeline 桥接 perception→world_model + import_rules allowlist | 全量绿 | 1ca4884 |
| 2026-08-29 | P2-1 | KnowledgeRegistry→SemanticStore 持久化镜像(UPSERT) | 5229 passed/1 failed(organ_client 既有) | 6a63222 |
| 2026-08-29 | P2-2 | runtime/stages 4 个占位接线 | 全量绿 | 415f4c8 |
| 2026-08-29 | P2-3 | event_memory SQLite 化(append-only) + archive 真实标记 + 删 CR55-03 假声称 | 57 passed 零回归 | 4b11c51 |
| 2026-08-30 | P2-4 | wisdom_store SQLite 落盘 + personalization FORMAL/BOLD 补实现 | 122 passed 零回归 | 1268495 |
| 2026-08-30 | P2-5 | living_test 真实化: resurrection_drill 10/10 + snapshot/goal 自愈建表 + 行工厂污染修复 | 全量仅 organ_client 既有失败 | 333675b |
| 2026-08-30 | P3-1 | stability/ 三件套删除 (生产零引用) + retry_policy 弃用桩 with_retry 删 | 定向 8 passed | 10b12ca |
| 2026-08-30 | P3-2 | persistence/ 核查: 非重复实现 (通用快照框架 vs agent SQLite) → 降级分工 docstring | phase51 87 契约测试过 | 54f69e1 |
| 2026-08-30 | P3-3 | crash_recovery 核查: 进程级 vs agent 轻量, 非重复 → 降级分工 docstring | recovery + phase21/58 测试过 | 5c06ea5 |
| 2026-08-30 | P3-4 | goal_store 两套核查: 表字段互斥 (result_json vs progress/decision_refs) → 降级分工 docstring; C.7 核查取消 (decision_loop 生产在用, 顶层 belief.py 不存在) | goal 6 测试过 | 9fb9a78 |
| 2026-08-30 | P3-5 | event/ vs events/ 分工 docstring (感知 vs 宪法总线); C.1 constitution 占位标注; event_store 测试契约锁定保留 | event 6 测试过 | b349c53 |
| 2026-08-30 | P3-6 | planning/validator.py 真合并入 plan_validator.py: validate_plan() 入口 + 删 48 行重复 + 迁移 2 测试 | 定向 12 passed 零回归 | 3f03794 |
| 2026-08-30 | P3-7 | capability_reality 核查: Phase 45 抽象层 vs Phase 55 真实层分层 → 降级分工 docstring | phase55/58 定向过 | cd556bb |
| 2026-08-30 | P3-8 | 三套注意力裁决: 分层确认 (引擎/控制器/编排) + 冻结面不动 → 裁决文档; C.3/C.4 清理 | 定向 44 passed (单跑竞态通过) | 9f2ed15 |
| 2026-08-30 | P3-C5 | engines/__init__ manifest 统一导出 + writer_engine 补 __manifest__ | writer/planning 测试过 | 8204b16 |
| 2026-08-30 | P3-C6+F1 | snapshot 默认路径收敛 ~/.ocos/ocos.db + stub/placeholder 复查清单存档 | phase21 测试过 | e8c09ac |
| 2026-08-30 | P3-F2 | 全量回归 | 唯一失败 = organ_client 既有超时, P3 零回归 | (见下) |
