# OCOS — Organic Cognitive Operating System

> ⚠️ **SUPERSEDED-PARTIAL（2026-09-08）**：本文的主链描述（MasterAgent → Cognition → Decision → Action）已被
> [COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md](COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md) 更新为
> ResidentRuntime → RuntimeKernel → AgentRuntime.tick() → TaskDAG → DecisionBridge 单主链。
> 本文其余基础设施/安全/持久化描述仍然有效。现行完整现状以[项目白皮书 v1.3.1](OCOS_项目白皮书_v1.2.md)为准。

> 个人智脑内核 — 非 Agent 框架，非 LLM 包装器
> 
> v1.0.0 | 2026-09-02

---

## 概述

OCOS 是一个**数字生命体内核**，设计用于构建始终运行的个人认知引擎。它不是：
- ~~Agent 框架~~
- ~~LLM 包装器~~
- ~~记忆后端~~

它是：
- **个人智脑** — 自主思考、记忆、信念演化
- **认知操作系统** — 感知 → 认知 → 决策 → 行动 → 学习闭环
- **内生智能体** — 具有目标、注意力、情绪、睡眠机制

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    MasterAgent（认知主体）                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Perception│  │ Cognition│  │ Decision │  │  Action  │   │
│  │  Phase T  │  │ Phase D  │  │ Phase I  │  │  Phase L │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐   │
│  │Attention │  │ Belief   │  │ Planning │  │Execution │   │
│  │ Phase O  │  │ Phase E  │  │ Phase J  │  │ Phase D  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│  ┌────▼─────────────────────────────────────────▼─────┐   │
│  │              Memory & Learning                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │   │
│  │  │ Long-term│  │Knowledge │  │Learning  │         │   │
│  │  │Memory    │  │Graph     │  │Phase R   │         │   │
│  │  │ Phase G  │  │ Phase S  │  │          │         │   │
│  │  └──────────┘  └──────────┘  └──────────┘         │   │
│  └────────────────────────────────────────────────────┘   │
│       │                                      │             │
│  ┌────▼────────────────────────────────────▼─────┐       │
│  │         Sleep & Dream (Phase U)               │       │
│  │  自主睡眠决策 → 梦境生成 → 记忆巩固             │       │
│  └───────────────────────────────────────────────┘       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Persistence│  │ Security │  │Monitoring│  │Performance│  │
│  │  Phase V  │  │  Phase X │  │  Phase Y │  │  Phase Z  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐                                │
│  │External  │  │Orchestration│                             │
│  │ Phase Q  │  │  Phase N   │                             │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 完成列表

| Phase | 名称 | Commit | 状态 |
|-------|------|--------|------|
| A | Identity 身份内核 | f934524 | ✓ |
| B | Goal Model 目标模型 | 932c07d | ✓ |
| D | Cognition 认知内核 | 76f316a | ✓ |
| E | Belief 信念存储 | b105184 | ✓ |
| F | Homeostasis 内稳态 | d7bd5df | ✓ |
| G | Memory 长期记忆 | 09dce51 | ✓ |
| H | Learning 学习引擎 | 77a19eb | ✓ |
| I | Decision 决策引擎 | 006e35f | ✓ |
| J | Planning 规划引擎 | ed918c7 | ✓ |
| K | Emotion 情绪系统 | 29d3934 | ✓ |
| L | Action 行动执行 | 7a15d89 | ✓ |
| M | Runtime Loop 主循环 | 4561089 | ✓ |
| N | Orchestration 调度层 | 76a7b30 | ✓ |
| O | Attention 注意力焦点 | 9bfa7f3 | ✓ |
| P | Proactive Output 主动输出 | 4439fff | ✓ |
| Q | External Interaction 外部交互 | 337b791 | ✓ |
| R | Continuous Learning 持续学习 | eb961f5 | ✓ |
| S | Knowledge Graph 知识图谱 | e131d7a | ✓ |
| T | Multi-modal Perception 多模态感知 | 979fe31 | ✓ |
| U | Autonomous Sleep & Dream 自主睡眠 | 6fe9114 | ✓ |
| V | Persistence & Recovery 持久化 | e70ae46 | ✓ |
| W | External Integration 外部集成 | 3aad59b | ✓ |
| X | Security Hardening 安全加固 | 3d83446 | ✓ |
| Y | Monitoring & Observability 监控 | 8e1d501 | ✓ |
| Z | Performance Optimization 性能优化 | ae4e7e0 | ✓ |

---

## 核心能力

### 1. 感知层（Perception）

```python
from ocos.perception.multi_modal import MultiModalPerception

perception = MultiModalPerception()
observation = perception.perceive(text="用户输入", audio=None, image=None)
fused = perception.fuse([observation])
```

- 文本感知（TextSensor）
- 文件感知（FileSensor）
- 环境感知（EnvironmentSensor）
- 跨模态融合（CrossModalFusion）

### 2. 认知层（Cognition）

```python
from ocos.knowledge.graph import KnowledgeGraph

kg = KnowledgeGraph()
kg.add_entity("用户", "Person")
kg.add_relation("用户", "knows", "OCOS")
results = kg.search("用户")
```

- 知识图谱（KnowledgeGraph）
- 信念存储（BeliefStore）
- 模式提取（PatternExtractor）

### 3. 决策层（Decision）

```python
from ocos.decision.engine import DecisionEngine

decision_engine = DecisionEngine()
result = decision_engine.decide(observation, goals, beliefs)
```

- 意图解析
- 目标评估
- 价值判断
- 宪法约束

### 4. 学习层（Learning）

```python
from ocos.learning.manager import ContinuousLearning

learning = ContinuousLearning()
learning.record_feedback(user_id="u1", feedback="positive")
preference = learning.get_preference("u1")
```

- 反馈学习
- 偏好模型
- 知识更新

### 5. 记忆层（Memory）

```python
from ocos.persistence.manager import PersistenceManager

pm = PersistenceManager()
pm.save(state, reason="checkpoint")
restored = pm.restore()
```

- 快照管理
- 崩溃恢复
- 自动定期保存

### 6. 睡眠与梦境（Sleep & Dream）

```python
from ocos.sleep_dream.manager import SleepDreamManager

sleep = SleepDreamManager()
decision = sleep.check_sleep_need(idle_seconds=300)
if decision.allow:
    result = sleep.initiate_sleep()
```

- 自主睡眠决策
- 记忆回放梦境
- 创造性重组
- 洞察提取

### 7. 监控与告警（Monitoring）

```python
from ocos.monitoring.manager import MonitoringManager

mm = MonitoringManager()
mm.record_metric("requests_total", 1.0)
alerts = mm.evaluate_alerts({"error_rate": 0.15})
```

- Prometheus 端点（/metrics）
- 健康检查（/health）
- 告警规则引擎

### 8. 安全层（Security）

```python
from ocos.security.manager import SecurityManager

sm = SecurityManager()
decision, reason, _ = sm.check_access("user", "query")
sanitized, threats, _ = sm.sanitize_input(user_input)
```

- 权限网关
- 输入清洗（SQL注入/XSS/路径穿越）
- 审计日志

---

## 项目结构

```
ocos/
├── agent/                    # 核心 Agent
│   ├── master_agent.py      # MasterAgent
│   ├── control_loop.py      # 控制循环
│   └── lifecycle.py         # 生命周期管理
├── perception/              # 感知层
│   ├── multi_modal.py       # 多模态感知
│   └── cross_modal_fusion.py # 跨模态融合
├── cognition/               # 认知层
│   ├── belief/              # 信念系统
│   └── knowledge_graph.py   # 知识图谱
├── decision/                # 决策层
│   └── engine.py            # 决策引擎
├── learning/                # 学习层
│   └── manager.py           # 持续学习
├── memory/                  # 记忆层
│   └── consolidation.py     # 记忆巩固
├── sleep_dream/            # 睡眠与梦境
│   └── manager.py           # SleepDreamManager
├── persistence/            # 持久化
│   └── manager.py           # PersistenceManager
├── external/               # 外部集成
│   └── server_manager.py   # HTTP Server
├── security/               # 安全
│   └── manager.py          # SecurityManager
├── monitoring/             # 监控
│   └── manager.py          # MonitoringManager
├── performance/            # 性能
│   └── manager.py          # PerformanceManager
└── tests/                  # 测试
    ├── test_*.py           # Phase 单元测试
    └── test_integration.py # 集成测试

代码规模：148,000+ 行
测试数量：260+ 个
```

---

## 快速开始

### 安装

```bash
cd /home/laogao/Documents/trae_projects/ocos
pip install -e .
```

### 运行测试

```bash
# 单 Phase 测试
python -m pytest ocos/tests/test_runtime_loop.py -v

# 集成测试
python -m pytest ocos/tests/test_integration.py -v

# 全部测试
python -m pytest ocos/tests/ --ignore=ocos/tests/test_phase*.py -q
```

### 使用示例

```python
from ocos.agent.master_agent import MasterAgent
from ocos.performance.manager import PerformanceManager
from ocos.monitoring.manager import MonitoringManager
from ocos.security.manager import SecurityManager

# 创建 Agent
agent = MasterAgent(
    agent_id="my-brain",
    identity=...,      # 注入 Identity
    goal_stack=...,    # 注入 GoalStack
    # ... 其他组件
)

# 运行
agent.run()
```

---

## 设计原则

1. **确定性优先** — 关键路径使用确定性逻辑，避免 LLM 随机性
2. **防御式设计** — 所有外部输入必须经过安全检查
3. **可观测性** — 所有关键操作都有日志和指标
4. **幂等性** — 重复操作不会产生副作用
5. **插件化** — 各子系统独立开发、独立测试

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.0 | 2026-09-02 | Phase A-Z 全部完成，核心能力栈构建完毕 |

---

## 许可

内部项目，版权所有。
