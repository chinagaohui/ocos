# Phase15.2.0 Control Signal Positioning Review

**日期**: 2026-07-22
**前置依赖**: Phase15.0 (Control Plane Positioning) ❄️, Phase15.1 (Runtime Registry) ❄️
**状态**: ❄️ FROZEN — 定位合约

---

## §0 Control Signal 定位

### 0.1 定义

Control Signal 是 **抽象控制意图（Control Intent）** — 从 Knowledge Plane 的 Principle/Pattern 到 OpenTale Runtime 的桥梁。

```
Knowledge Plane                    Control Plane                    Runtime
┌────────────────┐                ┌────────────────┐              ┌──────────┐
│  Principle     │                │  Control       │              │ Director │
│  Registry      │ ──Principle──→ │  Signal        │ ──Signal──→ │ Writer   │
│                │                │                │              │ CharBrain│
│  Pattern       │                │  (抽象控制意图) │              │ Quality  │
│  Registry      │ ──Pattern──→   │                │              │ Gate     │
└────────────────┘                └────────────────┘              └──────────┘
                                        ↑
                            NOT 具体指令 / NOT 文本 / NOT 配置
```

### 0.2 三问检查

| 问题 | 答案 |
|------|------|
| **方向** — 它往哪里去？ | 从 Principle+Pattern 提取抽象控制意图 → Adapter 转化为 Runtime 可理解的约束/参数 |
| **性质** — 它是什么？ | 抽象控制意图，不是具体指令。Signal 只说"控制什么方向"，不说"怎么执行" |
| **可删除性** — 如果没有它，会怎样？ | Knowledge Plane 仍能生产 Principle，但 Runtime 只能由硬编码规则驱动，无法动态适应叙事类型/风格 |

### 0.3 身份定位

| 维度 | 是（Control Signal） | 不是（❌） |
|------|---------------------|-----------|
| 抽象层级 | 控制意图（_what to constrain_） | 具体指令（_how to execute_） |
| 来源 | Principle / Pattern | Prompt / Template |
| 输出格式 | 结构化数据（dataclass） | 自然语言文本 / 配置参数 |
| 生命周期 | 由 Registry 管理或即时生成 | 持久缓存 / 共享状态 |
| 可变性 | 不可变（immutable）——生成后不修改 | 可编辑 / 可覆盖 |
| 包含 | signal_id, source_principle_ids, control_domain, payload（抽象）, version, trace_root | Writer 策略, Director 脚本, 参数配置 |

---

## §1 控制域定义

### 1.1 允许的控制域（ALLOWED）

| 控制域 | 描述 | 示例意图 |
|--------|------|----------|
| `narrative_control` | 叙事方向/类型/风格控制 | "保持悬疑节奏"、"偏向言情情绪曲线" |
| `pacing_control` | 叙事节奏/推进速度 | "加速高潮准备"、"减速抒情段落" |
| `constraint_control` | 约束结构控制 | "避免角色出场过密"、"保持 POV 一致性" |
| `planning_control` | 叙事规划控制 | "平行线索数限制"、"章节结构偏好" |

### 1.2 禁止的控制域（FORBIDDEN）

| 控制域 | 为什么禁止 |
|--------|-----------|
| ❌ `prompt` | 这是 Runtime 层的产出，控制信号不包含提示 |
| ❌ `template` | 格式化模板属于 Writer/Capability |
| ❌ `generation_text` | 生成的文本本身不是控制信号 |
| ❌ `rewrite_instruction` | 重写指令是 Director 执行后的产物 |
| ❌ `recommendation` | Control Signal 不得包含推荐/评分/排序 |
| ❌ `writer_config` | Writer 配置属于 Capability 层 |
| ❌ `director_script` | Director 脚本是 Control 层内部实现，不是 Signal |
| ❌ `parameter_bundle` | 参数配置是 Adapter 的翻译产物，不是 Signal 本身 |

### 1.3 控制域扩展规则

后续如需增加新的控制域，必须满足：

1. 新域必须是 **抽象控制意图**，不是具体执行指令
2. 新域不能是任何已有禁止域的别名或子集
3. 新域必须有明确的 Principle/Pattern 来源
4. 新域不能引用任何 OpenTale Runtime 模块的具体类/接口

---

## §2 Control Signal 的数据边界

### 2.1 包含（MUST HAVE）

```
ControlSignal {
  signal_id: str                                  — 唯一标识符
  source_principle_ids: list[str]                 — 来源 Principle IDs（至少 1 个）
  source_pattern_ids: list[str]                   — 来源 Pattern IDs（可选，提供更细粒度溯源）
  control_domain: str                             — 控制域（必须是 §1.1 允许的）
  payload: dict[str, Any]                         — 抽象负载（不包含具体 Runtime 参数）
  version: str                                    — Signal 版本
  trace_root: TraceRoot                           — 溯源根（与 Principle 共享）
}
```

### 2.2 不包含（MUST NOT HAVE）

❌ 不包含 `prompt_text` / `instruction_text` / `template` 等任何自然语言字段
❌ 不包含 `writer_params` / `director_config` / `runtime_args` 等 Runtime 配置
❌ 不包含 `score` / `rank` / `priority` / `recommendation` 等排序/推荐字段
❌ 不包含 `generated_text` / `output_content` 等生成产物
❌ 不包含 `rewrite_target` / `correction_instruction` 等修改指令

### 2.3 payload 限制

`payload` 字典中允许的值类型：

| 类型 | 允许 | 示例 |
|------|------|------|
| `str` | ✅ | 控制域特定的枚举值 |
| `int` | ✅ | 计数/索引 |
| `float` | ✅ | 阈值/比例/权重（0.0–1.0） |
| `bool` | ✅ | 开关标志 |
| `list[str]` | ✅ | 集合/列表 |
| `dict[str, Any]` | ✅ | 嵌套结构（但必须符合约束） |
| `None` | ✅ | 可选字段未设置 |

❌ 禁止：`Callable` / `Function` / 可执行代码
❌ 禁止：嵌套超过 3 层
❌ 禁止：键名包含 `prompt` / `instruction` / `template` / `config` / `param` / `score`

---

## §3 与 Principle/Pattern 的关系

### 3.1 映射原则

```
Principle —1→N— ControlSignal

一个 Principle 可以产生零个或多个 Control Signal。
一个 Control Signal 可以来自多个 Principle（冲突合并后）。
```

- Control Signal 必须可追溯到至少一个 Principle（`source_principle_ids`）
- Pattern 来源可选（`source_pattern_ids`），但如果有则必须可追溯
- Control Signal 不能凭空产生——没有 Principle/Pattern 来源的 Signal 是非法的

### 3.2 映射约束

| 条件 | 行为 |
|------|------|
| Principle 引用了一个禁止的控制域 | ❌ 映射禁止 |
| Principle 没有映射到任何允许的控制域 | Signal 不产生（静默跳过） |
| 多个 Principle 映射到同一 control_domain | 进入 Phase15.5 Meta-Control 冲突解决 |
| Signal 的 payload 包含禁止字段 | ❌ 验证失败 |

---

## §4 三层架构正式声明

自 Phase15 起，OCOS 正式使用以下三层架构命名：

```
┌──────────────────────────────────────────────────┐
│              Observation Plane                    │
│  Reality → Evidence → Relation → Pattern         │
│  对世界的观察，不包含解释或推荐                    │
├──────────────────────────────────────────────────┤
│              Knowledge Plane                      │
│  Principle → Registry (Runtime Infrastructure)    │
│  从观察中提炼的知识，可被控制层查询                │
├──────────────────────────────────────────────────┤
│              Control Plane                        │
│  Signal → Adapter → OpenTale Runtime              │
│  将知识转化为控制意图，驱动叙事生成                │
└──────────────────────────────────────────────────┘
```

### 4.1 层级隔离铁律

```
Knowledge  ────→  Control  ────→  Generation ✅
Knowledge  ────────────────→  Generation ❌ 禁止跨层
```

- **不得出现**: Principle → Writer（跳过 Control Signal）
- **不得出现**: Pattern → Director Prompt（Signal 未压缩就变成了文本）
- **不得出现**: Registry → Runtime（必须经过 Resolver → Adapter）

### 4.2 目录约定

后续代码目录、接口文档、架构审计统一使用这三层命名：

| 物理路径 | 层 |
|----------|-----|
| `reality/` | Observation Plane（已有 Phase13 基础） |
| `reality/` 下的 Registry 模块 | Knowledge Plane（Phase14→15.1） |
| `reality/` 下的 Signal 模块 | Control Plane（Phase15.2+） |

注：因物理目录已在 Phase13 定为 `reality/`，不再做目录迁移。三层标签通过模块命名和 `__init__.py` 导出区分。

---

## §5 签署

```
Phase15.2.0 Control Signal Positioning Review
============================================================
Date:     2026-07-22
Author:   laogao + Hermes Agent
Status:   ❄️ FROZEN — Positioning Contract

Phase15 Chain:
  15.0 Control Plane Positioning ❄️
  15.1 Runtime Registry ❄️
  → 15.2.0 Control Signal Positioning ❄️ (当前文档)
  → 15.2.1 Control Signal ABI (待构建)
  → 15.2.2 Principle→Signal Mapping Contract
  → 15.2.3 Signal Validation
  → 15.2.4 Signal Registry (可选)
  → 15.2.5 Freeze Audit

Next: 15.2.1 Control Signal ABI — 定义 ControlSignal dataclass
```

---

## Change Log

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-07-22 | 初始冻结 |
