# P2-C Dream Consolidation 冻结文档（2026-08-29）

## 1. 审计结论

| 组件 | 现状 | 证据 |
|---|---|---|
| dream() 入口 | ✅ 真实实现 | master_agent.py:803 — Phase 21 Lessons 合成 + Episode 存储 |
| DREAMING 触发链 | ✅ 已接 | life_cycle_orchestrator.py:112 `_tick_sleep → agent.dream()`，`_tick_idle` 检查 `attention.needs_sleep()` |
| Episode 存储 | ✅ 完整 | ocos/memory/episode/store.py — save/get/archive/query_by_time/query_by_goal/query_by_significance |
| Belief 系统 | ✅ 完整 | ocos/memory/belief/ — models（confidence/evidence_ids）、store（save/get/weaken/invalidate/archive/query_by_*）、validator、confidence、evidence |
| Pattern 系统 | ✅ 完整 | ocos/memory/pattern/ — extractor（extract/min_samples=3）、store（save/update_status/query_highest_confidence）、validator |
| **Episode→Belief/Pattern 巩固链** | ❌ **缺口** | dream() 只做 Lessons 合成；无"重放当日 Episode → 巩固入 Belief/Pattern → 修剪弱模式"（CLS 慢系统闭环） |
| MasterAgent 存储接线 | ❌ 缺口 | 无 belief_store/pattern_store 属性（learn() 的 patterns_learned 来自 opentale_bridge，非本地 PatternStore） |

**精确缺口**：升级报告 P2"dream() 每夜巩固窗口 🟡 测试态"——触发链与全部存储就绪，缺的是 dream() 内部的巩固编排：重放 → 聚合 → 巩固（Belief/Pattern）→ 修剪 → 幂等标记。

## 2. Scope（包含/不包含）

包含：
1. MasterAgent 构造新增 `belief_store` / `pattern_store` 可选参数（默认 None 时惰性创建 `:memory:` SQLite 并 initialize，风格对齐 `_episode_store`；显式传入则复用）
2. dream() 内新增巩固链（置于 Lessons 合成之后、wake_from_sleep 之前）：
   - **重放**：`episode_store.query_by_time(今日 0:00, now)`，过滤未 CONSOLIDATED 的 Episode
   - **Belief 巩固**：确定性聚合规则——按 Episode 的 tag/outcome 聚类；已存在同主题 Belief → evidence_ids 追加新 episode_id 且 confidence 提升（min(confidence+0.1, 1.0)）；不存在 → 新建（confidence=0.6 起，evidence_ids=[episode_id]）
   - **Pattern 提取**：`PatternExtractor.extract(当日未巩固 episodes)` → PatternStore.save；同 condition+outcome 已存在 → update_status 加强（不重复插入）
   - **弱模式修剪**：Belief confidence < 0.35 → weaken → archive（证据链断裂）；Pattern 同 condition 重复且低置信 → archive
   - **幂等标记**：巩固完成的 Episode 状态置 CONSOLIDATED（episode store 支持 status 字段；二次 dream 不重复巩固）
3. 巩固预算：单次 dream 处理上限 CONSOLIDATION_BATCH_LIMIT=200 条（防失控）；单条失败不阻塞
4. 契约测试 + L4 演化性测试 + 全量回归

不包含：
- ❌ 不触碰 dream() 现有 Lessons 合成路径（Phase 21 原样保留，追加而非替换）
- ❌ 不改 Belief/Pattern/Episode store 内部实现（只消费现成接口）
- ❌ 不引入 LLM——聚合/修剪/提升全部确定性规则表
- ❌ 不建新目录新模块（巩固编排写在 dream() 内 + 可注入的 `ConsolidationPlanner`？否——最小侵入：dream() 内私有方法 `_consolidate_episodes()`）
- ❌ 不做跨日重放窗口配置（今日 = 单日窗口，文档记录即可）
- ❌ 不动 opentale_bridge 的 patterns_learned（那是写作器官路径，非本地记忆巩固）

**接口签名**：
```python
# master_agent.py
def __init__(self, ..., belief_store: Any = None, pattern_store: Any = None): ...
def _consolidate_episodes(self) -> dict[str, Any]:
    """重放当日未巩固 Episode → Belief/Pattern 巩固 + 修剪。
    Returns: {"replayed": n, "beliefs_created": n, "beliefs_strengthened": n,
              "patterns_created": n, "patterns_strengthened": n, "pruned": n}
    """
```

## 3. 确定性规则表（防伪造）

| 规则 | 触发 | 动作 |
|---|---|---|
| Belief 新建 | 主题（tag 聚类）无现成 Belief | confidence=0.6，evidence_ids=[episode_id] |
| Belief 增强 | 同主题已有 Belief | confidence=min(c+0.1, 1.0)，evidence 追加 |
| Belief 修剪 | confidence < 0.35（N 夜未获新证据，N=3 规则位） | weaken → archive |
| Pattern 新建 | extractor 产出且 condition+outcome 不存在 | save |
| Pattern 加强 | condition+outcome 已存在 | update_status（confidence 提升） |
| 幂等 | Episode.status == CONSOLIDATED | 跳过（不重复巩固） |

## 4. 验收（L4 演化性）

1. 契约测试（tests/test_agent/test_dream_consolidation.py 新建）：
   - 当日 3 条同主题 Episode → dream() → Belief 1 条新建且 evidence_ids=3
   - 再入 1 条同主题 → 二次 dream → confidence 提升 +1，evidence 追加，Episode 置 CONSOLIDATED
   - 弱 Belief（confidence 0.3）→ dream → archive（修剪生效）
   - PatternExtractor 产出 → PatternStore 落库；重复 condition → 加强非重复插入
   - 二次 dream 幂等：CONSOLIDATED Episode 不重复计数
   - 无 episode_store → dream() 正常降级（返回全 0，不抛）
2. 全量回归 `pytest tests/`（基线 1952 passed / 8 skipped）
3. dream() 返回 consolidation dict 新增巩固统计字段（向后兼容：原字段不动）

## 5. Security（防越权/防伪造/防失控）

| 威胁 | 缓解 |
|---|---|
| 防越权 | 巩固链只读写本机 memory SQLite（belief/pattern/episode store），无外部接口 |
| 防伪造 | 全部确定性规则表（无 LLM）；confidence 由 evidence_ids 数量驱动，外部不可注入 |
| 防失控 | CONSOLIDATION_BATCH_LIMIT=200；单条失败不阻塞；修剪阈值下限 0.35 防止误删 |

## 6. Before / After

Before:
```
DREAMING → dream() → Lessons 合成 → Episode 存 → wake
                 └── (Episode 永不转化为 Belief/Pattern)
```
After:
```
DREAMING → dream() → Lessons 合成（原样）
                   → _consolidate_episodes()  ← 新增
                       query_by_time(今日) → 过滤未 CONSOLIDATED
                       → 聚类 → Belief 新建/增强（evidence 累加）
                       → PatternExtractor → PatternStore 保存/加强
                       → 弱 Belief/Pattern 修剪（archive）
                       → Episode 置 CONSOLIDATED（幂等）
                   → wake
```

## 7. 符合冻结原则声明

增量嵌入：不改既有 dream() 语义、不删任何存储接口、全部消费现成资产；新代码仅 dream() 内私有方法 + 构造参数；追加优先（Episode 状态位追加，不覆盖历史记录）。

## 8. 实施记录（2026-08-29，追加）

验收：✅ 全绿。全量回归 1952 → 1970 passed（+7 P2-C 契约 / +11 P2-D 契约），8 skipped，0 failed。

| 验收项 | 状态 | 证据 |
|---|---|---|
| _consolidate_episodes 私有方法 | ✅ | master_agent.py（dream() 内接线，Lessons 合成后调用） |
| 构造 2 可选参数（belief_store/pattern_store） | ✅ | 惰性创建内存存储，显式注入优先 |
| 确定性规则表（无 LLM） | ✅ | 全分支确定性：聚类键/强度/修剪阈值 |
| 200 条/夜预算 | ✅ | CONSOLIDATION_BATCH_LIMIT=200 模块常量 |
| Episode 置 CONSOLIDATED 幂等 | ✅ | mark_consolidated()；二次 dream 不重放（测试证） |
| 新契约测试 | ✅ | test_dream_consolidation.py 7 用例全绿 |
| 全量回归零破坏 | ✅ | 1970 passed / 0 failed |

### 实施偏差（追加记录，不覆盖冻结期假设）

1. **EpisodeStore 新增 mark_consolidated()**：冻结期假设"episode store 支持 status 字段"——字段存在但 store 无 status 更新方法（仅 archive()）。最小补充：单方法 UPDATE，幂等（rowcount 语义）。
2. **PatternStore 新增 find_by_condition()**：冻结期方案需"同 condition+outcome 去重"，store 原无按条件查询接口。最小补充：单查询方法。
3. **Pattern 弱修剪语义调整**：PatternStatus 枚举无 ARCHIVED（仅 CANDIDATE/VALIDATED/REJECTED）→ 低置信已有 Pattern 置 REJECTED（语义：被验证器拒绝，不参与后续）；Belief 弱修剪仍为 weaken→archive（原方案）。
4. **聚类键定稿**：goal → tags[0] → f"episode:{source}"（三阶回退，全确定性）。
5. **Belief id 确定性派生**：sha1(topic) 前缀（同主题跨 dream 可定位，增强不产生重复信念）。
