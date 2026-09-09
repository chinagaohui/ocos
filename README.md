# OCOS — Organic Cognitive Operating System

> 个人智脑内核 — 非 Agent 框架，非 LLM 包装器
> 
> v1.0.0

## 这是什么？

OCOS 是一个**数字生命体内核**，用于构建始终运行的个人认知引擎。

**它不是：**
- Agent 框架
- LLM 包装器
- 记忆后端

**它是：**
- **个人智脑** — 自主思考、记忆、信念演化
- **认知操作系统** — 感知 → 认知 → 决策 → 行动 → 学习闭环
- **内生智能体** — 具有目标、注意力、情绪、睡眠机制

## 核心能力

| 能力 | Phase | 说明 |
|------|-------|------|
| 多模态感知 | T | 文本/文件/环境感知 + 跨模态融合 |
| 认知推理 | D/I/J | 信念系统 + 决策引擎 + 规划引擎 |
| 持续学习 | H/R | 从反馈中学习偏好，更新信念 |
| 知识图谱 | S | Entity-Relation-Fact 三元组管理 |
| 自主睡眠 | U | 基于稳态的睡眠决策 + 梦境生成 |
| 持久化恢复 | V | 快照管理 + 崩溃恢复 |
| 安全权限 | X | 输入清洗 + 权限网关 + 审计日志 |
| 监控告警 | Y | Prometheus 端点 + 告警规则 |
| 性能优化 | Z | 智能缓存 + 批处理 + 性能分析 |

## 快速开始

```bash
# 安装
pip install -e .

# 运行测试
python -m pytest ocos/tests/test_integration.py -v

# 查看架构文档
cat docs/ARCHITECTURE.md
```

## 项目状态（2026-09-08 基线）

- **代码规模：** 167,311 行 / 817 modules / 2,364 classes
- **测试数量：** 7,034 passed（另有 34/34 生产验证检查项全通过）
- **生产状态：** systemd 常驻 daemon 运行中，行为级验收 10 项全绿
- **当前阶段：** 认知运行时收敛（P0-P4 完成）→ Behavioral Delta 验证
- **主链：** ResidentRuntime → RuntimeKernel → AgentRuntime.tick() → TaskDAG → DecisionBridge → Permission → Execution

## 文档

- [项目白皮书 v1.3.1](docs/OCOS_项目白皮书_v1.2.md)（最完整现状）
- [AGI 升级蓝图 v1.1](docs/BLUEPRINT_AGI_UPGRADE_v1.1.md)（当前路线）
- [认知运行时收敛裁决 v1.0](docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md)
- [架构文档](docs/ARCHITECTURE.md)（部分被收敛裁决更新，见文档头状态标注）
- [设计原则](docs/DESIGN_PRINCIPLES.md)
- [API 参考](docs/API_REFERENCE.md)

## 许可

内部项目，版权所有。
