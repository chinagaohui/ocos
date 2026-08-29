# P1-C 循环收敛（2026-08-29）

## 背景：5 套循环实体 + 1 生产循环

| 实体 | 位置 | 形态 | 生产路径 |
|---|---|---|---|
| A AgentRuntime | ocos/agent/agent_runtime.py | 10 步 tick()（真业务） | ✅ 经 E 驱动 |
| B RuntimeKernel | ocos/runtime/runtime_kernel.py | while tick_loop（空壳心跳 + 8 阶段 pipeline） | ✅ **收敛后唯一认知宿主** |
| C LoopOrchestrator | ocos/cognitive_loop/loop_orchestrator.py | 7 阶段 tick()（器官协同） | ❌ 仅测试 |
| C' AutonomousLoop | ocos/autonomous_runtime/autonomous_loop.py | 被动包装 C | ❌ 仅测试 |
| D TaskScheduler | ocos/runtime_scheduler/task_scheduler.py | while run()（调度壳） | ❌ 仅测试 |
| E ResidentRuntime | ocos/daemon/__init__.py | while _tick_loop（0.05-5s interval） | ✅ 生产唯一主动循环 |

收敛前：生产循环 E 直接调 A.tick()；B/C/C'/D 各自持有循环语义，但只有 B 的 8 阶段 pipeline
与 A 的 10 步高度同构（EventIngestion≈Step1、Attention≈Step2、MemorySync≈Step3、
GoalMaintenance≈Step4、ExecutionCheck≈Step5、ResultCollection≈Step9、LearningTrigger≈Step10）。

## 语义定调

「单进程单主循环」= **认知循环单一宿主**（RuntimeKernel.tick_loop），而非字面唯一 while。
daemon 的 while 保留为外层时钟（管 sleep/stop/目标队列 drain），每轮调
`kernel.tick_loop(max_ticks=1)` 触发一次认知 tick。

## 改动清单（注入式，零解冻）

### 1. ocos/runtime/pipeline.py
- `TickPipeline.attach_agent_driver(driver: Callable[[int], dict])`：
  driver 在 8 空壳 stage 之后、COMPLETE 之前执行；结果存 `last_agent_result`。
- 不改 STAGE_ORDER/阶段计数（R39-201 冻结断言保持）。
- 未 attach 时行为完全不变（R39-202 空系统心跳保持）。
- 零 import ocos.agent（R39-203 Governance 冻结保持）。

### 2. ocos/runtime/runtime_kernel.py
- `attach_agent_driver(driver)` 透传到 pipeline。
- `last_agent_result` property 透传 pipeline 结果。
- `tick_loop(max_ticks, interval)` 的 max_ticks 改为**本次调用内局部计数**
  （原实现用全局累计 tick_count，导致多次调用 `tick_loop(max_ticks=1)` 时第二次起直接空转
  ——P1-C 施工中实测发现并修复；单次大 max_ticks 语义不变）。

### 3. ocos/daemon/__init__.py（ResidentRuntime）
- `__init__(..., kernel=None)`：kernel 默认自建（延迟 import RuntimeKernel，零循环依赖）。
- `start()`：kernel.start()（幂等：RUNNING 则跳过，restart 场景安全）+ attach
  `lambda tick_id: self._runtime.tick()`（AgentRuntime.tick 经 driver 注入 kernel）。
- `_tick_loop()`：`self._runtime.tick()` → `self._kernel.tick_loop(max_ticks=1)`。

### 4. ocos/tests/test_single_main_loop.py（新建，11 项）
- T1（2）：kernel attach driver → tick_loop(3) 驱动 3 次 + last_agent_result 可查/逐次更新。
- T2（1）：未 attach → pipeline 8 stage trace + COMPLETE 完整（空系统语义不变）。
- T3（1）：ResidentRuntime 集成 → cycle_count 与 kernel.tick_count 同步增长 + driver 已注入。
- T4（3，parametrize）：daemon/__init__.py、factory.py、run.py 无 LoopOrchestrator/
  TaskScheduler/AutonomousLoop 引用（C/C'/D 不进生产路径）。
- T5（4，parametrize）：runtime_kernel.py、pipeline.py、stages 不 import ocos.agent（AST，R39-203）。

### 5. 未改动（保持冻结）
- AgentRuntime、LoopOrchestrator、AutonomousLoop、TaskScheduler、test_phase39_2.py 全部不动。

## 验收证据（2026-08-29）

| 测试面 | 结果 |
|---|---|
| ocos/tests/test_single_main_loop.py（P1-C 专属） | 11/11 ✅ |
| test_phase33（daemon 5 项，含 restart） | ✅ |
| test_phase39_1 / test_phase39_2（冻结） | ✅（45 项含 phase33） |
| P1-A 三件套 + tests/memory/ + phase24 | 308 过（唯一失败 = P1-A 遗留 isolation 断言，见下） |
| ocos/tests/ 全量 | 3237 过（唯一失败 = 既有 organ_client 超时） |
| tests/ 全量 | 1920 过（4 失败全部为已知基线缺陷，见下） |
| 生产入口冒烟 `ocos run --ticks 3` | cycles=3 ✅ daemon→kernel→driver→runtime 链路通 |

## 回归中发现的事项（非 P1-C 引入，待裁决）

1. **tests/memory/test_phase24_isolation.py::test_memory_imports_self_contained**
   - 失败点：memory 包 store（semantic/episode/pattern/belief）import `ocos.storage.connection`。
   - 溯源：baseline(81ea10d) 的 store 无此 import；P1-A store 下沉时引入共享 connection，
     P1-A 收官 71 项回归未覆盖此文件 → **P1-A 遗留过期断言**（Freeze 例外表未同步）。
   - 建议最小修改：`_FREEZE_ALLOWED` 增加 `ocos.storage.connection`（符合 store 下沉定案架构）。
   - 未静默修改，提请裁决。

2. 已知基线缺陷（归 P1-D）：test_repl_api（权限 8 vs 6）、test_logger_coverage（15.7%<20%）、
   test_no_personality_leak（self/ 13 处 prefer）；ocos/tests/test_organ_client（urllib 重试超时）。

## 前后形态

```
收敛前:  E._tick_loop ──> A.tick()            B/C/C'/D 各持循环语义（仅测试）
收敛后:  E._tick_loop ──> B.tick_loop(1) ──> pipeline 8 stage ──> A.tick()（driver 注入）
         C/C'/D 保持组件与测试，明确不进生产路径
```

## 符合冻结原则

- 不改 STAGE_ORDER/阶段计数（R39-201 绿）；未 attach 空系统行为不变（R39-202 绿）；
  零 import ocos.agent（R39-203 绿，AST 断言）。
- 注入式收敛：无解冻、无拆建，Governance 冻结全程保持。
- 循环收敛未增加任何新的并发循环——生产仍是单 while（daemon 外层时钟），认知 tick 唯一经 kernel。
