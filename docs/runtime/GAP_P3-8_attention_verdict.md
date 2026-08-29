# GAP-P3-8 裁决: 三套注意力并存 (2026-08-30)

## 结论
三套注意力文件不是重复实现, 是职责分层 → **不改码, 冻结面不动**。
按方案冻结条款 ("若触碰 Authority/注意力 ABI 只写裁决文档不改码") 执行。

## 引用面核查 (证据)
| 组件 | 行数 | 职责 | 引用面 | 触碰 attention_abi 冻结面 |
|---|---|---|---|---|
| ocos/attention/ (retrieval+scoring) | 357 | Phase 39 评分引擎: 检索 + 候选评分 | 生产: opentale_bridge/master_agent.py, runtime/stages/attention.py; 测试: test_phase39_1/5/6 | 否 |
| ocos/capability/attention.py | 909 | 运行时注意力控制器 (Phase 36/37) | 生产核心 (ABI 消费者) | **是 — 唯一 ABI 实现者** |
| ocos/agent/attention.py | 155 | agent 编排层注意力 (Attention/FocusMode) | agent/__init__.py 核心导出, life_cycle_orchestrator.py; 测试: test_single_main_loop, test_phase33/35, test_proactive_output | 否 |

## 分层判断
引擎(计算) → 控制器(决策, ABI 契约) → 编排(agent 使用)。三套全部有生产
引用, 无一套是死代码; capability/attention.py 是冻结面
(AttentionDecision/FocusChange/WMAllocation 等)的唯一契约实现者, 合并
即破坏 ABI。

## 附带清理 (随 P3-8)
- C.3: runtime/attention_engine.py:60 移除 SemanticContentAnalyzer
  "占位承诺" (该分析器从未实现)
- C.4: kernel/abi.py Event.event_type 默认值注释收敛 (placeholder → 显式
  指定提示)

## 遗留 (不修, 记 findings)
- Attention 噪声: 缺 current_focus 告警 (attention_engine.py 附近)
- 三套注意力命名易混淆, 建议后续统一命名空间 (如 attention_engine/
  attention_controller/agent_attention), 不在 GAP-P3 范围
