# GAP P0-P2 升级总结：从"器官图谱"到"活体内核"

日期：2026-08-30
范围：docs/OCOS_GAP_REPAIR_PLAN.md §P0（正确性与安全 4 项）+ §P1（点亮孤岛器官 3 项）+ §P2（持久化与占位补齐 5 项）
性质：升级总结（P3 收敛与清理按用户决定搁置，不在本次范围）
验证基线：全量 tests/ + ocos/tests/ 约 5230 passed，唯一失败 ocos/tests/test_organ_client.py::test_network_error_raises（基线既有网络超时，与本次无关）

## 1. 本质判断

本次升级不是"新增能力"，而是把已长出的器官接上真实生命管线。
此前状态：记忆库有接口但可能静默失败；感知产出进不了世界模型；决策走占位链；
崩溃无人知晓、无法复活。本次 12 个功能提交（P0×4、P1×3、P2×5）贯通四条生命线：
记忆全系落盘、感知有真实入口、决策走真实链、崩溃能真实复活。

## 2. P0 诚实性修复 — ✅（4/4）

核心问题：系统"假装有功能"。全部改为真实行为。

| 项 | 目标 | 状态 | 证据 |
|---|---|---|---|
| P0-1 | 身份快照静默失败修复 | ✅ | save_snapshot/load_snapshot 真实读写，keep 10，Phase 34E 消费 |
| P0-2 | dream 持久化 | ✅ | MemoryHub 唯一 store 源 + attach_memory_hub 回填 |
| P0-3 | ExecutionBridge 权限检查 | ✅ | PermissionGateway 注入，fail-closed（无网关即拒绝）+ import-rule allowlist 修复 |
| P0-4 | plugin sandbox 诚实失败 | ✅ | 无实例不假成功，SandboxRunner validate 真实 import 探测 |

## 3. P1 点亮孤岛器官 — ✅（3/3）

| 项 | 目标 | 状态 | 证据 |
|---|---|---|---|
| P1-1 | 决策链真实化 | ✅ | DecisionPipeline 接真实 Phase 43 链（ContextBuilder→OptionGenerator→Risk+Value→Validator→Tracer）+ DecisionValidator 治理 |
| P1-2 | daemon 稳态健康监控 | ✅ | HealthLoop 4 项（记忆条数/goal 栈深/决策失败率/WM 占用）→ CognitiveExaminer 体检 → AlertManager 告警 + Homeostasis 复用；E2E 膨胀落盘测试 |
| P1-3 | 感知入口桥接 | ✅ | PerceptionPipeline：FileSensor Observation → WorldStore.update_from_observation，entity/state resolvers，状态变化触发因果推断 |

## 4. P2 持久化与复活 — ✅（5/5）

| 项 | 目标 | 状态 | 证据 |
|---|---|---|---|
| P2-1 | 知识落库 | ✅ | KnowledgeRegistry→SemanticStore 持久化镜像（UPSERT） |
| P2-2 | 占位接线 | ✅ | runtime/stages 4 个占位补齐 |
| P2-3 | 事件记忆 SQLite 化 | ✅ | append-only 落盘 + archive 真实标记 + 删 CR55-03 假声称 |
| P2-4 | 智慧与个性化落盘 | ✅ | wisdom_store SQLite + personalization FORMAL/BOLD 补实现 |
| P2-5 | living_test 真实化 | ✅ | scripts/resurrection_drill.py 全真实组件演练 10/10（记忆 3/3、身份 2/2、快照 2/2、目标/报告 3/3） |

## 5. 演练逼出的生产缺陷（P2-5 顺带修复）

1. **行工厂污染**：ocos/snapshot/manager.py 与 ocos/goal/store.py 的 `conn.row_factory = None`
   把共享连接池连接改为 tuple 模式，污染同 db 其他 store（identity_store 等）的 dict(row) 查询
   → 已删除，共享池纪律注释在案。
2. **建表缺口**：snapshots 表、goals 表此前仅测试夹具创建，生产路径缺失
   → 两处 _conn() 内 CREATE TABLE IF NOT EXISTS 自愈建表。

## 6. 遗留边界（不在本次范围，已记录）

| 项 | 状态 | 说明 |
|---|---|---|
| P3 收敛与清理（8 组去重 + 附带清理） | ⏸ 用户决定搁置 | 纯重构删码，后续单独分支执行 |
| attention 既有告警噪声 | ⚠ 已记 findings | CognitiveAttentionController 缺 current_focus 事件，tick 内既有缺陷 |
| organ_client 网络超时测试 | ⚠ 基线既有 | 与本次无关，未触碰 |

## 7. commit 链（新 → 旧）

ac598d2 docs 执行记录表补登（§0 + P0-1~4 + P1-1~3 + P2-1~5）
333675b GAP-P2-5 复活演练 + 自愈建表 + 行工厂修复
1268495 GAP-P2-4 wisdom 落盘 + personalization 补实现
4b11c51 GAP-P2-3 event_memory SQLite 化
415f4c8 GAP-P2-2 runtime/stages 占位接线
6a63222 GAP-P2-1 SemanticStore 持久化镜像
1ca4884 GAP-P1-3 PerceptionPipeline 桥接
8acce0f GAP-P1-2 HealthLoop 稳态监控
944c994 GAP-P1-1 DecisionPipeline 真实链
54fcf6e GAP-P0-4 sandbox 诚实失败
3b4a571 GAP-P0-3 权限网关
b21512b GAP-P0-2 dream 持久化
e6c1776 GAP-P0-1 身份快照修复
