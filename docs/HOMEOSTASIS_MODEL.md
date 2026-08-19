# OCOS Homeostasis Model（稳态模型）

> **v1.0 — 2026-07-23 — 冻结于架构定调会议**  
> **层级：Layer 2 — 理论**  
> **地位：Homeostasis 是数字生命体区别于普通程序的关键特征。Recovery 是坏了修，Homeostasis 是始终保持健康。**  

---

## 核心理念

> "生命最大的能力不是修复损坏，而是始终保持不坏。"

Recovery 是"出事了怎么办"。  
Homeostasis 是"不让出事"。

```
人体：冷了 → 升温 | 热了 → 降温 | 累了 → 睡觉 | 饿了 → 吃饭
OCOS：Memory 太多 → 整理 | CPU 太高 → 暂停 | Goal 太多 → 排序
       Context 太长 → 压缩 | LLM 失败 → 等待 | DB 损坏 → 恢复
```

Homeostasis Manager 是一个**始终运行、优先级高于 Goal 的底层模块**。

---

## Homeostasis 系统结构

```
Homeostasis Manager（稳态管理器）
├── Monitor（监控器）
│   ├── resource_monitor      CPU / Memory / Storage / LLM 调用
│   ├── memory_monitor        记忆体大小 / 碎片率 / 遗忘率
│   ├── goal_monitor          Goal 数量 / 阻塞率 / 过期率
│   ├── health_monitor        错误率 / 延迟 / 崩溃计数
│   ├── context_monitor       Context 长度 / Token 消耗
│   └── identity_monitor      Identity 完整性检查
│
├── Regulator（调节器）
│   ├── memory_regulator      记忆压缩 / 遗忘 / 归档
│   ├── load_regulator        负载均衡 / 任务排队 / 降级
│   ├── context_regulator     Context 压缩 / 分页 / 摘要
│   ├── goal_regulator        Goal 排序 / 废弃 / 合并
│   └── energy_regulator      LLM 调用频率 / 冷却
│
├── Threshold（阈值配置）
│   ├── memory_max            最大记忆体（默认 100MB）
│   ├── goal_max              最大活跃 Goal（默认 10）
│   ├── context_max_tokens    最大 Context Token（默认 4096）
│   ├── error_rate_max        最大错误率（默认 5%）
│   ├── attention_fatigue_max 最大注意力疲劳（默认 0.8）
│   ├── latency_max           最大响应延迟（默认 30s）
│   └── llm_calls_per_hour    每小时最大 LLM 调用（默认 100）
│
└── Health Report（健康报告）
    ├── current_health_score  当前健康分 [0, 100]
    ├── alerts[]              活跃告警列表
    ├── recommendations[]     调节建议
    └── history               历史健康数据
```

---

## 监控维度

### 资源监控

| 指标 | 告警阈值 | 调节行动 |
|------|----------|----------|
| CPU 使用率 | > 80% | 暂停低优先级任务 |
| Memory 使用率 | > 80% | 触发遗忘 / 压缩 |
| Storage 使用率 | > 85% | 归档旧数据 |
| LLM 调用频率 | > 80/小时 | 降级推理质量 / 增加缓存 |
| 响应延迟 | > 30s | 检查阻塞点 / 熔断 |
| 错误率 | > 5% | 降级运行模式 |

### 记忆监控

| 指标 | 告警阈值 | 调节行动 |
|------|----------|----------|
| Working Memory 大小 | > 1000 项 | 压缩 / 转 Episode |
| Episode Memory 大小 | > 10000 项 | Consolidation 触发 |
| Long-term Memory 大小 | > 1GB | 遗忘策略激活 |
| Belief 数量 | > 5000 | 低置信度清理 |
| 记忆碎片率 | > 30% | 整理索引 |

### Goal 监控

| 指标 | 告警阈值 | 调节行动 |
|------|----------|----------|
| 活跃 Goal 数量 | > 10 | 暂停低优先级 Goal |
| 阻塞 Goal 数量 | > 3 | 集中解决阻塞 |
| 过期 Goal 数量 | > 5 | 归档过期 Goal |
| Goal 层断裂 | 存在孤立 Goal | 创建追踪链条 |

### 注意力监控

| 指标 | 告警阈值 | 调节行动 |
|------|----------|----------|
| 注意力疲劳 | > 0.7 | 建议切换到简单任务 |
| 注意力疲劳 | > 0.9 | 强制 SLEEP |
| 上下文切换频率 | > 30 次/小时 | 提示 "你是否需要专注模式？" |

---

## 稳态调节行动

### 记忆调节

```
当 memory_monitor 检测到：
  Working Memory > 1000 项
    → 触发 Episode Memory 写入
    → 清空已归档的 Working Memory
  Long-term Memory > 1GB
    → 触发 Forgetting Engine
    → 置信度 < 0.2 的 Belief 进入"待遗忘"
```

### 负载调节

```
当 load_regulator 检测到：
  CPU > 80% 连续 5 分钟
    → 暂停所有非交互性任务
    → 只保留 OBSERVE 和 THINK 的最低活跃度
  LLM 调用频率 > 80/小时
    → 启用响应缓存
    → 降级推理质量（先用轻量推理）
```

### Context 调节

```
当 context_monitor 检测到：
  Context Token > 4096
    → 压缩历史轮次（摘要化）
    → 丢弃已处理的 Observation
    → 警告不降低决策质量
  Context Token > 8192
    → 强制 REFLECT 后丢弃旧 Context
    → 归档到 Episode Memory
```

### Goal 调节

```
当 goal_monitor 检测到：
  活跃 Goal > 10
    → 按优先级排序
    → 暂停最低 3 个到 PENDING
  阻塞 Goal > 3
    → 分析阻塞原因
    → 解决最简单的阻塞先
```

---

## 稳态与 Life Cycle 的关系

| 阶段 | Homeostasis 活动 | 优先级 |
|------|-----------------|--------|
| BOOT | 全系统健康检查 | 最高 |
| WAKE | 加载阈值配置 + 检查告警 | 高 |
| OBSERVE | 持续监控所有维度 | 中（后台运行） |
| THINK | 仅在检测到高优先级告警时中断 | 低 |
| DECIDE | 不干预 | 无关 |
| ACT | 仅资源监控（防止执行耗尽资源） | 低 |
| REFLECT | 评估 Homeostasis 系统自身效果 | 中 |
| LEARN | 从 Homeostasis 数据中学习模式 | 低 |
| SLEEP | 非关键调节执行（压缩、遗忘、归档） | 高 |
| DREAM | **全系统稳态维护最佳窗口** | **最高** |

---

## Homeostasis 的优先级规则

```
Homeostasis 的优先级高于所有 Goal。
但 Homeostasis 不直接打断用户交互。
```

**规则**：

1. **用户交互时**：Homeostasis 在后台监控，不触发前台干扰
2. **空闲时**：Homeostasis 执行非紧急调节
3. **SLEEP/DREAM 时**：Homeostasis 执行全面维护
4. **紧急告警时**（如即将 OOM）：Homeostasis 获得最高优先级，**可以暂停用户交互并告知主人**

---

## 与 Recovery 的关系

```
Homeostasis（稳态）          Recovery（恢复）
──────────────────────    ──────────────────────
事前                         事后
预防                         修复
持续运行                     触发式
降级优先                     重启优先
"我不让出事"                 "出事了我搞定"
```

**协作流程**：

```
Homeostasis 检测到异常 → 尝试调节
  ├── 调节成功 → 记录到健康日志
  └── 调节失败 → 升级到 Recovery
                    ├── Recovery 尝试修复
                    ├── 修复成功 → 通知 Homeostasis 更新健康状态
                    └── 修复失败 → Human Escalation（求助主人）
```

---

## Homeostasis 的测试

| 测试场景 | 方法 |
|----------|------|
| Memory 溢出的稳态反应 | 写入 10 倍于阈值的记忆，验证自动遗忘 |
| CPU 过载的稳态反应 | 启动 50 个并发的 Task，验证自动降级 |
| Goal 爆炸的稳态反应 | 创建 30 个 Goal，验证自动排序和暂停 |
| Context 爆长的稳态反应 | 发送 500 轮对话，验证 Context 压缩 |
| LLM 失败的稳态反应 | 模拟 LLM 超时，验证熔断和冷却 |
| 注意力疲劳的稳态反应 | 模拟 2 小时持续专注，验证强制 SLEEP |

---

## Homeostasis 的未来扩展

| 能力 | 说明 | 预计 Phase |
|------|------|-----------|
| 自适应阈值 | 根据主人使用习惯自动调整阈值 | Phase 24 |
| 预测性稳态 | 预测即将出现的问题并提前干预 | Phase 25 |
| 跨设备稳态 | 多设备间的负载均衡 | Phase 27 |
| 长期健康演化 | 根据多年数据优化稳态策略 | Phase 28 |
