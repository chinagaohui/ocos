# OCOS 审计修复执行方案（AUDIT_FIX_PLAN v1.0，2026-08-30）

> **依据**: `docs/OCOS_MODULE_AUDIT_20260830.md`（F1-F10 + 三处扫描纠正 + 测试覆盖分析）
> **基线**: 合并 testpaths 后 5245 passed / 24 skipped / 0 failed（commit 0de4c62）
> **纪律**: 沿用 GAP 计划三条纪律——每项一个 commit（编号 AUD-F1 等）、不动冻结面（触碰即走 evolution 审批链）、架构守卫测试（import_rules/no_direct_store_access）必须持续通过。
> **总工期**: 约 5-7 个工作日；P0 半天必须做，P1 一天，P2 是主体，P3 收尾。

---

## P0：快速修复（4 项，约半天）

### AUD-F1 补齐 run.py 半接线（语义镜像 + 感知链上电）

**问题**：P2-1 与 P1-3 的接线只做到 factory 层，`cli/commands/run.py:49-58` 未调用 `build_knowledge_registry` 和 `build_perception_pipeline`——知识库 SQLite 镜像与世界模型感知链在默认入口不生效。

**改动文件**：`ocos/interaction/cli/commands/run.py`

**步骤**：
1. 在 `build_master_agent` 之后：
   ```python
   from ocos.daemon.factory import build_knowledge_registry, build_perception_pipeline
   from ocos.memory.hub import MemoryHub
   hub = MemoryHub(db_path)                      # 与 run.py 现有 db_path 一致
   build_knowledge_registry(semantic_store=hub.semantic)
   pipeline = build_perception_pipeline(sensors=[])   # 默认零传感器，零噪音
   ```
2. 感知管线的宿主：给 `ResidentRuntime` 增加可选 `perception_pipeline` 参数，在 `_tick_loop` 中按 N tick（建议与 health_loop 同款节流，默认每 tick drain 一次，传感器为空时为零开销）调用 `pipeline.poll()`；sensor 注入留给 `--watch-dir` 后续参数（本项不做，只留接口）。
3. 启动输出加两行状态（对齐现有 `bridge :` 打印风格）：`knowledge : SemanticStore 镜像已启用` / `perception : 感知管线已挂载 (0 sensors)`。
4. 更新 `build_knowledge_registry` 的消费链说明：确认 registry 实例同时被 engines 的 promotion/consolidation 路径拿到（若 engines 经全局 discovery 拿不到该实例，则至少保证镜像写路径在 registry 内自洽——以测试为准）。

**验证**：
```bash
python -m pytest tests/test_daemon_health_loop.py ocos/tests/test_single_main_loop.py tests/interaction/ -q
# E2E 冒烟: 临时库跑 ocos run --ticks 3, 检查 knowledge 表存在且 daemon 启动无异常
OCOS_DB_PATH=$(mktemp -d)/t.db python -m ocos.interaction.cli.main run --ticks 3
```

**完成标准**：默认入口启动日志含两行新状态；全量测试绿；无 sensor 时 tick 开销无感。

### AUD-F3 修正 stages/__init__.py 过期 docstring

**问题**：`ocos/runtime/stages/__init__.py:4-9` 仍写 ①③⑤⑥ 四个 stage 是"占位"，实际 GAP-P2-2 已全部接线——文档与代码矛盾会误导下一次审计。

**改动文件**：`ocos/runtime/stages/__init__.py`

**步骤**：重写 docstring 为当前事实：①EventIngestion=注入 EventBus drain（缺省 None 诚实降级）；③MemorySync=MemoryHub 快照；⑤ResultCollection=ExecutionManager 历史；⑥ExecutionCheck=可选 TaskDAG + PermissionGateway（默认不传→空候选）。标注"可选依赖缺省 = 诚实降级，非占位"。

**验证**：`python -m pytest ocos/tests/test_single_main_loop.py -q`（纯文档改动，跑一次防手滑）。

### AUD-F4 living_test day7 协议本体 fail-closed

**问题**：`ocos/living_test/day7_resurrection.py:80-95`——钩子为 None 时 `restored/memory_intact/goals_intact/timeline` 仍置 True，空场景可假通过（目前靠 scripts/resurrection_drill.py 兜底，但协议自身不诚实）。

**改动文件**：`ocos/living_test/day7_resurrection.py`

**步骤**：
1. 钩子缺失时结果置 False 并给出明确 `reason="hook not provided — scenario cannot prove resurrection"`；
2. 同模式检查 day1-day6 各场景文件（`grep -n "placeholder\|= True" ocos/living_test/`），凡"钩子缺失→默认通过"的断言一并改 fail-closed；
3. 跑 `scripts/resurrection_drill.py` 确认真实钩子路径不受影响。

**验证**：
```bash
python -m pytest ocos/tests/test_phase58*.py -q        # 协议测试（如有假通过断言需同步改）
python scripts/resurrection_drill.py 2>&1 | tail -3    # 真实演练仍 10/10
```

**完成标准**：空场景 run 结果为 fail；drill 结果不回退。

### AUD-F2 补 P3 唯一遗漏的裁决：runtime_scheduler ↔ runtime/scheduler

**问题**：P3 四组重复实现裁决中唯一没写 docstring 的一对。两者职责不同：`runtime/scheduler.py` 是 B3 事件驱动分发器（EngineInfo/RegistryAdapter，生产在用）；`runtime_scheduler/` 是心跳调度器（CognitiveClock/PriorityQueue/Backpressure/Worker，Phase 51.2，零生产引用）。

**改动文件**：两个包的 `__init__.py`（或主文件头部）

**步骤**：
1. 各写分工 docstring（对齐 P3-2/P3-5 的裁决格式）：runtime/scheduler="B3 事件分发（tick 内 stage 级）"；runtime_scheduler="独立任务心跳调度（Phase 51.2 契约，test_phase51_2 锁定），当前无生产消费者，候选接入点=ResidentRuntime 任务队列"。
2. 在本文档 §决策记录表登记"保留两者、待 daemon 任务队列需要背压时再评估合并"。

**验证**：`python -m pytest ocos/tests/test_phase51_2.py tests/ -q -k scheduler`

---

## P1：裁决与去重（5 项，约 1 天）

> 纯文档/docstring/小删除，无行为变化。每项先 diff 确认无字段丢失。

### AUD-F5 operations/ vs digital_world/ 裁决

**问题**：两套平行的真实执行操作面。`operations/`（Phase 22-E）= SandboxOps（30+ 危险命令黑名单 + 白名单前缀 + 路径沙盒 + 真实 subprocess）+ SearchOps（URL 白名单 + 真实 HTTP）；`digital_world/`（Phase 29）= file/git/api/db/search/sandbox（默认 dry_run）。零互相引用，均无生产消费者。

**步骤**：
1. 做能力矩阵 diff（命令执行/文件读写/HTTP/DB 各自覆盖与安全机制），写入两个包 `__init__.py` 裁决 docstring + `docs/OCOS_MODULE_AUDIT_20260830.md` 追加节。
2. 推荐结论（可调）：**operations/ = 未来 DecisionBridge 高危能力（shell/HTTP）的执行层候选**（黑白名单模型与 R4-A 的 AUTO/ASK 分级天然契合）；digital_world/ = 面向"数字世界"语义的宽操作库，维持 dry_run 默认。二者分工登记，不合并、不删除。
3. 若裁决为上述结论，在 `execution/bridge.py` 的 DENY/ASK 注释处补一行指向 operations/ 的候选关系。

**验证**：`python -m pytest tests/test_operations/ tests/digital_world/ -q`（确认 docstring 改动零破坏）。

### AUD-F6 第三套同名实现裁决：storage/event_store、dead_letter_queue vs events/

**步骤**：
1. diff 三者接口（`storage/event_store.py` SQLiteEventStore 生产在用（recovery 链）、`events/event_store.py` 内存版契约锁定保留、`storage/dead_letter_queue.py` vs events/ 下同名物）。
2. 按 P3-5 格式写分工 docstring：谁服务持久化恢复链、谁服务进程内总线；被裁决为死代码的直接删除并迁移测试。
3. 把结论追加到 GAP 执行记录表的 P3 节（"P3-5 扩展"）。

**验证**：`python -m pytest tests/ ocos/tests/ -q -k "event_store or dead_letter or event_bus"`

### AUD-F7 TaskDAG 同名撞车去重

**问题**：`ocos/task/`（Phase 23-C，零生产 import）与 `planning/models.py` 里的 TaskDAG（生产在用，TaskDecomposer 产出）同名不同实现。

**步骤**：
1. diff 字段/接口（`resolve_ready/拓扑排序/环检测` vs planning 版）。
2. 推荐结论：**ocos/task/ 降级为"待 RuntimeKernel execution_check 消费的执行队列"**——它就是 P2-2 为 execution_check 预留的注入类型。两个动作：① `ocos/task/__init__.py` 写裁决 docstring 指明唯一未来消费者与与 planning 版的分工（规划期 DAG vs 执行期就绪队列）；② 让 `runtime/stages/execution_check.py` 的 docstring 明确"注入类型应为 ocos.task.TaskDAG"，消除 duck-type 模糊。
3. 不做合并（planning 版带 goal_id/agent_type 语义，执行版带依赖调度语义）。

**验证**：`python -m pytest ocos/tests/ -q -k "task or dag or execution_check"`。

### AUD-F10a 候选裁撤清单（auth / belief.py / SelfGovernor+SelfMonitor）

**步骤**：
1. `docs/OCOS_AUDIT_KERNEL.md` 新增 "Deprecated / Pending-Removal 清单" 节，登记三项：
   - `ocos/auth/`：与 self.IdentityBoundary 语义重叠，唯一 gate 引用是 phase23_gate 脚本；
   - `ocos/belief.py`（BeliefManager）：第三套信念系统，仅 test_phase61a/62d 引用，持久化 TBD；
   - `self/governor.py` + `self/monitor.py`：生产零引用（审批能力已由 evolution + R4-A ASK 承担）。
2. 每项写明：裁撤理由、替代物、迁移动作（auth 若 API 鉴权要用则转正——与 F8/安全项联动）。
3. 本项**只登记不删除**；实际删除放下一个大版本（与 test_phase61a 等测试一并迁）。

**验证**：全量测试（纯文档）。

### AUD-F11 agent_orchestration supervisor 模拟回退收敛

**问题**：`agent_orchestration/supervisor.py:32-38` 无 AgentExecutor 注入时返回假成功 `True, "Agent ... completed task"`——虽然当前无生产实例化（沉睡），但一旦被接线就是假成功复发点。

**步骤**：模拟回退改为返回 `(False, "no AgentExecutor injected — task NOT executed")` 并 logger.warning；同步改依赖旧行为的测试（grep `_execute_agent` / supervisor 相关断言）；`AgentExecutor` 注入路径保持不变。

**验证**：`python -m pytest tests/test_agent_orchestration/ ocos/tests/ -q -k "supervisor or executor"`（测试目录以实际为准）。

---

## P2：功能补齐（4 项，约 2-3 天）

### AUD-F8 CLI goal/plan 落库 + API 写路径

**问题**：`cli/commands/goal.py:53` 只 `session.record_goal`（会话内存），:64/:74 仍打印 "not yet implemented / TBD"；plan.py 分解后 DAG 只打印；API goal 路由只读。

**改动文件**：`ocos/interaction/cli/commands/goal.py`、`plan.py`、`ocos/interaction/api/routes/goal.py`（可选）

**步骤**：
1. goal.py：`to_user_goal()` 后经 `GoalSQLiteStore(db_path).save()` 落库（db_path 复用 run.py 的 `OCOS_DB_PATH`/`~/.ocos/ocos.db` 解析——抽一个 `interaction/cli/paths.py::resolve_db_path()` 小工具避免三处重复）；`PermissionGuard.create_goal` 三重检查保持在前。
2. plan.py：分解后把 DAG 存入 goal 对应记录（或 `snapshot` 体系的新表 `plan_dag(goal_id, dag_json)`——加入 `storage/schema.py` v4 迁移）。
3. 删除两处 "TBD" 打印，改为确认输出（goal id + 落库路径）。
4. API：`routes/goal.py` 增加 POST 走同一 GoalSQLiteStore（PermissionGuard 前置不变）。
5. 迁移：`storage/migrations.py` 版本 +1，`ensure_schema` 自动补。

**验证**：
```bash
python -m pytest tests/interaction/ ocos/tests/test_no_direct_store_access.py -q
# E2E: ocos goal create ... 后 sqlite3 ~/.ocos/ocos.db "select count(*) from goals"（表名以 schema 为准）
```

**完成标准**：CLI 创建的 goal 重启进程后仍可查询；TBD 文案归零（`grep -rn "TBD" ocos/interaction/` 复查）。

### AUD-F9 build_master_agent 引擎注册（消灭 status:"stub" 降级）

**问题**：`daemon/factory.py` 组装 MasterAgent 时未注册任何决策引擎，生产运行时 master_agent 的 think/decide/reflect/learn 走 `status:"stub"` 降级（master_agent.py:312,413,484,624,667）——认知阶段名存实亡。

**改动文件**：`ocos/daemon/factory.py`、`ocos/interaction/cli/commands/run.py`

**步骤**：
1. factory 增加 `build_engine_bridge()`：`EngineBridge()`（`_ensure_engines_registered` 已保证 planner/reasoner/writer 在册）→ 实例化三引擎 → 注入 MasterAgent 对应构造参数（以 master_agent.__init__ 实际参数名为准，缺省 None 的逐一填上）。
2. run.py 装配 + 启动输出加一行 `engines  : planner/reasoner/writer 已注册`。
3. 在 master_agent 各阶段 stub 返回处加 debug 日志（保留诚实降级语义，_factory 不再触发它）。
4. 验证 LLM Provider 缺 key 时 text_generator/writer_engine 的 Mock 降级仍按既有设计工作（不引入新依赖）。

**验证**：
```bash
python -m pytest tests/test_agent/ ocos/tests/test_single_main_loop.py -q
# 冒烟: ocos run --ticks 5, 确认 tick 输出无 "status": "stub"
```

**完成标准**：默认入口 5 个 tick 内 decide/reflect 返回真实引擎结果；stub 路径仍存在但仅作为无引擎时的诚实降级。

### AUD-F12 R4-B 最小可用：ASK 待批队列的持久化与审批命令

**问题**：DecisionBridge 的 `_pending` 只在内存，`ocos run` 进程一退待批动作即丢，且无任何批准入口（run.py 已明示）。这是执行回路"卡住"的根源。

**改动文件**：`ocos/execution/pending.py`（新建）、`ocos/execution/bridge.py`（注入替换 list）、`ocos/interaction/cli/commands/approvals.py`（新建）、`ocos/interaction/cli/parser.py`（注册命令）

**步骤**：
1. `pending.py`：SQLite 表 `pending_actions(id, action_type, target, payload_json, text, queued_at, status[pending|approved|denied|executed], decided_at)`——落 `~/.ocos/ocos.db`（复用 storage 连接池；DDL 入 schema v4，与 F8 同一个迁移版本）。`PendingStore` 提供 enqueue/list/decide/mark_executed。
2. bridge：构造函数接受 `pending_store`（默认 None 时退回内存 list——诚实降级）；`_pending.append` 改为 store.enqueue；run.py 装配时传入。
3. CLI：`ocos approvals list` / `ocos approvals approve <id>` / `ocos approvals deny <id>`。approve 时按 action_type 回放执行：DAG 类任务重建 task 交 `_dag_*_execute`；AUTO_ACTIONS 类交 `dispatcher.dispatch`；执行后 mark_executed + ExecutionAudit 记录（审批人记 "cli"）。
4. 安全边界：approve 属人工决策，不二次过 PermissionGuard 语义双检（人工即 authority），但**必须**落审计；`ocos run` 启动输出更新为 "ASK 待批: N 项待决（ocos approvals list）"。
5. 迁移与 F8 合并进 schema v4。

**验证**：
```bash
python -m pytest ocos/tests/ -q -k "pending or approval"          # 新增 test_pending_store.py + bridge 注入测试
# E2E: ocos run 触发一个 create 类 DAG 任务 → ocos approvals list 见 1 项
#      → ocos approvals approve <id> → 审计出现 executed 记录
```

**完成标准**：待批动作跨进程存活；approve 后真实执行且有审计；deny 后不再出现。

### AUD-F13 decision 链与 cognitive_loop 的处置裁决（架构决策项）

**问题**：审计纠正了 P1-1 的认知——DecisionPipeline→decision 组件链接线真实，但挂在未上电的 AutonomousLoop 上；生产 tick 走 AgentRuntime 自己的决策路径。这是"备用引擎"格局，需要明确处置而非默认漂移。

**两个选项**（本方案推荐 A，但此项涉及主循环行为，**执行前应经老高确认**）：
- **选项 A（推荐，成本 0.5 天）**：维持备用引擎定位。在 `cognitive_loop/__init__.py` 与 `decision/__init__.py` 写裁决 docstring（"已上电的决策路径 = AgentRuntime step7/8 + DecisionBridge；本链 = 自治循环编排视图，经 AutonomousLoop 激活，当前无生产消费者"），并在 os_v1/freeze 清单登记。等 R4-B 稳定后再评估是否让 AgentRuntime 在无 DAG/无决策时 fallback 到 LoopOrchestrator。
- **选项 B（成本 2 天，改变主循环）**：AgentRuntime step 7 在无 TaskDAG 且 core_loop 无产出时调用 `DecisionPipeline.propose()` 作为决策来源，经 DecisionBridge 分级执行——让 decision 组件链（RiskEngine/Validator）真正进入生产行为。

**验证**：选项 A 全量测试；选项 B 需新增 E2E（构造无 DAG goal → 断言 proposal 来自 OptionGenerator 且 trace 落 DecisionTracer）。

---

## P3：测试补强 + 收尾（2 项，约 1 天）

### AUD-F14 新接线模块 E2E 补强

**问题**：主链路覆盖最薄的四个包：proactive（12 test 函数）、alerts（18）、decision（20）、execution（27）。

**步骤**：每个包补 1 条穿透 E2E（对齐 test_execution_bridge.py 的风格）：
1. proactive：goal→空闲 tick→输出触发→审计落库（mock output_callback 收集）；
2. alerts：health_loop 超阈快照→FileChannel 文件断言（已有 daemon 测试，补一条 alerts 独立端到端）；
3. decision：ContextBuilder→OptionGenerator→Validator 全链 + trace 完整性；
4. execution：AUTO/ASK/DENY 三路各一条真实执行/入队/拒绝断言（部分已有，补 DENY 路径与审计断言）。

**验证**：`python -m pytest -q` 合并全量，基线 ≥5245+新增。

### AUD-F15 审计收尾

1. `docs/OCOS_MODULE_AUDIT_20260830.md` 追加"修复执行记录"节，逐项登记 commit 与测试基线；
2. `grep -rn "TBD\|占位\|placeholder" ocos/ --include="*.py" | grep -v tests` 复查，输出残留清单存档（与 GAP-P3-C6 的 F.1 清单合并）；
3. 全量回归 + 更新 GAP_REPAIR_PLAN §6 记录表。

---

## 决策记录表（执行中填写）

| 日期 | 编号 | 决策 | 理由 |
|------|------|------|------|
| | AUD-F2 | 保留双调度器，登记分工 | 心跳调度器为 Phase 51.2 契约测试锁定 |
| | AUD-F5 | operations=高危能力执行层候选 / digital_world=宽操作库 | 黑白名单模型契合 R4-A 分级 |
| | AUD-F7 | ocos/task=执行期就绪队列（execution_check 唯一消费者） | 与 planning 期 DAG 分工 |
| | AUD-F13 | 待老高确认（推荐 A：备用引擎定位） | 涉及主循环行为 |

## 执行顺序与依赖

```
P0: F1 → F3 → F4 → F2          （半天，互不依赖可并行）
P1: F5/F6/F7/F10a/F11          （一天，纯裁决+小改）
P2: F8(含 schema v4) → F12(复用 v4) → F9 → F13   （F8/F12 共用迁移版本）
P3: F14 → F15
```

schema 迁移只开一个版本号（v4），F8 与 F12 的 DDL 一次进齐，避免迁移碎片化。
