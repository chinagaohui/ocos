# OCOS 升级优化修复方案 —— 可行性评审与落地执行版 v1.0

> 评审对象：《OCOS 升级优化修复方案》（4 Sprint / 9 P1 + 14 P2 + 6 P3 + 4 P4 + 3 架构优化）
> 评审依据：《OCOS 项目白皮书 v1.2》全量审计结论 + 2026-09-05 对关键代码点的二次核验
> 结论先行：**方案总体可行**——批次划分、依赖编排、TDD 策略、Feature Flag 风险控制均正确，行号/常量名/根因描述经抽查与代码一致。但存在 **6 处需要修正**（P1 覆盖缺口 4 项、P2 缺口 8 项、1 项行为变更波及面被低估、1 项架构迁移应降级、5 处技术细节修正、1 处审计误报需复核），修正后按本执行版落地。

---

## 一、评审结论与修正清单

### 1.1 总评

| 维度 | 评价 |
|---|---|
| 批次划分（安全止血→数据完整性→生产可用→架构治理） | ✅ 正确，依赖关系成立 |
| 缺陷定位精度 | ✅ 抽查 6 处（bridge.py:905、pending.py:34、server.py:88、adapter_fs.py:79、resource_manager emit、ActionType 枚举）全部与代码一致 |
| 修复手法 | ✅ 大部分最小侵入（单行修复、守卫、默认值调整），符合"不动冻结面"纪律 |
| P1 覆盖 | ⚠️ 方案称 9 项，白皮书实测 12 项；**遗漏 4 项**（见 R1），另有 1 项审计误报需降级（R6） |
| P2 覆盖 | ⚠️ 遗漏 8 项高频静默失效（学习闭环三连、focus TypeError 等，见 R2） |
| 最大行为变更 | ⚠️ S2.2 审批默认值切换波及面被低估（见 R3） |
| Sprint 3.1 管线迁移 | ⚠️ 触碰冻结语义，建议降级（见 R4） |

### 1.2 修正清单（R1–R6）

**R1 —— P1 覆盖缺口：补入 4 项遗漏的 P1**

| 缺项 | 白皮书编号 | 编入 |
|---|---|---|
| digital_world/sandbox.py"沙箱"实为 shell=True+11 条黑名单（可变体绕过） | P1-12 | **Sprint 1.7**（新增） |
| health_examination OCOS_ORGANS 器官注册表失配（3 个模块路径不存在、12 器官 exports 全 missing，实测复现） | P1-9 | **Sprint 2.12**（新增） |
| life_cycle_orchestrator 与生产注意力对象接口失配 | P1-10 | **降级为复核项**（见 R6），编入 Sprint 2.13 |
| orchestration/engine.py:346 record.to_dict() 崩溃 + agent_orchestration_autonomous 串行路径伪造成功 | P1-11 | **Sprint 4.3**（并入死代码清理，两处均为孤立支线，修复=诚实失败或删除） |

**R2 —— P2 覆盖缺口：补入 8 项（全部为审计实测确认的静默失效）**

| 缺项 | 位置 | 编入 |
|---|---|---|
| 学习闭环三连：`_extract_beliefs` 条件失配恒空转（outcome "completed" vs 判定 "success/great/good"） | agent_runtime.py:1560-1575 vs :1411 | Sprint 2.14 |
| 学习闭环三连：reliability 查 `count` 键而 `get_stats` 返回 `total` | capability/outcome_evaluation.py:128 | Sprint 2.14 |
| 学习闭环三连：calibration_store 调用不存在的 `update_reliability()` 假报 applied=True | capability/calibration_store.py:75-81 | Sprint 2.14 |
| attention/focus.py `process_observation` 关键字错误实测 TypeError（主入口即坏） | attention/focus.py:131-139 | Sprint 2.15 |
| `_tick_errors` 无自增点 → 稳定性报告 error_rate 恒 0 | agent_runtime.py:138/1669/1685 | Sprint 3.9 |
| PipelineError 不被 tick_loop 捕获 → 单 stage 失败终止整个心跳 | pipeline.py:120-127 + runtime_kernel | Sprint 3.10 |
| runtime_id 每 boot 换 uuid → 旧式 checkpoint 永远 miss；RestoreResult 认知矢量不回灌 | runtime_kernel.py:59-69/113-130 | Sprint 3.11 |
| event_store sequence 非原子（SELECT MAX 后 INSERT）；kernel EVENT_SCHEMA 三键重复注册弱化校验 | storage/event_store.py:193-195；kernel/event_schema.py:180-268 | Sprint 3.12 |

**R3 —— S2.2 审批默认值切换是全方案最大行为变更，缩小切口**

现状：`OCOS_APPROVAL_MODE` 默认 `auto`（pending.py:34-41），UX-H"对话即执行"、生产验证 e2e 全链路都依赖 auto 下的自动执行。方案的原设计（auto 仅在 dev 双条件下生效）会**一次性打断所有自动执行流**，验收基线（5287+）也会因流程语义变化大面积变红。修正为三步走：
1. Sprint 1 已通过 1.1 的修复实现"**危险动作子集强制审批**"（FILE_WRITE 无 approval_id 必入待批）——这已经消除了最危险面；
2. Sprint 2 只做**可观测**：auto 模式启动时打印显著警告横幅（含设置方法），文档标注生产环境建议 `ask`；
3. 全局默认值切换（auto→ask）作为 **Sprint 3 收尾的一次性变更**，切换前全量回归 + 更新 PRODUCTION_VALIDATION 的 e2e 预期。

**R4 —— Sprint 3.1 TickPipeline 迁移降级**

10 步迁移进 8 Stage 触碰 step7 冻结语义（上电方案 PW-4.3 已裁决"延后，触碰 step7 冻结语义"），且 GAP-P2-2 的"生产旁路"是有裁决注释的现状而非回归。本迭代只做两件事：① PipelineError 在 tick_loop 层兜底（S3.10，与 R2 合并）；② SAFE_MODE/DEGRADED 死状态接线最小实现（宪法违规→SAFE_MODE）。**完整 Stage 化迁移移出本迭代**，单独立项（Phase 63 候选）。

**R5 —— 五处技术细节修正**

1. **S1.6 emit→publish**：两套总线 API 不同（`ocos/events` 有 publish，`ocos/event` 只有 push/ingest）。resource_manager/adaptive_control 的 docstring 语义对应 `ocos/events.EventBus`，替换为 `publish` 正确，但需在步骤中显式断言注入类型（`isinstance` 校验或文档约束），防再次错配。且这两个模块无生产消费者——修完即回归测试锁死即可，不必接线。
2. **S1.5 ShellAdapter 白名单化波及面**：bridge 的 RUN 命令走 `operations.SandboxOps`（不受影响），但 ShellAdapter 被 tool/manager 等消费，白名单化会改变其行为面——需在步骤中列出消费方并逐一回归。
3. **S1.2 AuthMiddleware 会打断现有客户端**：TUI（tui.py 纯 HTTP 客户端）、restart.py、external/server_manager 健康检查、生产 hermes-gateway 都在调 API。步骤中必须包含"客户端同步注入 Token"子项，并保留 `/ocos/health` 与 `/ui` 豁免。
4. **S2.5 event_store 时间格式统一必须带旧数据迁移**：现库已存在两种格式（`datetime('now')` 空格式 vs 本地 ISO T 格式）混合行，仅改写入侧会让 load_from_db 对旧行解析失败（ts=0.0）。需一次性迁移脚本。
5. **S2.3 Boundary 阻断需可配置**：INCOMPLETE 经验保留是设计行为（ExperienceCandidate 文档明示）；直接 raise 会误杀合法候选。改为 `OCOS_EXPERIENCE_BOUNDARY_STRICT`（默认 false=仅记录，true=阻断），默认值调整放 Sprint 3。

**R6 —— 一处审计误报复核（诚实修正）**

白皮书 P1-10（life_cycle_orchestrator 调用 `attention.needs_sleep()` 而生产对象无此方法）经二次核验**不成立**：`CognitiveAttentionController` 继承自 `AttentionManager`（capability/attention.py:133/469），`needs_sleep` 定义于父类（:137 附近）。降级为 P3 复核项：需实测 `_tick_idle` 全路径行为语义（tick/reset/needs_sleep 三调用的参数兼容性），不作为 P1 修复项。

---

## 二、Sprint 1 落地步骤：安全止血（P1×7，3–5 天）

> 执行纪律：每项独立 commit（编号 S1.x），先写失败测试再修复；每项完成后跑 `python -m pytest -q` 确认基线不红。

### S1.1 DecisionBridge FILE_WRITE 审批绕过

**前置**：确认工作区干净或先行提交现有改动（当前有 5 个未提交修改文件）。
**改动文件**：`ocos/execution/bridge.py`、`ocos/autonomous_runtime/action_dispatcher.py`（仅枚举）、`tests/` 新增回归。

步骤：
1. `action_dispatcher.py:17` ActionType 枚举新增成员 `FILE_WRITE = auto()`（核验：当前 10 个成员无 FILE_WRITE，方案 1.1-③ 的前提成立）。
2. `bridge.py:53` ASK_ACTIONS 冻结集加入 `ActionType.FILE_WRITE`；`_DAG_ASK_TYPES`（:80）保持不变（create/modify/execute 已覆盖任务级）。
3. `bridge.py:905-910`（`_handler_dag_task` 的 FILE_WRITE 分支）：删除默认值——`"approval_id": payload.get("approval_id", "task-approved")` 改为 `"approval_id": payload.get("approval_id")`。
4. `bridge.py` `_handler_file_op` 入口：`approval_id` 为 None 时**无视 `approval_disabled()`** 直接 `_enqueue_pending`（FILE_WRITE 属强制审批动作，不受 auto 模式豁免）；返回 `{"ok": False, "pending": True, "reason": "file_write requires approval"}`。
5. `execute_approved()`（:1051）入口加校验：从 PendingStore 读取该 pid，断言 `status == 'approved'` 且 `action_type` 匹配，否则拒绝执行并留审计（防伪造 approval_id 重放）。
6. 新增测试 `tests/test_bridge_file_write_approval.py`：
   - `test_file_write_without_approval_goes_pending`：无 approval_id 的 FILE_WRITE payload → 断言返回 pending 且 pending_actions 表新增行、无文件落盘；
   - `test_file_write_with_fake_approval_rejected`：`execute_approved("file_write", ...)` 传未存在于库中的 pid → 断言拒绝；
   - `test_file_write_approved_flow`：enqueue → decide(approve) → execute_approved → 文件落地 + result_summary 记录。
7. 验证：`pytest tests/test_bridge_file_write_approval.py tests/test_execution_bridge.py tests/test_pending_store.py -q`；手工冒烟 `OCOS_APPROVAL_MODE=auto` 下 `ocos goal exec "创建文件 /tmp/probe.txt 内容 hello"` → 应入待批而非直接写。
**回滚**：revert 单 commit（改动集中在 2 文件 3 处）。

### S1.2 API 网关认证 + 默认监听 127.0.0.1

**改动文件**：`ocos/interaction/api/server.py`、新增 `ocos/interaction/api/auth.py`；同步改客户端 4 处。

步骤：
1. `server.py:88`：`host="0.0.0.0"` → `os.environ.get("OCOS_API_HOST", "127.0.0.1")`。
2. 新建 `auth.py`：`AuthMiddleware`（纯 ASGI 中间件，不引第三方）——读取 `~/.ocos/config.json` 的 `api.token` 段；缺失时首次启动生成 `secrets.token_urlsafe(32)` 写回（chmod 0600），并在日志打印"Token 已生成于 ~/.ocos/config.json"。
3. 豁免清单：`/ocos/health`、`/`、`/ui`、`/ocos/openapi.json`、`/ocos/docs`、`/ocos/redoc`；其余全部要求 `Authorization: Bearer <token>`。
4. 显式关闭开关：`OCOS_API_AUTH_DISABLED=true` 时跳过校验，启动时 `logger.warning("API auth DISABLED — dev only")`。
5. **客户端同步**（R5-3）：
   - `ocos/interaction/tui.py`：API_BASE 请求统一带 Token（读取同一 config 段，封装 `get_api_token()` 于 auth.py 供复用）；
   - `ocos/external/server_manager.py` 健康检查仅打豁免端点（已打 `/ocos/health`，确认即可）；
   - `cli/commands/restart.py` 的 `_port_ready` 探测走 TCP 连接（不受影响，确认）；
   - 生产 hermes-gateway：在交付说明中标注需配置 Token（部署机侧操作）。
6. 新增测试 `tests/test_api_auth.py`：无 Token 401 / 错 Token 403 / 正确 Token 200 / health 豁免 / AUTH_DISABLED 跳过（5 用例，用 FastAPI TestClient）。
**回滚**：`OCOS_API_AUTH_DISABLED=true` 可运行时关闭；代码 revert 单 commit。

### S1.3 converse 数据面接入权限裁决

**改动文件**：`ocos/interaction/converse.py`（tool executor）、`ocos/execution/bridge.py`（可选辅助）。

步骤：
1. `make_default_tool_executor`（converse.py 内，USE| 动作执行器）：执行前调用 `PermissionGateway`（构造时注入；daemon/factory 已有 gateway 实例可传）。新增一个 `pre_check(capability, params) -> (allowed, reason)`：
   - `shell`：复用 bridge `_run_one` 的只读判定 + SandboxOps 黑白名单预检（不重复造轮子，抽 `bridge.preflight_shell(cmd)` 公共方法）；
   - `fs_read`：safe_roots + 敏感前缀检查（现有逻辑上移为可复用函数）。
2. DENY → 回注观察块如实告知（保持现有"拒绝如实回注防 LLM 重试"模式）；现有 USE| 协议本身已限只读白名单，本步是把"协议约束"升级为"网关约束"。
3. API 层（routes/converse.py 的 approvals approve/self-improve/goals-from-chat 三个写面端点）：各入口加 `PermissionGuard.check(action)`（复用 interaction/base.py 现成组件，与 S1.2 的 Token 认证叠加为两层）。
4. 测试 `tests/test_converse_gateway.py`：`USE|shell|{"command":"rm -rf /"}` → DENY 回注；`/ocos/approvals/{pid}/approve` 无 guard 上下文 → 仍放行（审批本身是人工动作）但落审计。
**回滚**：单 commit revert；网关异常时 fail-closed（拒执行不阻断回复主体）。

### S1.4 插件沙箱：AST 静态门 + hook 修复

**改动文件**：`ocos/platform/plugin_sandbox.py`、`plugin_loader.py`。

步骤：
1. **短期主修复（本迭代）**：`plugin_loader.load()` 入口新增 `_ast_forbidden_import_check(source)`——AST 扫描 Import/ImportFrom 节点，命中 `os/subprocess/socket/shutil/ctypes/importlib.sys` 等高危模块即拒绝加载（返回 LoadResult 错误码 `FORBIDDEN_IMPORT`），并写审计记录。此检查不依赖 meta_path，确定生效。
2. `_ImportBlocker` hook 修复：`execute()` 中创建 blocker 后真正 `sys.meta_path.insert(0, blocker)`（修复白皮书 P1-8 的"创建未安装"），finally 中已有 remove 保留；并在 sandbox 内执行前后断言 hook 存在（防回归）。注明局限：仅对新 import 生效（R5 认知一致）。
3. RestrictedPython/子进程隔离**不在本迭代**（中期项，立 TODO 注释即可——插件当前无生产消费者，风险已由 AST 门覆盖）。
4. 测试 `tests/test_plugin_sandbox_ast.py`：恶意插件（`import os; os.system(...)`）→ 拒绝加载 + 审计；良性插件 → 正常；execute 期间 sys.meta_path 含 blocker 的断言。
**回滚**：单 commit revert。

### S1.5 capability_reality 沙盒修复

**改动文件**：`ocos/capability_reality/adapter_fs.py`、`adapter_shell.py`。

步骤：
1. `adapter_fs.py:79` `_resolve`：`startswith` → `os.path.realpath()` 归一后 `Path(resolved).is_relative_to(Path(root).resolve())`（Python 3.9+，项目要求 ≥3.10）；任一 safe_root 命中即通过。补 `expanduser`+`realpath` 顺序注释（防 symlink 逃逸）。
2. `adapter_shell.py`：
   - 命令解析改 `shlex.split`，首词必须在 `OCOS_SHELL_WHITELIST`（新增环境变量，默认 `cat,ls,grep,head,tail,wc,find,git status,git log,git diff,python3 --version`，逗号分隔前缀匹配）；
   - 参数与整串拒绝元字符 `| && ; \` $() > <`（含 `OCOS_SHELL_ALLOW_PIPE=true` 显式放行管道的旁路开关）；
   - workdir 越界改为**报错**而非静默回落 safe_roots[0]（修复 W2 记录的静默改变用户意图问题）；
   - 危险黑名单保留为第二层。
3. **消费方回归**（R5-2）：grep `ShellAdapter` 消费方（tool/manager、adapter_discovery 注册链）逐一跑通；bridge 的 RUN 链路走 SandboxOps 确认不受影响（已核验：bridge.py 用 `operations/sandbox_ops`）。
4. 测试 `tests/test_sandbox_hardening.py`：`read("/home/laogao/Documents-evil/x")` → PermissionError；`read("/tmp/../etc/shadow")` → 拒绝；`echo $(cat /etc/shadow)` → 拒绝；`ls /tmp` → 通过；`a && b` → 拒绝。
**回滚**：单 commit revert（两文件内聚）。

### S1.6 emit API 错配 + RecoveryManager.shutdown 双定义

**改动文件**：`ocos/runtime/resource_manager.py`、`adaptive_control.py`、`runtime/recovery/recovery_manager.py`。

步骤：
1. 三处 `self._event_bus.emit(`（resource_manager.py:289/405/440、adaptive_control.py:525）→ `self._event_bus.publish(`；调用点加 `getattr(self._event_bus, "publish", None)` 守卫，None 则 logger.debug 跳过（兼容 None 注入的测试现状，与 R5-1 一致）。
2. `recovery_manager.py`：删除 :200 的第二个 `shutdown()` 定义，保留 :124 版本（含 `_save_ledger()`）；两版本 diff 逐行比对后合并（若第二版有新增逻辑，并入第一版）。
3. 测试：现有 `test_adaptive_control.py`/`test_resource_*`/`test_phase39_4/5` 全量回归 + 新增 `test_recovery_shutdown_persists_ledger`（shutdown 后 ledger.json 非空且含 shutdown 前记录）。

### S1.7（新增，R1）digital_world 沙盒白名单化

**改动文件**：`ocos/digital_world/sandbox.py`。

步骤：
1. 与 S1.5 同方案：`shlex.split` + `OCOS_DW_SHELL_WHITELIST`（默认只读命令前缀）+ 元字符拒绝；黑名单保留为第二层。
2. `sandbox_exec` 在 `OCOS_DW_DRY_RUN=1`（默认）下行为不变；dry_run=0 时新校验生效。
3. 测试 `tests/digital_world/test_sandbox_hardening.py`（沿用该目录现有测试风格）。

**Sprint 1 验收**：方案原标准 + 补充——① 7 项 P1 修复各有 ≥2 回归测试；② `pytest -q` 全量 ≥5287 基线且新增用例全绿；③ 手工渗透清单：无 Token 401、`FILE_WRITE|/tmp/probe` 入待批、`read(/home/laogao/Documents-evil)` 拒绝、恶意插件拒载；④ 渗透脚本 `scripts/security_probe.py`（新增，固化上述 4 项为可重复执行）。

---

## 三、Sprint 2 落地步骤：数据完整性与执行闭环（P1×2 + P2×11，5–7 天）

### S2.1 WorldValidator 自比较修复（P1）
1. `world_validator.py:118`：`existing.entity_type != existing.entity_type` → `existing.entity_type != observation.claimed_state.get("entity_type", existing.entity_type)`（对照 validate_against_model 的实参取观察侧类型；若观察类型载体是 claimed_relation/claimed_state 需按实际字段取，先写失败测试锁定）。
2. 测试：`test_world_validator_conflict.py`——同 entity_id 不同类型 Observation → CONFLICT；同类型 → 非 CONFLICT。
3. 注意：修复后 REJECT/CONFLICT 决策开始真实触发，需同步确认 `update_from_observation` 对非 ACCEPT 决策的既有分支行为（W7 记录：REJECT/QUARANTINE 声明未用——修复后首次激活，补决策分支处理或显式忽略+日志）。

### S2.2 审批默认值（按 R3 缩小切口）
1. 本 Sprint 只做：`ResidentRuntime.start()` 与 `ocos run` 启动横幅——`approval_disabled()` 为 True 时打印 `"⚠ OCOS_APPROVAL_MODE=auto：ASK 类动作将自动执行。生产环境建议 OCOS_APPROVAL_MODE=ask"`。
2. 文档：docs/ 部署章节补"生产必设 ask"。
3. 全局默认值切换移至 Sprint 3 收尾（S3.13）。

### S2.3 Experience Boundary 可配置阻断（R5-5 修正版）
1. `memory/experience/builder.py`：Boundary 违规时行为由新开关 `OCOS_EXPERIENCE_BOUNDARY_STRICT` 控制（默认 false=现状仅记 rejection_reason；true=拒绝入库并在 GateDecision 附 reason）。
2. 默认值切换并入 S3.13 统一评估（避免本 Sprint 误杀合法 INCOMPLETE 候选）。
3. 测试：两态各 1 用例。

### S2.4 Recall experience 链路修复
1. 推荐方案 A：`memory/hub.py` MemoryHub 增加 `experience` 属性——但 hub 并无 ExperienceStore（audit 确认 memory 包内无此 Store，experience 只是流水线阶段）。**修正方案的方案**：`recall.py` `_recall_experience` 改为遍历 `hub.episode` 中 `source in ("lesson",)` 且 tags 含 "synthesized" 的行（LessonsLearned 落库形态），或直接移除该子召回并在 docstring 标注"经验召回由 lesson 承担"。二选一，倾向后者（删死代码优于造假链路）。
2. 测试：recall 返回不含 experience 空源异常；lesson 行可被召回。

### S2.5 event_store 时间统一 + 生命周期归一（R5-4 修正版）
1. 写入侧：`event_store.py _persist` 改 `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")`。
2. **迁移脚本** `scripts/migrate_event_store_time.py`：扫描既有行，空格式（`YYYY-MM-DD HH:MM:SS`）按 UTC 补 T/.000000Z；本地 ISO 行按 Asia/Shanghai 转 UTC（写死偏移 +8，注释注明一次性假设）；执行前打印将迁移行数并要确认。
3. 生命周期：`mark_archived` 改为调用 `EventArchiveManager.apply_lifecycle` 的单事件等价路径（或在 EventStore 内补齐 `_events/_by_id` 同步更新），两条路径归一。
4. 测试：迁移脚本对三种格式样例行幂等；归档后 `find()` 与 `headers()` 一致。

### S2.6 Goal 双表 Migration v6
1. `storage/migrations.py` 新增 v6：`ALTER TABLE goal RENAME TO goal_legacy;`（幂等：先查 sqlite_master）。
2. 确认生产读写全走 `goals` 表（grep schema.py 的 `goal` 表消费方——audit 已确认 migrations v3 的 goal 表无人用）。
3. `goal_legacy` 保留一个版本周期，v7 删除（登记到 ROADMAP）。

### S2.7 恢复数据落 ~/.ocos/recovery/
1. `runtime/runtime_kernel.py`：`data_dir=checkpoint_dir=/tmp/ocos_checkpoints` → `os.environ.get("OCOS_RECOVERY_DIR", "~/.ocos/recovery")`（expanduser）。
2. 启动时 `os.makedirs(..., mode=0o700, exist_ok=True)`；首次迁移：若旧 /tmp 目录存在且有数据，打印迁移提示（不自动搬——/tmp 数据本就易失，直接丢弃可接受，日志说明即可）。
3. 快照/事件/账本/审批四子目录路径随 data_dir 联动（recovery_manager 已按 data_dir 拼，确认无独立硬编码）。

### S2.8 POST /ocos/goal 落库
1. `api/routes/goal.py`：构造 UserGoal 后调 `GoalStore(db).save(...)`（复用 cli/commands/goal.py 的 `cmd_goal_create` 落库参数集：origin_level=HUMAN、caller="api"、status=PENDING），返回 `goal_id`；PermissionGuard 校验保留。
2. 集成测试：POST → 200 + goal_id → `GoalStore.load(goal_id)` 命中。

### S2.9 日志脱敏
1. `ocos/logging/formatter.py` JSONFormatter：新增 `_redact(extra)`——对键名含 `content/message/payload/user_message` 的值 >50 字符时截断为 `prefix[:50]...[REDACTED:{len}]`；`OCOS_LOG_REDACT=false` 可关（默认开）。
2. `ocos/event/__init__.py` `record_trace`：对 summary 做 `content[:50]` 截断（同开关）。
3. 测试：含 200 字用户消息的日志行 grep 不到原文 51+ 字符子串。

### S2.10 Audit 规则字段补齐
1. `platform/audit_engine.py` `_on_governance_event/_on_system_event`：details 补 `governance_audit_id`（governance 事件落审计后回填自身 id）与 `related_halt_audit_id`（emergency.halt 事件的关联审计 id）。
2. 若实现代价高：备选方案——两条规则标注 deprecated 并从 DEFAULT_AUDIT_RULES 移除（移除也消除"假阴性"误导）。实现前先评估，二选一。

### S2.11 master_agent AccessDecision 顶部导入（P1）
1. `master_agent.py`：模块级 `from ocos.security.manager import AccessDecision`（若引发循环导入则改用字符串常量比较——AccessDecision 是枚举，可 `AccessDecision = getattr(...)` 延迟绑定并加注释；先试直接 import）。
2. 顺带统一语义：`check_access` 未注入分支由"未注入=ALLOW"改为"未注入=DENY + warning"（fail-closed，与 :2095 异常分支对齐）——**行为变更**，在测试中固化。
3. 测试：不注入 security_manager 调 check_access/sanitize_input → 不 NameError 且返回 DENY。

### S2.12（新增，R1）health_examination 器官注册表修正
1. `health_model.py:59-84` OCOS_ORGANS：`ocos.self_model`→`ocos.self`、`ocos.continuity`→`ocos.cognitive_continuity`、`ocos.os`→`ocos.os_v1`；required_exports 改为各包**真实存在**的导出符号（以白皮书 2.14 各组导出清单为准，如 `ocos.capability`→`CapabilityRegistry`、`ocos.runtime`→`RuntimeKernel`）。
2. structural_examiner 结论输出加免责行："本体检器仅校验模块结构与导出存在性，不代表运行时健康"。
3. 测试：`StructuralExaminer.examine` 对真实仓库运行，0 个 MISSING（路径存在性）；exports 命中率 ≥ 预期值。

### S2.13（新增，R1/R6）life_cycle_orchestrator 复核与守卫
1. 复核（R6）：实测 `_tick_idle` 全路径——`needs_sleep/tick/reset` 对 CognitiveAttentionController 的参数兼容性；写一条集成测试锁定现状（若真有问题再修，不预设）。
2. 防御加固：`_tick_idle/_tick_sleep` 对 `attention.*` 调用加 `hasattr` 守卫 + logger.warning（消除"恒 ERROR 被吞"的不可观测面）。

### S2.14（新增，R2）学习闭环三连修复
1. `agent_runtime.py:1560-1575` `_extract_beliefs`：判定条件 `exp.outcome in ("success","great","good")` → `in ("success","great","good","completed")`（与 ExperienceStore.record 写入值对齐）；补注释指向 :1411。
2. `capability/experience_memory.py get_stats` 返回结构**不动**（多处消费），改 `capability/outcome_evaluation.py:128`：`stats.get("count")` → `stats.get("total")`。
3. `capability/calibration_store.py:75-81`：移除对不存在方法的调用；改为更新本地累计并返回 `applied=False, reason="reliability backend not wired"`（诚实降级），删除假 `applied=True` 路径。
4. 测试：三处各 1 用例（信念提取对 completed 经验生效；reliability 随历史数变化；calibration 返回 applied=False 不再假成功）。

### S2.15（新增，R2）attention/focus.py TypeError 修复
1. `attention/focus.py:131-139`：`self._update_focus(focus_type=..., focus_target=..., attention_scores=...)` → 按实际签名 `(focus_type, target, score, ...)` 传参：`self._update_focus(focus_type=ft, target=observed_target, score=composite, attention_scores=...)`。
2. 测试：`test_attention_focus.py` 补 `test_process_observation_no_typeerror`（composite≥0.3 观察 → 正常返回 FocusState）。

**Sprint 2 验收**：① `validate_against_model` 冲突场景返回 CONFLICT；② 无审批 FILE_WRITE 100% 入待批（承接 S1.1）；③ 学习闭环三连回归测试绿；④ 全量 ≥5287 + 新增约 30 用例。

---

## 四、Sprint 3 落地步骤：生产可用性与健壮性（P2×10 + P3×6，7–10 天）

### S3.1（降级，R4）管线范围收缩
本迭代仅做 S3.10（PipelineError 兜底）与 SAFE_MODE 最小接线；Stage 化迁移立 `docs/phase63_candidate.md` 立项说明（含方案原文 3.1 的两阶段设计，作为后续输入）。

### S3.2 权限网关生产接线
1. `bridge.process()` 与 `execute_dag_task()` 入口统一 `PermissionGateway.evaluate()`（构造时注入；未注入时 fail-closed 拒绝 + warning，对齐 execution_bridge 的 GAP-P0-3 语义）。
2. 与 S1.3 联动验证：converse/CLI/agent_runtime 三路径动作全部产生 PermissionTrace。
3. `REGISTERED_CAPABILITIES` 补注册 `api.get/web.post/database.update/process.start` 四项（W4 P4-4 漂移）。
4. 测试：三入口各 1 条 trace 断言；未注册能力默认拒绝。

### S3.3 配置管理统一（渐进）
1. 新建 `ocos/config/__init__.py`：`OCOSConfig` 单例（线程安全），`get(key, default)` 三层优先级 env > ~/.ocos/config.json > 内置默认；内置 `DEFAULTS` dict 集中本白皮书 §6.1 的 21 个 OCOS_* 变量。
2. 本 Sprint 迁移 3 个模块作为样板：`interaction/api/server.py`（host/port/token）、`execution/pending.py`（approval mode）、`runtime/runtime_kernel.py`（recovery dir）。
3. `.env` 加载：**不做**（R5 延伸——.env 从未生效且 example 是 OpenClaw 模板；补 README 说明即止，避免引入 dotenv 新语义）。
4. pydantic Schema 校验：config.json 的 `llm/llm_fallback/api` 段建 model，启动时校验失败 warning 不阻断。

### S3.4 版本一致性
1. pyproject `1.0.0` 为准；`scripts/check_version_consistency.py`：比对 pyproject vs `ocos.__version__` vs requirements.lock editable 行；进 `make gate`。

### S3.5 Monitoring 接入生产
1. `daemon/factory.py build_health_loop`：实例化 `MonitoringManager`（端口 `OCOS_MONITORING_PORT` 默认 9090）并 `start_http()`；注册 5 个核心指标：`ocos_tick_total`(counter)、`ocos_goal_active`(gauge)、`ocos_llm_calls_total`(counter)、`ocos_memory_episodes_total`(gauge)、`ocos_execution_pending`(gauge)。
2. daemon tick 循环埋点（heartbeat 处 +1 tick；bridge LLM 调用处 +1）。
3. 顺手修 `ococ_up`→`ocos_up` 拼写与 histogram 分位实现（W10 P3-17）。
4. 验收：`ocos run` 后 `curl 127.0.0.1:9090/metrics` 见 5 指标。

### S3.6 REPL DB 路径统一
1. `interaction/repl/shell.py:34`：`os.environ.get("OCOS_DB_PATH", "ocos.db")` → `from ocos.interaction.cli.paths import resolve_db_path`。
2. `interaction/context.py` 缺省 `:memory:` 的调用方检查：REPL/main 传 resolve 结果。
3. 测试：REPL 会话写的行在 CLI `ocos status` 可见。

### S3.7 线程安全（text_generator 代理变量）
1. `OpenaiProvider.generate`：删除 pop/restore 全局 env 的做法——构造时一次性读取代理配置存实例属性，请求时以 `httpx.Client(proxy=...)` 传参（httpx 原生支持），不再动进程 env。
2. `bridge.py` 内同类 pop/restore（:800-827,1011-1026）同步改法。
3. 测试：并发 10 线程 generate（mock provider）后 `os.environ` 代理键无变化。

### S3.8 query_db 去硬编码
1. `bridge.py _handler_query_db`：`~/.ocos/ocos.db` → `self._db_path`（构造已有）；无可信 db_path 时拒绝。

### S3.9（新增，R2）_tick_errors 自增
1. 各 `_tick_step_*` 的 except 分支统一 `self._tick_errors += 1`（11 个 step 方法收口到一个 `_note_step_error(step_name, exc)` 辅助）。
2. 测试：注入失败 step → get_stability_report error_rate>0、drift_flags 触发。

### S3.10（新增，R2/R4）PipelineError 兜底 + SAFE_MODE 最小接线
1. `runtime_kernel.tick_loop`：包裹 `pipeline.execute_tick`，捕获 PipelineError → logger.error + lifecycle.enter_degraded() + 连续 3 次 enter_safe_mode()（RuntimeState 转移表已允许 RUNNING→DEGRADED→SAFE_MODE）。
2. SAFE_MODE 行为最小实现：仅执行 Stage⑧ checkpoint + agent_driver 跳过；连续 5 tick 正常后 recover()（转移表 SAFE_MODE 仅到 SHUTDOWN——**需先扩转移表 SAFE_MODE→{RUNNING}**，一步 schema 修改 + 测试）。
3. 测试：mock stage 抛错 → tick_loop 不死、状态降级、恢复路径。

### S3.11（新增，R2）runtime_id 固定 + 恢复矢量回灌
1. `runtime_kernel.py`：runtime_id 支持 `OCOS_RUNTIME_ID` 环境变量，daemon 传 `agent_id` 同值（稳定跨重启）→ CheckpointEngine.latest_checkpoint 可命中。
2. RestoreResult 回灌最小集：`active_goal_ids` → 校验 goals 表存在性后 logger.info（本迭代只做**观测回灌**，不做状态注入——注入涉及 goal 状态机，风险高）；pending_approvals 数量 >0 时启动横幅提示。
3. 测试：两次 boot 同 runtime_id → checkpoint 命中；快照含 pending → 启动日志提示。

### S3.12（新增，R2）sequence 原子化 + schema 去重
1. `storage/event_store.py _next_sequence`：改 `UPDATE sqlite_sequence SET seq=seq+1 WHERE name='event_store' RETURNING seq`（SQLite 3.35+；项目环境核实）或 `INSERT ... ON CONFLICT` 补偿；至少加 `BEGIN IMMEDIATE` 事务包裹。
2. `kernel/event_schema.py`：删除 :180-191 与 :232-268 中 GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 的重复键（保留字段更全的一版）。
3. 测试：双线程并发 append 1000 条 → sequence 无重复无跳号；GOAL_SET 缺 description 事件被拒。

### S3.13 收尾：一次性默认值切换（R3 第三步）
1. 全量回归后：`OCOS_APPROVAL_MODE` 默认 auto→ask、`OCOS_EXPERIENCE_BOUNDARY_STRICT` 默认 false→true（若 S2.3 验证无误杀）。
2. 同步更新 e2e 预期（tests/test_e2e、生产验证脚本）、PRODUCTION_VALIDATION 报告补一章"行为变更说明"。
3. 回滚开关：两个环境变量改回旧值即可，代码不 revert。

**Sprint 3 验收**（修正后）：① `/metrics` 可访问含 5 指标；② 日志 grep 不到 >50 字符用户消息原文；③ 配置改 env 不改代码生效（3 个样板模块）；④ PipelineError 注入后 daemon 不死；⑤ 全量测试绿。

---

## 五、Sprint 4 落地步骤：架构治理与死代码清理（5–7 天）

### S4.1 双 EventBus 统一
1. `ocos/event/` 整体重命名 `ocos/perception_bus/`（git mv 保留历史）；`agent_runtime.py:174` 等 3 处 import 更新；顶层无 shim（内部包，无外部用户）。
2. `ocos/events/__init__.py` 补 `__all__`；`docs/` 架构图同步。
3. 测试：`grep -rn "from ocos.event import" ocos/` 零命中；全量回归。

### S4.2 占位端点 501 化
1. memory/belief/trace 三组路由返回 `501 + {"note": "not implemented"}`（替代 200 空结果）；OpenAPI 注解 deprecated。
2. CLI `trace show` 同步返回明确"未实现"（退出码 2）。

### S4.3 死代码清理（含 R1 补入项）
1. `master_agent.py:1730` 第一版 search_knowledge（被 :1804 遮蔽）→ 删。
2. `master_agent.py:879-891` `_recall_and_record` 空实现 → 删 + 调用点移除。
3. `orchestration/engine.py:346` `record.to_dict()` → ExecutionAudit 补 `to_dict()`（修优于删——该模块若未来接线）；`agent_orchestration_autonomous.py` `_monitor_running` 伪造成功段 → 诚实失败（任务置 failed + 理由），或整体标废弃（上电方案 W5 已列废弃候选，二选一：**推荐标废弃**，文件头加 DeprecationWarning）。
4. `digital_world/db_ops.py` → 文件头标"占位，v1.2 删除候选"。
5. 每处清理独立 commit，删除前 `grep` 确认零引用。

### S4.4 Scope Freeze 强化
1. `os_v1/freeze.py`：freeze() 时对 12 个 ABI_MODULES 逐个 `inspect.getmembers` 公开签名序列化 + SHA-256 入 manifest；新增 `verify()` 启动校验，不一致 `FROZEN_VIOLATION` warning（raise 由 `OCOS_FREEZE_STRICT` 控制，默认 warn）。
2. `scripts/verify_freeze.py` 进 `make gate`。
3. 注意：首次启用会有存量 diff——先基线化（以当前代码生成首份签名），后续变更才比对。

### S4.5 测试基础设施补强
1. Sprint 1/2 全部修复项回归测试清点（目标 ≥2 用例/项，约 40+ 用例）。
2. `tests/integration/test_security_chain.py`：用户输入→PermissionGateway→DecisionBridge→沙盒 全链 e2e（正常放行 + 三类拦截各 1）。
3. pytest `--strict-markers` 接入（清理 test_phase52 的 2 处 psutil skipif 改为显式 marker）。

**Sprint 4 验收**（修正后）：① 双 EventBus 旧路径零命中；② verify_freeze 进 gate 且绿；③ 死代码净减 ≥200 行；④ security_chain e2e 绿。

---

## 六、执行编排与提交纪律

- **提交节奏**（按工作流偏好逐项编号）：每 Sx.y 一 commit，message 格式 `fix(S1.1): FILE_WRITE 强制审批 — 白皮书 P1-1`；每 Sprint 结束打 tag `sprint1-security` 等。
- **每项完成即重启验证**：改代码必须重启 server/daemon 后再手工验证（进程旧代码是历史头号"修了没生效"原因）。
- **全局回滚单元**：每项改动集中且可单独 revert；S3.13 两个默认值切换保留环境变量回滚开关。
- **工期复核**：Sprint 1 增至 7 项 P1 后维持 3–5 天可行（1.4 中期项已移出）；Sprint 2 增 4 项后 5–7 天偏紧，建议 7 天；Sprint 3 因管线降级实际减负，7–10 天可保。总工期 **4–5 周不变**。
- **遗留至下一版本**（本方案明确不做，防范围蔓延）：TickPipeline 完整 Stage 化（Phase 63 候选）、持久化四套物理合并（仅定义 PersistenceFacade Protocol）、RestrictedPython/WASM 插件沙箱、`_CHAT_SESSIONS` 无淘汰等 W3 P2 项、Phase 53 主动交互管线接线。
