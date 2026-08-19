# OpenTale 代码级实现报告

## 1. 报告范围

本报告基于当前项目代码的只读审查生成，不以既有架构文档为依据，不包含推测性的“理想设计”，只描述当前代码真实实现状态。

审查范围包括：

- 入口层
- 核心生成链路
- pipeline 拆分状态
- domain 模型拆分状态
- compiler / writer / governance / state / evaluation / repository / shell 实现状态
- 测试覆盖面
- 当前发布阻塞项

项目路径：

- `/home/laogao/Documents/trae_projects/1234/novel_writing_system`

## 2. 当前总体判断

当前项目已经从“单体写作系统”进入“重构过渡态”。

这意味着：

- 新架构骨架已经落地一大部分
- 新模块已经开始接管一部分职责
- 但真正的生产能力中心仍主要保留在旧内核中

一句话判断：

```text
这是一个“新旧双轨并存”的系统：
外层结构已重构，核心能力尚未完全迁移。
```

## 3. 当前代码规模与结构

### 3.1 核心文件规模

当前关键文件行数：

- [opentale/app/service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/service.py:1) `3615` 行
- [opentale/app/export.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/export.py:1) `720` 行
- [opentale/cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1) `340` 行
- [opentale/app/review.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/review.py:1) `266` 行
- [opentale/app/book_review.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/book_review.py:1) `143` 行
- [opentale/app/models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/models.py:1) `73` 行

### 3.2 现有主要模块族

已经存在的结构分层：

- `pipeline/`
- `domain/`
- `compiler/`
- `writer/`
- `governance/`
- `state/`
- `evaluation/`
- `repository/`
- `execution/`
- `shell/`
- `polish/`

这说明项目已经脱离“纯单文件单模块”状态，正在向目标分层架构迁移。

## 4. 入口层实现状态

### 4.1 CLI

[opentale/cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1) 仍是主入口之一，已经具备以下特征：

- 保留原有 `generate / resume / rewrite-chapter / list-projects / verify-package` 命令
- 已接入 `--mode`
- `GenerationRequest` 已带 `execution_mode`

当前已暴露的 execution mode：

- `full`
- `fast_draft`
- `fast_redraft`
- `skeleton`
- `deterministic`

判断：

- `Stage 2` 的 CLI 用户可见落点已经部分完成
- 但 CLI 仍主要依赖旧内核调用链，而不是完全依赖新模块独立组合

### 4.2 API

[app.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/app.py:1) 规模较小，仍充当 FastAPI 服务壳。

判断：

- API 不是当前主要复杂度来源
- 主要风险不在 API 层，而在底层 orchestration

## 5. 核心生成链路实现状态

### 5.1 `AutonomousNovelSystem` 已降级为 facade，但未完全瘦身

[opentale/app/service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/service.py:1) 当前已出现重要变化：

- `generate()` 已调用 `GenerateNovelPipeline`
- `resume()` 已调用 `ResumeProjectPipeline`
- `rewrite_chapter()` 已调用 `RewriteFlowPipeline`
- `ensure_export_ready()` 已调用 `PublishFlowPipeline`

这说明：

- `Stage 1` 已部分完成
- 主流程入口已从单体方法改为 pipeline 调度

但同一文件中仍保留大量旧私有实现，例如：

- `_normalize_request`
- `_generate_outline`
- `_generate_world`
- `_generate_characters`
- `_generate_chapter_specs`
- `_draft_chapters`
- `_repair_book_if_needed`
- `_build_story_bible`
- `_build_memory_snapshot`
- `_build_dependency_graph`

判断：

- 现在的 `service.py` 是“已 facade 化，但仍承担旧实现仓库角色”
- 还没有完成“pipeline 自包含”

### 5.2 当前真实生产主链仍以旧实现为主

虽然 `pipeline/` 已存在，但以 [generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1) 为例，其主要特点是：

- 负责 orchestration
- 但核心步骤仍大量委托回 `system._xxx()` 私有方法

代码中直接体现为：

- `system._normalize_request(...)`
- `system._generate_outline(...)`
- `system._generate_world(...)`
- `system._generate_characters(...)`
- `system._generate_chapter_specs(...)`
- `system._draft_chapters(...)`
- `system._repair_book_if_needed(...)`
- `system._build_memory_snapshot(...)`

判断：

- pipeline 已经建立
- 但核心业务实现尚未真正迁出 `service.py`

## 6. Pipeline 实现状态

### 6.1 已存在模块

当前已存在：

- [pipeline/generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1)
- [pipeline/resume_project.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/resume_project.py:1)
- [pipeline/publish_flow.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/publish_flow.py:1)

### 6.2 成熟度判断

`GenerateNovelPipeline` 当前不是“完整自足 pipeline”，而是“已抽离的编排层”。

其完成度大致是：

- 编排层：已落地
- 依赖注入：已落地
- mode 分支：已接入
- checkpoint：已接入一部分
- 底层实现迁移：未完成

当前阶段判断：

```text
Pipeline 层：半完成
```

## 7. Domain 模型实现状态

### 7.1 `models.py` 已成功降级为兼容层

[opentale/app/models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/models.py:1) 当前仅做 re-export。

它从：

- 过去的“全部模型定义中心”

转成：

- 当前的“向后兼容导出层”

这说明 `Stage 4` 的模型拆分已经完成关键一步。

### 7.2 现有 domain 模块

当前已拆出的主要模型模块：

- [domain/enums.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/enums.py:1)
- [domain/requests.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/requests.py:1)
- [domain/story_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/story_models.py:1)
- [domain/chapter_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/chapter_models.py:1)
- [domain/memory_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/memory_models.py:1)
- [domain/bible_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/bible_models.py:1)
- [domain/package_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/package_models.py:1)

判断：

- 模型拆分已经不是规划，而是代码现实
- 但新领域对象还没有完全成为主链唯一对象

## 8. ExecutionMode 与 fast-path 实现状态

### 8.1 请求模型已接入

[domain/requests.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/requests.py:1) 中：

- `GenerationRequest` 已包含 `execution_mode`
- `RewriteRequest` 已包含 `execution_mode`

### 8.2 CLI 已接入 mode

[cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1) 中 `generate` 和 `rewrite-chapter` 都已暴露 `--mode`

### 8.3 pipeline 已做 mode 分支

[generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1) 中已出现：

- `FAST_DRAFT`
- `SKELETON`
- `DETERMINISTIC`

判断：

- `Stage 2` 已有真实落地
- 但 mode 的行为仍偏轻量，更多是“跳过某些步骤”，不等于完整 fast-path 引擎

## 9. Checkpoint 实现状态

### 9.1 已存在 checkpoint 模块

存在：

- [opentale/app/checkpoint/__init__.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/checkpoint/__init__.py:1)

### 9.2 已被 generate pipeline 使用

[generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1) 中已经创建 `CheckpointStore`

### 9.3 成熟度判断

当前 checkpoint 更像“开始记录阶段信息”，还不是成熟缓存系统。

判断：

```text
Checkpoint：有实现，但未形成完整缓存/恢复能力
```

## 10. Governance 实现状态

### 10.1 已存在模块

当前存在：

- [governance/change_request_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/change_request_service.py:1)
- [governance/feedback_bus.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/feedback_bus.py:1)
- [governance/recovery_policy.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/recovery_policy.py:1)
- [governance/story_lock.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/story_lock.py:1)

### 10.2 变更分级已实现第一版

[change_request_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/change_request_service.py:1) 已定义：

- `LANGUAGE`
- `CONTINUITY`
- `STORY`

并实现关键字分类。

### 10.3 RecoveryPolicy 已实现第一版决策

[recovery_policy.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/recovery_policy.py:1) 已具备：

- `RecoveryBudget`
- `LOCAL_PATCH`
- `LOCAL_RECOMPILE`
- `CHAPTER_REPLAN`
- `VOLUME_REPLAN`
- `STORY_REVISION`
- `DEFER`

判断：

- 治理系统的概念已经进入代码
- 但仍偏“规则级骨架”
- 尚未看到它完整接入主生成/重写链路的深度证据

## 11. Compiler 实现状态

### 11.1 已存在合同引擎

当前存在：

- [compiler/contract_engine.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/contract_engine.py:1)
- [compiler/dependency_analyzer.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/dependency_analyzer.py:1)
- [compiler/invalidation_planner.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/invalidation_planner.py:1)
- [compiler/models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/models.py:1)

### 11.2 当前 `ContractEngine` 能力判断

[contract_engine.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/contract_engine.py:1) 目前已经能：

- 读取目标 `ChapterPackage`
- 读取基本 preconditions
- 合并 StoryLock 保护项
- 生成 `ExecutionContract`
- 输出 `CompileResult`

但它目前仍有明显限制：

- 依赖输入仍较浅
- 主要围绕 `ChapterSpec` 级字段拼接
- 没有成熟的增量编译图
- 没有复杂 invalidation
- 没有真正惰性编译链路

判断：

```text
ContractEngine：v1 骨架已成，尚未达到成熟编译器级别
```

## 12. Writer 实现状态

### 12.1 已存在 WriterExecutor

当前存在：

- [writer/writer_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/writer_executor.py:1)
- [writer/scene_decomposer.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/scene_decomposer.py:1)
- [writer/contract_verifier.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/contract_verifier.py:1)
- [writer/local_repair.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/local_repair.py:1)
- [writer/models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/models.py:1)

### 12.2 当前能力判断

[writer_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/writer_executor.py:1) 已实现：

- scene decomposition
- content assembly
- contract verification
- local repair

但默认生成模式仍是：

- 如果没有注入 `llm_fn`
- 则输出确定性占位文本

这意味着：

- WriterExecutor 的结构已经搭起来了
- 但它还不是当前系统的高质量正文生产主引擎

判断：

```text
WriterExecutor：结构上已成立，能力上仍偏占位/第一版
```

## 13. State 层实现状态

### 13.1 已显式实现 StateAdapter

[state/state_adapter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/state_adapter.py:1) 已经把蓝图里那个关键桥接层写出来了。

它当前承担：

- 旧文件系统状态读取
- `ProjectMemorySnapshot` 兼容桥接
- `ChapterDraft` 兼容桥接
- 后续向 `CanonLedger` 切换的适配点

### 13.2 已存在 Canon 与 Query 层

存在：

- [state/canon_ledger.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/canon_ledger.py:1)
- [state/story_ir_query.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/story_ir_query.py:1)

### 13.3 当前成熟度判断

目前 State 层已经不是空白，但仍处于：

- 接口建立完成
- 数据源桥接开始实现
- 正式主链切换尚未完成

判断：

```text
State 层：已进入接管前夜，但尚未成为唯一事实源
```

更精确地说：

- [state_adapter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/state_adapter.py:1) 已同时支持旧文件系统数据源和新 `CanonLedger` 数据源
- 代码中已提供 `use_canon_ledger()` 切换入口
- 这意味着主链切换成本主要是“注入与接线”，不是再次重构接口

## 14. Repository / Export 实现状态

### 14.1 旧 `export.py` 仍然很重

[export.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/export.py:1) 仍有 `720` 行，仍承担大量职责。

### 14.2 新 repository 体系已开始出现

存在：

- [repository/project_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/project_repository.py:1)
- [repository/artifact_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/artifact_repository.py:1)
- [repository/index_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/index_repository.py:1)
- [repository/package_exporter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/package_exporter.py:1)

### 14.3 成熟度判断

以 [package_exporter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/package_exporter.py:1) 为例，它已经开始把 manuscript 导出到新 artifact tree，但导出深度还有限：

- 已有 `story_package`
- 已有 `chapter drafts`
- 已有 `evaluation`
- 已有 `manifest`

但距离完整的目标产物树还差：

- contracts
- canon_state
- governance logs
- checkpoints metadata
- richer chapter package artifacts

判断：

```text
Repository / Export：已开工，未收口
```

## 15. Evaluation 实现状态

### 15.1 已存在新评价层

存在：

- [evaluation/chapter_evaluator.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/chapter_evaluator.py:1)
- [evaluation/book_evaluator.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/book_evaluator.py:1)
- [evaluation/quality_gate.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/quality_gate.py:1)

### 15.2 当前实现深度

[quality_gate.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/quality_gate.py:1) 已支持：

- chapter gate
- volume gate placeholder
- book gate
- publish gate

但明显仍是过渡态：

- volume gate 还是 placeholder
- publish gate 仍是简化版
- 与旧 `review.py` / `book_review.py` 的完全替换尚未完成

判断：

```text
Evaluation：过渡可用，未完成最终收口
```

## 16. ReadService / Tool / Shell 实现状态

### 16.1 ReadService 已实现，但仍依附旧 export 结构

[execution/read_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/read_service.py:1) 当前已经可读：

- project manifest
- outline
- story bible
- chapter spec
- chapter draft
- book review
- project health

但内部仍大量调用：

- `load_project_package(...)`
- `project_overview(...)`
- `verify_project_package(...)`

也就是：

- 它是“统一读接口”
- 但底层仍依赖旧 package loader

### 16.2 ToolRegistry 已有

[execution/tool_registry.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tool_registry.py:1) 已是可用实现，不是空壳。

### 16.3 Shell 已能运行，但智能度较浅

存在：

- [shell/agent.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/agent.py:1)
- [shell/intent.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/intent.py:1)
- [shell/planner.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/planner.py:1)
- [shell/plan_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/plan_executor.py:1)
- [shell/session_store.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/session_store.py:1)

当前实现特点：

- `IntentRouter` 主要是规则匹配
- `Planner` 主要是规则分解
- `Shell` 主要是 REPL 和工具调用壳

判断：

```text
V3.2 外壳已长出来，但仍是规则驱动的早期版本
```

## 17. 测试实现状态

### 17.1 测试规模

当前更可靠的口径应以 pytest 实际运行结果为准：

- `195 passed`

如果按文件内 `def test_` / `async def test_` 签名粗略统计，则是 `200+` 量级，但该口径会受到共享辅助函数和文件组织方式影响，不应当作最终测试规模数字。

### 17.2 测试结构

保留的旧测试：

- [tests/test_clean_pipeline.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_clean_pipeline.py:1)
- [tests/test_cli_clean.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_cli_clean.py:1)
- [tests/test_api_clean.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_api_clean.py:1)

新增 pipeline 测试：

- `tests/pipeline/test_generate.py`
- `tests/pipeline/test_writer.py`
- `tests/pipeline/test_compiler.py`
- `tests/pipeline/test_governance.py`
- `tests/pipeline/test_execution.py`
- `tests/pipeline/test_repository.py`
- `tests/pipeline/test_evaluation.py`
- `tests/pipeline/test_shell.py`
- `tests/pipeline/test_canon_state.py`
- `tests/pipeline/test_export.py`
- `tests/pipeline/test_repair.py`
- `tests/pipeline/test_fallback.py`
- `tests/pipeline/test_long_form.py`

### 17.3 判断

测试层明显强于之前阶段，说明：

- 不再只是“写完代码再说”
- 重构已经有模块级保护网

但需要注意：

- 大量旧测试仍然对旧内核行为强绑定
- 新旧双轨并存期间，测试通过不等于新链路完全接管

## 18. 当前所处阶段映射

按当前代码现实，可大致映射为：

- `Stage 1`：部分完成
- `Stage 1.5`：已开始，且测试面已明显扩展
- `Stage 2`：部分完成
- `Stage 3`：第一版骨架已落地
- `Stage 4+5`：部分完成
- `Stage 6`：第一版骨架已落地
- `Stage 7`：第一版骨架已落地
- `Stage 9`：部分完成
- `Stage 8`：桥接层已落地，但主链未完全切换
- `Stage 10`：第一版评价层已落地
- `Stage 11-12`：早期版本已存在
- `Stage 13`：基本未完成或仅有概念准备

## 19. 当前系统的主要优点

### 优点 1：重构不是停留在文档阶段

大量目标模块已经真正生成代码文件，不再是空谈。

### 优点 2：模型兼容层处理得对

`models.py -> domain/ + re-export` 是正确迁移策略，降低了 import 爆炸风险。

### 优点 3：StateAdapter 已显式实现

这一步很关键，避免了 `ContractEngine/WriterExecutor` 被 Stage 8 卡死。

### 优点 4：测试面已扩张

`195 passed` 的 pytest 结果说明系统已经开始具备“工程化保护网”。

### 优点 5：外壳与内核都在推进

不仅有内核拆分，还有：

- `ReadService`
- `ToolRegistry`
- `Shell`

说明系统已经开始向“可操作系统”演进。

### 优点 6：执行层的读写分流约束已经硬化

`ToolExecutor` 已经把“读直调、写走治理”这条架构边界固化进代码。

当前已经具备：

- `ToolAccess.READ` 直接执行
- `ToolAccess.GOVERNED` 走治理判定

虽然 Governance 的审批能力还未完全收口，但执行层的路由约束已经成立。

## 20. 当前系统的主要问题

### 问题 1：`service.py` 仍然过重

虽然比之前瘦了，但 `3615` 行依然是系统最大技术债。

### 问题 2：pipeline 仍依赖旧私有方法

新 pipeline 还没有真正接管底层实现。

### 问题 3：新模块不少还是 v1 占位实现

尤其是：

- `ContractEngine`
- `WriterExecutor`
- `QualityGate`
- `ReadService`
- `Shell`

### 问题 4：Repository / Export 未完成收口

新产物树存在，但旧 `export.py` 仍是中心。

### 问题 5：状态层还不是唯一事实源

`ProjectMemorySnapshot` 仍在主链中占重要地位。

### 问题 6：外层壳已经开始建设，但底层主链仍未完全稳定

这意味着项目已经进入“必须注意收口顺序”的阶段。

## 21. 当前发布阻塞项

如果目标是“健康、稳定、可运行、可打包发布”，当前仍有这些阻塞项：

### 阻塞项 1

`service.py` 尚未完成核心逻辑迁移。

### 阻塞项 2

`ContractEngine` 还不是完整生产级合同编译器。

### 阻塞项 3

`WriterExecutor` 还不是主链真实高质量正文引擎。

### 阻塞项 4

`StateAdapter -> CanonState` 切换尚未完全收口。

### 阻塞项 5

`export.py` 与新 repository 仍双轨并存。

### 阻塞项 6

`ReadService` 和 `Shell` 仍更多依赖旧 package 结构。

### 阻塞项 7

评价层与旧 `review.py / book_review.py` 仍处于并存阶段。

## 22. 结论

当前项目不是“未重构”，而是“重构已实质启动并取得明显进展”。

它最准确的状态是：

```text
内核重构已进入中期
外层交互壳已进入早期
核心生产能力仍由旧内核主导
新架构已具备骨架，但尚未完全接管
```

如果继续推进，最合理的工作重点不是再扩概念，而是：

1. 继续瘦身 `service.py`
2. 让 pipeline 真正接管主链
3. 让 `ContractEngine -> WriterExecutor -> StateAdapter/CanonState` 成为稳定硬链路
4. 收口 `export/repository`
5. 最后再让 `ReadService / Shell` 脱离旧系统依赖

这份代码现状说明：

- 项目方向是对的
- 架构骨架是成立的
- 工程化程度比早期明显高
- 但距离“稳定发布态”仍有一段明确的收口工程要完成

## 23. 当前代码缺口清单

本节将当前系统按四类状态整理：

- 已完成
- 半完成
- 未完成
- 发布阻塞

### 23.1 已完成

以下内容已经不再只是设计，而是代码中明确存在并可用：

#### 已完成 A：入口 facade 化第一步

- `AutonomousNovelSystem.generate()`
- `AutonomousNovelSystem.resume()`
- `AutonomousNovelSystem.rewrite_chapter()`
- `AutonomousNovelSystem.ensure_export_ready()`

已转为调用 pipeline，而不是继续把主流程写死在公开方法里。

对应文件：

- [opentale/app/service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/service.py:1)
- [opentale/app/pipeline/generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1)

#### 已完成 B：domain 模型拆分

`models.py` 已从模型定义中心降级为 re-export 兼容层。

对应文件：

- [opentale/app/models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/models.py:1)
- [opentale/app/domain/](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/__init__.py:1)

#### 已完成 C：ExecutionMode 基础接入

请求模型和 CLI 已经支持 mode。

对应文件：

- [opentale/app/domain/requests.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/requests.py:1)
- [opentale/cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1)

#### 已完成 D：治理骨架

已经有：

- ChangeRequest 分级
- FeedbackBus
- RecoveryPolicy
- StoryLock

对应文件：

- [opentale/app/governance/change_request_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/change_request_service.py:1)
- [opentale/app/governance/feedback_bus.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/feedback_bus.py:1)
- [opentale/app/governance/recovery_policy.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/recovery_policy.py:1)
- [opentale/app/governance/story_lock.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/story_lock.py:1)

#### 已完成 E：StateAdapter 桥接层

这个是非常关键的完成项，因为它已经把新状态接口与旧数据源桥接起来了。

对应文件：

- [opentale/app/state/state_adapter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/state_adapter.py:1)

#### 已完成 F：测试面扩张

当前测试已不是只有旧 clean 测试，已经扩展到 pipeline 模块组。

对应路径：

- [tests/pipeline/](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_generate.py:1)

#### 已完成 G：ToolExecutor 读写分流约束

`ToolExecutor` 已经把“读直调、写走治理”这条架构边界固化进代码。

当前已经具备：

- `ToolAccess.READ` 直接执行
- `ToolAccess.GOVERNED` 走治理判定

虽然 Governance 的审批能力还未完全收口，但执行层的路由约束已经硬化。

对应文件：

- [opentale/app/execution/tool_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tool_executor.py:1)
- [opentale/app/execution/tool_registry.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tool_registry.py:1)

### 23.2 半完成

这些部分已经开始实现，但还没有真正收口。

#### 半完成 A：Pipeline 主链接管

现状：

- pipeline 已建立
- 但仍大量回调 `service.py` 私有方法
- checkpoint 当前主要在 generate 方向写入阶段快照

差距：

- pipeline 尚未真正自包含
- resume 流程尚未形成对 checkpoint 的稳定读取与复用闭环

影响：

- 新旧双轨并存时间过长
- 出现“写了 checkpoint，但没有形成完整读路径”的不对称

#### 半完成 B：Checkpoint / Fast Path

现状：

- mode 已有
- checkpoint 已出现

差距：

- 缓存命中、阶段复用、重跑边界还不够成熟

#### 半完成 C：ContractEngine

现状：

- 能生成合同
- 能做基本校验
- 能输出 compile result

差距：

- 还不是成熟增量编译器
- invalidation 和 dependency graph 还很浅

对应文件：

- [opentale/app/compiler/contract_engine.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/contract_engine.py:1)

#### 半完成 D：WriterExecutor

现状：

- 结构已成立
- 有 scene decomposition / verify / local repair

差距：

- 默认仍是占位生成
- 尚未成为当前系统主链的高质量正文引擎

对应文件：

- [opentale/app/writer/writer_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/writer_executor.py:1)

#### 半完成 E：Repository / Export 重构

现状：

- 新 repository 已建立
- package exporter 已开始导出新 artifact

差距：

- 旧 `export.py` 仍然太重
- 新产物树仍不完整

#### 半完成 F：CanonState / StoryIR Query

现状：

- `canon_ledger.py`
- `story_ir_query.py`
- `state_adapter.py`

都已存在。

差距：

- 尚未成为主链唯一事实源
- 仍依赖旧 memory snapshot

#### 半完成 G：Evaluation Gate

现状：

- 新 evaluator 已有
- quality gate 已有

差距：

- volume gate 还是 placeholder
- 与旧 review 仍并存

#### 半完成 H：ReadService / Shell

现状：

- ReadService 可用
- ToolRegistry 可用
- Shell 可跑

差距：

- 仍依附旧 export/package 结构
- Intent / Planner 仍是规则级

### 23.3 未完成

这些部分在当前代码里还没有进入成熟实现，或者只停留在极弱形态。

#### 未完成 A：Pipeline 自主实现

目标状态应是：

- `GenerateNovelPipeline` 自己持有步骤实现

当前还没有做到。

#### 未完成 B：ContractEngine 的真正增量编译能力

包括：

- 精准 invalidation
- 惰性编译
- 跨章节依赖收缩
- 编译失败恢复建议闭环

#### 未完成 C：WriterExecutor 的正式高质量生成能力

包括：

- 与真实 llm runtime 深度集成
- 多场景高质量 prose 输出
- 稳定满足合同约束

#### 未完成 D：状态层唯一事实源化

也就是：

- ContractEngine
- WriterExecutor
- Director
- ReadService

全部改读正式 CanonState / StoryIR，而不是旧桥接混合态。

#### 未完成 E：完整 artifact tree

还缺：

- contract artifact 正式导出
- canon state artifact 正式导出
- governance artifact 正式导出
- checkpoints metadata 正式导出

#### 未完成 F：Review 新旧统一

还没有彻底完成：

- `review.py`
- `book_review.py`
- `evaluation/*`

的统一出口。

#### 未完成 G：发布态打包链路

当前代码审查中，没有看到完整的：

- wheel/install 流程验证
- 可执行入口验证
- 桌面程序打包实现
- 发布流水线

### 23.4 发布阻塞

以下事项如果不解决，系统不适合宣称为“健康、稳定、可发布”。

#### 阻塞 1：`service.py` 仍然是最大中心节点

只要它还是 `3615` 行并保留大量业务实现，系统就还没有真正摆脱旧内核。

#### 阻塞 2：新主链未完全接管正文生产

如果 `WriterExecutor` 还不是主生产引擎，那么“新架构已完成”这件事就不能成立。

#### 阻塞 3：状态层仍非唯一数据源

只要 `ProjectMemorySnapshot` 仍在主链中占据关键地位，就还存在双事实源风险。

#### 阻塞 4：新旧导出体系并存

只要旧 `export.py` 仍然是核心中心，repository / artifact tree 就未真正收口。

#### 阻塞 5：评价体系未统一

如果新旧 review 并行但出口未统一，就会出现：

- 判定标准不一致
- 回归逻辑不一致
- 发布门不一致

#### 阻塞 6：Shell 仍依赖旧数据读取体系

如果 `ReadService` 还是靠旧 `load_project_package()`，那 Shell 还不是最终态的查询外壳。

## 24. 面向“健康可发布态”的剩余工作摘要

如果以“健康、无明显 bug、可运行、可打包”为目标，剩余工作应压缩成以下几项主线：

### 主线 1：内核收口

- 继续瘦身 `service.py`
- 让 pipeline 真接管
- 让 ContractEngine / WriterExecutor 真接管

### 主线 2：状态收口

- `StateAdapter -> CanonState`
- StoryIR Query 正式化
- 单一事实源

### 主线 3：产物收口

- export/repository 统一
- 完整 artifact tree
- 兼容旧项目包

### 主线 4：评价收口

- review 统一出口
- publish gate 真正稳定

### 主线 5：发布收口

- CLI / API / Shell 入口稳定
- 安装与运行验证
- 打包流程明确

## 25. 具体施工任务清单

本节将当前剩余工作转为可以直接执行的任务书。

规则：

- 按优先级排序
- 每项任务尽量落到文件级
- 每项任务都带验收标准
- 优先处理会影响后续全部工作的事项

### P0：必须先做

这些任务不完成，后续大部分工作都会建立在不稳定基础上。

#### 任务 P0-1：完成 `service.py -> pipeline/` 主链迁移

目标：

让 `service.py` 只保留 facade，不再保留核心业务实现。

涉及文件：

- [opentale/app/service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/service.py:1)
- [opentale/app/pipeline/generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1)
- [opentale/app/pipeline/resume_project.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/resume_project.py:1)
- [opentale/app/pipeline/publish_flow.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/publish_flow.py:1)

具体动作：

1. 梳理 `service.py` 中仍被 pipeline 间接调用的私有方法。
2. 按流程拆到对应 pipeline 或下游模块。
3. 保持旧公开接口不变。
4. 每迁一个主步骤就跑回归测试。

验收标准：

- `service.py` 不再包含主生成链的大段业务实现
- pipeline 不再依赖大量 `system._xxx()` 私有方法
- CLI/API 回归通过

#### 任务 P0-2：完成 Stage 1.5 测试重定位

目标：

让测试绑定新模块边界，而不是继续强耦合旧调用路径。

涉及文件：

- [tests/test_clean_pipeline.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_clean_pipeline.py:1)
- [tests/test_cli_clean.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_cli_clean.py:1)
- [tests/test_api_clean.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/test_api_clean.py:1)
- [tests/pipeline/test_generate.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_generate.py:1)
- [tests/pipeline/test_repair.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_repair.py:1)

具体动作：

1. 补 facade 兼容测试。
2. 补 pipeline 直接测试。
3. 清理只适合旧私有路径的 mock。

验收标准：

- facade 层测试存在
- pipeline 层测试存在
- 后续改 pipeline 不需要反复改旧测试路径

#### 任务 P0-3：稳定 ExecutionMode 与 checkpoint 语义

目标：

让 mode 真正成为可依赖的执行模式，而不是零散跳步。

涉及文件：

- [opentale/cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1)
- [opentale/app/domain/requests.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/requests.py:1)
- [opentale/app/pipeline/generate_novel.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/generate_novel.py:1)
- [opentale/app/checkpoint/__init__.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/checkpoint/__init__.py:1)

具体动作：

1. 明确每个 mode 跑哪些阶段。
2. 明确 checkpoint 命中条件。
3. 明确 skeleton / deterministic / fast_draft 的边界。

验收标准：

- 同一输入重复运行时阶段复用稳定
- `--mode` 行为一致可预测
- 文本输出和产物结构与 mode 对应

#### 任务 P0-4：把恢复系统真正接到 rewrite / repair 链路

目标：

让 ChangeRequest / FeedbackBus / RecoveryPolicy 不只是孤立模块。

涉及文件：

- [opentale/app/governance/change_request_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/change_request_service.py:1)
- [opentale/app/governance/feedback_bus.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/feedback_bus.py:1)
- [opentale/app/governance/recovery_policy.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/recovery_policy.py:1)
- [opentale/app/pipeline/resume_project.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/resume_project.py:1)
- [opentale/app/pipeline/publish_flow.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/pipeline/publish_flow.py:1)

具体动作：

1. rewrite 前先生成/分类 ChangeRequest。
2. contract 或 review 失败时发 FeedbackEvent。
3. 根据 RecoveryPolicy 决定 local patch / recompile / replan。

验收标准：

- 重写不再是直接“重跑章节”
- 失败恢复路径可追踪
- 测试可验证分级恢复策略

### P1：内核硬链路

这些任务决定系统能否从“重构骨架”进入“真实新内核”。

#### 任务 P1-1：正式落地 `StoryPackage / StoryLock / ChapterPackage`

目标：

让设计态对象成为主链正式输入，而不是辅助对象。

涉及文件：

- [opentale/app/domain/package_models.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/domain/package_models.py:1)
- [opentale/app/screenwriter/service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/screenwriter/service.py)
- [opentale/app/governance/story_lock.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/governance/story_lock.py:1)
- [opentale/app/director/chapter_director.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/director/chapter_director.py)

具体动作：

1. 定义稳定数据结构。
2. 让生成链明确输出这三类对象。
3. 让项目包正式保存这些产物。

验收标准：

- 新产物进入主链
- Writer 之前有正式 package 对象
- 不再只靠 `ChapterSpec` 直连正文生成

#### 任务 P1-2：把 ContractEngine 提升为主链真实入口

目标：

让 Writer 前必须经过合同编译。

涉及文件：

- [opentale/app/compiler/contract_engine.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/contract_engine.py:1)
- [opentale/app/compiler/dependency_analyzer.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/dependency_analyzer.py:1)
- [opentale/app/compiler/invalidation_planner.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/compiler/invalidation_planner.py:1)
- [tests/pipeline/test_compiler.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_compiler.py:1)

具体动作：

1. 明确 contract 必填字段。
2. 明确 compile failure 结构。
3. 接入 dependency analysis。
4. 接入最小 invalidation scope。

验收标准：

- Writer 之前必须有 contract
- contract 不通过时禁止写正文
- contract failure 可测试、可恢复

#### 任务 P1-3：把 WriterExecutor 提升为真实正文执行链

目标：

让新 Writer 成为主链生产引擎，而不是旁路实现。

涉及文件：

- [opentale/app/writer/writer_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/writer_executor.py:1)
- [opentale/app/writer/scene_decomposer.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/scene_decomposer.py:1)
- [opentale/app/writer/contract_verifier.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/contract_verifier.py:1)
- [opentale/app/writer/local_repair.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/writer/local_repair.py:1)
- [tests/pipeline/test_writer.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_writer.py:1)

具体动作：

1. 接入真实 llm_fn 或稳定 prose backend。
2. 明确 scene decomposition 结果结构。
3. 把 contract verifier 和 repair 接成闭环。
4. 逐步替换旧章节写作路径。

验收标准：

- WriterExecutor 产出的正文被主链使用
- 合同满足率可测
- 本地修补可测

#### 任务 P1-4：收口 StateAdapter，准备 CanonState 切换

目标：

保证 Stage 6-7 和 Stage 8 之间的数据接口稳定。

涉及文件：

- [opentale/app/state/state_adapter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/state_adapter.py:1)
- [opentale/app/state/canon_ledger.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/canon_ledger.py:1)
- [opentale/app/state/story_ir_query.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/story_ir_query.py:1)

具体动作：

1. 固定 StateAdapter 接口。
2. 对现旧数据源映射做测试。
3. 为 CanonState 切换预留一致方法签名。

验收标准：

- ContractEngine / WriterExecutor 只依赖 adapter 接口
- 切换底层状态源时不需要改上层调用

### P2：数据与产物收口

这些任务决定项目包是否稳定、可查询、可维护。

#### 任务 P2-1：完成 repository / export 双轨收口

目标：

让旧 `export.py` 退出中心地位。

涉及文件：

- [opentale/app/export.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/export.py:1)
- [opentale/app/repository/project_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/project_repository.py:1)
- [opentale/app/repository/artifact_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/artifact_repository.py:1)
- [opentale/app/repository/index_repository.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/index_repository.py:1)
- [opentale/app/repository/package_exporter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/repository/package_exporter.py:1)

具体动作：

1. 定义标准 artifact tree。
2. 用 repository 层承担读写。
3. 让 export.py 只保留兼容入口。

验收标准：

- 新项目走 repository/exporter
- 旧项目仍能加载
- 产物目录稳定

#### 任务 P2-2：补齐 artifact tree

目标：

让当前项目包不只包含 manuscript 和 review，还包含新内核所需全部关键产物。

应补齐：

- story package
- story lock
- chapter package
- contracts
- canon state
- evaluations
- governance logs
- checkpoints metadata

验收标准：

- 项目包能独立支撑查询、恢复和继续生成

#### 任务 P2-3：完成 CanonState 接管

目标：

让旧 `ProjectMemorySnapshot` 从主链退到兼容层。

涉及文件：

- [opentale/app/state/canon_ledger.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/canon_ledger.py:1)
- [opentale/app/state/state_adapter.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/state/state_adapter.py:1)
- [tests/pipeline/test_canon_state.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/tests/pipeline/test_canon_state.py:1)

验收标准：

- 状态唯一事实源明确
- 旧 memory snapshot 仅作为兼容投影

### P3：质量门与运行收口

这些任务决定系统是否能稳定交付，而不是只会生成内容。

#### 任务 P3-1：统一 review / evaluation 出口

目标：

让旧 `review.py / book_review.py` 和新 `evaluation/*` 统一成一个主出口。

涉及文件：

- [opentale/app/review.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/review.py:1)
- [opentale/app/book_review.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/book_review.py:1)
- [opentale/app/evaluation/chapter_evaluator.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/chapter_evaluator.py:1)
- [opentale/app/evaluation/book_evaluator.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/book_evaluator.py:1)
- [opentale/app/evaluation/quality_gate.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/evaluation/quality_gate.py:1)

具体动作：

1. 定义统一评审输出结构。
2. 用新 quality gate 包装旧逻辑。
3. 逐步替换旧逻辑实现。

验收标准：

- 所有模式下只走一个评审出口
- 新旧测试不冲突

#### 任务 P3-2：补完 publish gate

目标：

让 publish 不再只是简单通过，而是真正有发布前检查。

应包含：

- chapter gate
- volume gate
- book gate
- publish gate

当前缺口：

- volume gate placeholder
- publish gate 仍简化

验收标准：

- `STRICT/PUBLISH` 模式的 gate 行为清晰稳定

#### 任务 P3-3：统一日志、失败报告、健康检查

目标：

让运行失败时能诊断，不是静默坏掉。

涉及文件：

- [opentale/cli.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/cli.py:1)
- [opentale/app/export.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/export.py:1)
- [opentale/app/gateway_support.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/gateway_support.py:1)

验收标准：

- 缺配置时报错明确
- provider 失败可诊断
- failure report 结构稳定

### P4：外壳与发布

这些任务排在最后，因为它们不解决内核正确性，但决定最终交付形态。

#### 任务 P4-1：完成 ReadService 脱钩

目标：

让 ReadService 不再主要依赖旧 `load_project_package()`。

涉及文件：

- [opentale/app/execution/read_service.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/read_service.py:1)

验收标准：

- ReadService 直接读新 artifact tree
- 不再大量回调旧 export 加载器

#### 任务 P4-2：稳定 ToolRegistry / ToolExecutor / Governance API

目标：

让查询与受治理写操作形成稳定工具层。

涉及文件：

- [opentale/app/execution/tool_registry.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tool_registry.py:1)
- [opentale/app/execution/tool_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tool_executor.py:1)
- [opentale/app/execution/tools/standard_tools.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/app/execution/tools/standard_tools.py:1)

验收标准：

- 读写路径清晰
- governed tool 真走治理链

#### 任务 P4-3：稳定 NarrativeShell

目标：

把 shell 从规则壳提升为稳定操作壳。

涉及文件：

- [opentale/shell/agent.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/agent.py:1)
- [opentale/shell/intent.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/intent.py:1)
- [opentale/shell/planner.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/planner.py:1)
- [opentale/shell/plan_executor.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/plan_executor.py:1)
- [opentale/shell/session_store.py](/home/laogao/Documents/trae_projects/1234/novel_writing_system/opentale/shell/session_store.py:1)

验收标准：

- shell 能查询真实新产物
- 能发起受治理修改
- 会话状态稳定持久化

#### 任务 P4-4：打包与发布验证

目标：

让项目进入真正可交付状态。

应完成：

- 安装验证
- CLI 入口验证
- API 启动验证
- shell 入口验证
- 发布说明

涉及文件：

- [pyproject.toml](/home/laogao/Documents/trae_projects/1234/novel_writing_system/pyproject.toml:1)
- [requirements.txt](/home/laogao/Documents/trae_projects/1234/novel_writing_system/requirements.txt:1)
- [requirements.lock](/home/laogao/Documents/trae_projects/1234/novel_writing_system/requirements.lock:1)

验收标准：

- 可以安装
- 可以运行
- 可以导出项目
- 可以恢复项目

## 26. 推荐执行顺序

如果按最小返工原则执行，推荐顺序如下：

1. `P0-1` 完成 pipeline 主链迁移
2. `P0-2` 完成测试重定位
3. `P0-3` 稳定 ExecutionMode 与 checkpoint
4. `P0-4` 接通恢复系统
5. `P1-1` 落地 StoryPackage / StoryLock / ChapterPackage
6. `P1-2` 把 ContractEngine 接成主链入口
7. `P1-3` 把 WriterExecutor 接成主链正文执行器
8. `P1-4` 固化 StateAdapter 接口
9. `P2-1` 和 `P2-2` 收口 export / repository / artifact tree
10. `P2-3` 完成 CanonState 接管
11. `P3-1` 和 `P3-2` 收口 evaluation / publish gate
12. `P3-3` 收口日志与失败报告
13. `P4-1 ~ P4-4` 再做外壳和发布

## 27. 最终执行标准

只有当以下条件同时满足时，才可以把系统定义为“健康、稳定、可发布”：

### 内核标准

- `service.py` 不再是主业务中心
- pipeline 真正接管主链
- ContractEngine 真正接管 Writer 前置合同
- WriterExecutor 真正接管正文生成

### 数据标准

- CanonState 是唯一事实源
- artifact tree 稳定
- repository 是统一读写入口

### 质量标准

- review / evaluation / publish gate 出口统一
- 失败可诊断
- 回归测试稳定

### 交付标准

- CLI 可用
- API 可用
- Shell 可用
- 项目包可导出、可恢复、可复核
- 安装与运行方式明确
