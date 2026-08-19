# OpenTale Testing Strategy v1.0

> 生效日期：2026-07-19
> 适用范围：V4.6 及后续所有版本
> 维护者：架构师 / 项目维护者

---

## 1. 哲学

测试是验证体系，不是负担。它的价值在于：

- **PR 阶段快速拦截回归**
- **Nightly 验证完整链路正确性**
- **Release 前进行全量门禁检查**
- **架构变更时提供可信的度量基线**

**核心原则**：marker 按测试**性质**分类，不按执行时间。执行时间会随系统规模变化，但测试性质不变。

**优先级**：可信度 > 速度。宁可慢而准确，不可快而不可靠。

---

## 2. Marker 体系

### 2.1 定义

| Marker | 性质 | LLM | 完整生成 | PR 必跑 | 失败时 |
|---|---|---|---|---|---|
| `unit` | 验证单一模块边界行为 | 否 | 否 | ✅ | block merge |
| `integration` | 验证多模块协作，不触发生成循环 | 否 | 可局部 (≤1ch) | ✅ | block merge |
| `generation` | 验证完整生成流程（3+ chapters） | 可选 | 是 | ❌ | nightly alert |
| `golden` | 验证金标准输出一致性 | 按配置 | 是 | ❌ | release block |
| `llm` | 依赖真实模型/API 的集成测试 | 是 | 可选 | ❌ | release block |

**判断方法**：在决定 marker 时，自问"这个测试在测什么"而非"它跑多久"。

### 2.2 新增测试的自动归属

```python
# 默认 marker 由文件位置和函数特征决定
if "test_" in path and not path.startswith("tests/pipeline/"):
    if "generate" in test_name or "full_flow" in test_name:
        marker = generation
    else:
        marker = unit
elif path.startswith("tests/pipeline/"):
    if _triggers_full_generation(test_file):
        marker = generation
    else:
        marker = integration
```

实际通过 `pytestmark` / `@pytest.mark` 静态声明，不依赖自动化推断。

### 2.3 混编文件规则

当一个文件同时包含不同 marker 的测试时：

- 文件级 `pytestmark` 设为主要 marker（用于 CI 文件级别过滤）
- 异常测试函数单独加 `@pytest.mark.<other_marker>`
- CI 中该文件会被两个 marker 过滤器命中
- 示例：`test_api_clean.py`：文件级 `unit`，`test_generate_handler` 上加 `@pytest.mark.generation`

---

## 3. 新增测试归属指南

### 3.1 新增模块的最低要求

每个新增模块**至少**应满足：

- [ ] **至少一个 `unit` test**：覆盖模块核心行为
- [ ] **若影响 Pipeline 流程**：增加 `integration` test
- [ ] **若影响最终生成效果**：更新 Golden test 或人工审核输出
- [ ] **若引入 >10% 性能开销**：更新 Performance Baseline 并说明原因

### 3.2 示例：新增一个模块

```
新增: opentale/app/writer/plot_weaver.py
测试:
  tests/test_plot_weaver.py              unit (核心算法)
  tests/pipeline/test_plot_weaver.py      integration (嵌入 Writer 流程)
  tests/performance/test_pipeline_runtime.py  更新 (若新增耗时)
```

### 3.3 例外处理

当不满足某个要求时，必须在 PR 描述中说明：

- "暂不增加 integration test，因为 X 功能尚未完整落地"
- "暂不更新 Golden，因为输出格式待定"

例外需在下一 PR 中补齐。

---

## 4. 新增 Marker 流程

仅当现有 marker 无法表达新测试性质时，才考虑新增 marker。

**流程**：

1. 提出 RFC（在 README 或讨论中描述新 marker 的定义）
2. 确认现有 marker 确实不适用（不允许以"太慢"为理由新建 marker）
3. 全量更新：`pyproject.toml` + `TEST_STRATEGY.md` + 所有 CI workflow
4. 标记已有测试文件中适合该 marker 的用例
5. 全组周知（至少 README 更新）

**不批准新增 marker 的场景**：

- "这个测试跑得慢，需要一个 slow marker" → 应使用 `generation`
- "这个测试依赖数据库，需要一个 db marker" → 应使用 `integration`

---

## 5. CI 分层

### 5.1 三层架构

| Workflow | 触发器 | Marker 过滤器 | 目标耗时 | 失败时 |
|---|---|---|---|---|
| `ci.yml` | pull_request | `unit or integration` | <60s | ❌ block merge |
| `nightly.yml` | cron 06:00 UTC | `unit or integration or generation` | <10min | ⚠️ alert，不阻塞 |
| `release.yml` | push tags (v*) | 无（全量） | <30min | ❌ block release |

### 5.2 跨 layer marker 的行为

`ci.yml` 选择 `unit or integration`，含义是：

- 纯 `unit` 文件 → 执行
- 纯 `integration` 文件 → 执行
- 混编文件（文件级 `unit` + 函数级 `generation`）→ 执行，但 `generation` 标记的函数被 pytest 过滤器过滤掉
- 纯 `generation` 文件 → 跳过

### 5.3 扩展性

以后引入 Agent 或 World Simulator 时，无需新增 workflow：

- 单元级 Agent 行为 → `unit` 或 `integration`
- 完整 Agent 协作 → `generation`
- 只有必须每天跑、但 PR 不应跑的全新测试类别，才考虑新增 workflow

---

## 6. Performance Baseline

### 6.1 路径

```
tests/performance/
  __init__.py
  test_pipeline_runtime.py    # 第一个探针
  baseline_v4_6.json          # 首次基线数据
```

### 6.2 数据结构

```python
@dataclass
class PipelineRuntime:
    # 各阶段耗时（秒）
    context_assemble: float = 0.0
    memory_retrieve: float = 0.0
    world_simulation: float = 0.0    # V4.6: N/A
    planner: float = 0.0
    writer: float = 0.0
    reviewer: float = 0.0
    quality_gate: float = 0.0
    total_runtime: float = 0.0

    # 资源指标
    peak_context_tokens: int = 0
    llm_calls: int = 0
    retry_count: int = 0

    # 元数据
    commit_sha: str = ""
    timestamp: str = ""
    marker: str = "generation"  # 或 "golden"
```

### 6.3 行为

- 放在 `tests/performance/`，归属 `generation` marker
- 每次 full generation run（3 chapters, 6000 words）记录一次
- 不验证剧情正确性 —— 只验证耗时不超过前次基线的 20%
- 结果存为 JSON，保留历史
- 超出阈值时：告警（不 fail，因为性能可能因环境波动）

### 6.4 插桩方式

不修改生成代码。使用 `unittest.mock.patch` 包装关键方法：

```python
@contextmanager
def _time(label: str, results: dict):
    t0 = time.perf_counter()
    yield
    results[label] = time.perf_counter() - t0
```

或在 `AutonomousNovelSystem` 已有 trace 机制上包装。

### 6.5 V5 扩展

当引入 Agent、World Simulator 时，新增对应字段即可。接口固定，不需改框架。

---

## 7. Golden 管理

- 路径：`tests/golden/`（已有 `golden_chapter.py`）
- 金标准由人工审核确认
- Golden 变更必须附带 diff 说明
- Golden 测试在 release.yml 中执行，PR 阶段跳过

---

## 8. Exit Criteria

每个 Phase 必须有可验证的 Exit Criteria，以 checkbox 列表形式记录在 Phase 文档中。

### A1.5 Exit Criteria

```
□ PR CI（unit + integration）< 60s
□ Nightly（+ generation）全部完成不超时
□ Release（全量）包含 golden + llm
□ 130 个测试文件全部标记完成
□ TEST_STRATEGY.md 合并并生效
□ Performance Baseline 首次记录完成（v4.6 基线）
□ 新增测试默认带有正确 marker
□ 混编文件函数级 marker 到位
□ docs/testing/ 目录结构确立
```

### 通用 Exit Criteria 格式

```
□ <可验证条件>
□ 验证方式：<如何验证>
□ 负责人：<谁负责>
```

---

## 9. 维护责任

| 职责 | 负责人 | 周期 |
|---|---|---|
| 测试分类正确性 | 模块作者（引入新测试时） | 每次提交 |
| CI 配置完整性 | 开发者 | 每次 CI 变更 |
| Golden 更新审核 | 架构师 / PM | 每次 Golden 变更 |
| Performance Baseline 审核 | 架构师 | 每次 Release |
| TEST_STRATEGY.md 更新 | 架构师 | 每次策略变更 |
| Marker 体系扩展审批 | 架构师 | 仅新增 marker 时 |

---

## 附录 A：变更日志

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-07-19 | v1.0 | 初始版本，建立 marker 体系、CI 分层、Performance Baseline、Golden 管理 |
