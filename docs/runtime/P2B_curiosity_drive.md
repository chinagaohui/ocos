# P2-B 好奇心驱动（Curiosity Drive）— Scope 冻结

日期：2026-08-29 | 阶段：P2 本能（Instinct）| 拆分：B（A=Regulator ✅ 已完成）

## 1. 审计结论（先审计，不改代码）

**已有什么但未激活**（P2-B 的本质：激活而非新建）：

| 资产 | 位置 | 状态 |
|---|---|---|
| EXPLORE 驱力（匮乏触发） | homeostasis.py:164（P2-A 点亮） | ✅ 仅"目标匮乏"触发，无 novelty 信号 |
| AttentionEngine novelty 评分（1.0 - max_overlap） | runtime/attention_engine.py:150 | 🟡 完整实现，scheduler.py:271 集成点注释"后续 B2 集成"，默认 None 未接 |
| attention_fatigue（注意力疲劳） | homeostasis.py:343 | ✅ 现成，可作探索注意力预算（L5 防失控） |
| CURIOSITY_SPIKE 信号 | autonomous_runtime/runtime_config.py:28 | ❌ 零消费（仅定义，全库无消费点）— dead code |

**精确缺口**：EXPLORE 驱力无"新信息增量"输入。Schmidhuber 压缩进展 = novelty 最大化 → 探索目标；现有 novelty 评分引擎就是现成度量，缺的是把它接进 Regulator 的 derive_drives 规则表。

## 2. Scope（包含/不包含）

**实现路径说明（2026-08-29 实施时定稿）**：novelty 实际来源为 Step 2 已产出的
`AttentionDecision.score_trace.novelty`（CognitiveAttentionController → AttentionScoringEngine
确定性计算，attention.py:638 `novelty = priority_hint * 0.4`，round 4 位），取本 tick
所有决策的最大值。与文档初稿的 AttentionEngine.score_novelty（runtime/attention_engine.py）
同为确定性新信息度量；选择 Step 2 产物因为：① AgentRuntime 注意力链本就是
CognitiveAttentionController，无需跨系统重新采样；② 注意力系统唯一输出格式（attention_abi
Freeze §1.2）直接可消费；③ 防伪造属性保留（外部不可注入）。禁区全部遵守：未新建模块、
未触碰 AttentionEngine 内部、无 LLM、门控未变、未接 scheduler 参数。

包含：
1. AttentionEngine novelty 采样接入 AgentRuntime tick（Step 4.5 内），注入 MonitorSnapshot 新字段 `context.novelty`（默认 0.0，向后兼容）
2. derive_drives 新增确定性规则：novelty ≥ 0.6 → EXPLORE 强度按比例映射 [0.3, 1.0]（对齐 P2-A 偏差映射模式）；novelty < 0.6 不额外触发（匮乏规则保留）
3. 注意力预算：`attention_fatigue ≥ 0.70（max）→ 探索强度 ×0.5 抑制`（L5 防失控对应）
4. CURIOSITY_SPIKE 归并：runtime_config 中删除该枚举（并入 novelty 规则，不留双轨）

不包含（禁区）：
- ❌ 不新建模块（并入 Regulator，报告允许"或并入 Regulator"）
- ❌ 不触碰 AttentionEngine 内部评分逻辑（novelty 计算已冻结，只消费）
- ❌ 不引入 LLM/随机性（纯确定性规则表）
- ❌ 不改变 GoalOriginEnforcer 门控 / 优先级（沿用 P2-A D3: SELF < HUMAN）
- ❌ 不接 scheduler 的 attention_engine 参数（那是事件优先级用途，与本驱动无关）

## 3. 接口签名（冻结）

```python
# MonitorSnapshot.context 新增（向后兼容，默认值不破坏既有构造）
novelty: float = 0.0        # 0.0 ~ 1.0, AttentionEngine.score_novelty 输出

# Regulator.derive_drives 规则新增（确定性）
if snapshot.context.novelty >= 0.6:
    explore_intensity = clamp((novelty - 0.6) / 0.4)   # [0.0, 1.0] → [0.3, 1.0] 映射
    if snapshot.context.attention_fatigue >= 0.70:     # 预算抑制
        explore_intensity *= 0.5
```

## 4. 验收（2026-08-29 全部通过 ✅）

| # | 验收项 | 证据 |
|---|---|---|
| 1 | 契约测试：novelty=0.8 → EXPLORE 强度 ∈ [0.3, 1.0]；fatigue≥0.7 → ×0.5；novelty=0.3 → 不额外触发 | TestCuriosityDrive 8 项全绿（tests/test_capability/test_homeostasis.py）：0.8→0.5、1.0→1.0、0.3 不触发、匮乏合并取 max、fatigue 0.75→0.25（×0.5）、0.5 不抑制、regulate 注入、合并语义 |
| 2 | 全链路：Step 2 novelty → Step 4.5 好奇心 EXPLORE | TestCuriosityInjectionChain 2 项全绿（tests/test_agent/test_runtime_loop.py）：高 novelty decision → Step 4.5 drives 含 EXPLORE；无 decisions → 0.0 降级不中断 |
| 3 | `pytest tests/` 全量无回归 | **1952 passed / 8 skipped / 0 failed（10.68s）**（基线 1942 + 新增 10） |
| 4 | CURIOSITY_SPIKE 删除后全库无引用残留 | grep 全库仅剩注释与本文档说明，枚举成员零消费 |

## 5. Security（防越权/防伪造/防失控）

| 威胁 | 防护 |
|---|---|
| 防失控（探索过度） | attention_fatigue ≥ 0.70 强度 ×0.5 预算抑制；MAX_GOALS_PER_CYCLE=3 仍生效 |
| 防越权（内生目标越级） | 沿用 P2-A：GoalOriginEnforcer + HUMAN_PRIORITY_FLOOR=1.0 |
| 防伪造（novelty 造假） | novelty 仅来自 AttentionEngine.score_novelty（确定性计算），外部不可注入 |

## 6. Before / After

Before: EXPLORE 仅"无事可做"触发 → 内生目标 = 匮乏驱动，无新信息追求
After:  EXPLORE = 匮乏驱动 + novelty 驱动（新信息增量最大化），受注意力预算约束

## 7. 符合冻结原则

✅ 增量嵌入（零推翻）| ✅ 确定性规则优先 | ✅ 复用既有资产（novelty 引擎激活）| ✅ 禁区清单明确 | ✅ 验收可测试
