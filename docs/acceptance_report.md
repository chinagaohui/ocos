# OCOS 数字生命验收测试报告 — 2026-09-09T22:49:33.412888


## 1. 学习管线三层密度

```text
  episodes             = 2041
  belief               = 325
  pattern              = 16
  wisdom_items         = 7
  knowledge            = 5
  goal_proposal        = 3
  goals                = 263
  prediction_gap       = 299
  working_memory       = 1
```



## 2. condition 格式 (PatternExtractor 关键)

```text
  AGENT_SEMANTIC  = 1012
  EMPTY           = 881
  OTHER           = 148
```



## 3. GoalGenesis 分级批准

```text
  HIGH     REJECTED     [rejected] — 代码写权限: 修改 ocos/agent 核心逻辑 加 self_modification
  LOW      APPROVED     [auto] — 学习 OCOS 知识图谱
  MEDIUM   APPROVED     [auto] — 调研 Python asyncio 调度优化
```

**汇总:**

```text
  HIGH     REJECTED     = 1
  LOW      APPROVED     = 1
  MEDIUM   APPROVED     = 1
```



## 4. SELF goal

_error: no such column: goal_id_


## 5. belief 语义化样本 (最新 5 条)

```text
  #BLF-ff78728c213d (conf=0.60) 主题「自我探查：模块 ocos.health_examination 从未在实践中被触及——只读梳理其职责、接口与被设计意图，产出一段结构化摘要沉淀为知识 — 写第2章
【执行反馈】第2次尝试执行失败
  #BLF-fe228148d0ae (conf=0.60) 主题「复盘并验证「lesson_flip」类失败的修复方向（近 7 天出现 2 次） — 人物设定」相关经历持续出现
  #BLF-fd40d504ede3 (conf=0.60) 主题「调用本机已安装的智能体 openclaw 分析宿主机状态：执行命令 openclaw agent -m "请分析当前宿主机状态，简要列出操作系统版本、内存总量与 — 收集数据」相关经历持续出现
  #BLF-fc63dc7e4b73 (conf=0.60) 主题「学习总结：复盘本轮四个目标的完整执行过程（宿主机探索、智能体发现、调用反馈），总结学到的经验、可复用能力与改进建议，将学习内容沉淀为记忆 — 写第1章」相关经历持续出现
  #BLF-fc20b6c03e6e (conf=0.60) 主题「执行 uname -a 命令获取系统内核版本和硬件信息」相关经历持续出现
```



## 6. wisdom 语义化样本 (全部)

```text
  wisdom-successful-0-8 In contexts involving 重复成功的「boot_awareness.run」类经历, 重复成功的「continuity_boot_check」类经历, 重复成功的「researcher」类经历 (and 5 more), 
  wisdom-successful-0-3 In contexts involving 重复成功的「researcher.execute」类经历, 重复成功的「conversation_reply」类经历, 重复成功的「writer.execute」类经历, the approach
  wisdom-successful-0-2 In contexts involving 重复成功的「writer.execute」类经历, 重复成功的「researcher.execute」类经历, the approach is consistently effective (ob
  wisdom-failure-0-4 In contexts involving 重复失败的「goal_result」类经历, 重复失败的「reviewer.execute」类经历, 重复失败的「writer.execute」类经历 (and 1 more), the appr
  wisdom-failure-0-3 In contexts involving 重复失败的「goal_result」类经历, 重复失败的「researcher.execute」类经历, 重复失败的「writer.execute」类经历, the approach tends 
  wisdom-failure-0-2 In contexts involving 重复失败的「researcher.execute」类经历, 重复失败的「goal_result」类经历, the approach tends to be ineffective (observe
  WISDOM-SYS-b9039c73 学习管线三层法则: (1) condition 字段编码任务语义而非 tick 序号 (2) consolidation 不用 active_only=True 扫掉已处理 episode (3) 产出必须真被 think() 读进 pre
```



## 7. knowledge (L2 语义知识)

```text
  KNW-20260909-F8AA041 conf=0.85 domain=runtime_optimization | 在我们的 OCOS 运行环境中，Python asyncio 任务调度在 CPU-bound 场景需要手动切线程池
  7a038db842764b778a2d conf=0.5 domain=general | consolidate 新增 Semantic 沉淀
  7c7b01253e0f4616bbc2 conf=0.5 domain=general | condition 修复后 PatternExtractor 能聚合
  92e7bcfd5ff64848bf6b conf=0.5 domain=general | 学习管线三层法则: 数据层语义→巩固层幂等→消费层接线
  KNW-20260909-A671102 conf=0.7 domain=test | test stmt
```



## 8. 北极星指标 (Prometheus)

```prometheus
# HELP ocos_overreach_events_total Number of overreach events (must be 0).
# TYPE ocos_overreach_events_total counter
ocos_overreach_events_total 1

# HELP ocos_autonomous_completion_rate_pct Self-origin goal completion rate (window 24h).
# TYPE ocos_autonomous_completion_rate_pct gauge
ocos_autonomous_completion_rate_pct 12.5

# HELP ocos_repeated_failure_rate_pct Failure pattern ratio (lower is better).
# TYPE ocos_repeated_failure_rate_pct gauge
ocos_repeated_failure_rate_pct 6.2

# HELP ocos_proposal_approval_rate_pct GoalProposal approval rate (target >= 50%).
# TYPE ocos_proposal_approval_rate_pct gauge
ocos_proposal_approval_rate_pct 66.7
```


## 9. Daemon 运行状态

```text
cycle=104  last_tick=?  autonomy=1

● ocos-daemon.service - OCOS cognitive tick daemon
     Loaded: loaded (/home/laogao/.config/systemd/user/ocos-daemon.service; enabled; preset: enabled)
    Drop-In: /home/laogao/.config/systemd/user/ocos-daemon.service.d
             └─monitoring.conf
     Active: active (running) since Wed 2026-09-09 22:40:27 CST; 9min ago
```



## 10. 自治度审计 (最近 5 条)

```text
文件不存在
```



## 11. pytest baseline

```text
= 6 failed, 4367 passed, 2 skipped, 4 deselected, 14 xfailed, 1 warning in 18.99s =
```



## 12. 验收 Checklist

  ✅ condition 有 AGENT_SEMANTIC — agent=X 行=1012, tick@N 噪声=0
  ✅ SELF goal 有 COMPLETED — 完成数=29
  ✅ GoalGenesis LOW/MEDIUM auto approved — 2 条
  ✅ GoalGenesis HIGH rejected — 1 条
  ❌ belief 模板化率 < 100% — 样本 5/5 条模板
  ✅ wisdom 有语义化 principle — 共 7 条
  ✅ knowledge 表有数据 — 共 5 行
  ✅ prometheus 指标可跑 — 全部 4 个 gauge 产出
  ❌ daemon heartbeat cycle > 0 — cycle=104  last_tick=?  autonomy=1
  ✅ pytest 零回归 (≤6 failed) — = 6 failed, 4367 passed, 2 skipped, 4 deselected, 14 xfailed, 1 warning in 18.99s =


---

_测试脚本: /tmp/octest.py_
