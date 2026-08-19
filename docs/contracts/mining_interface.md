# Phase14.3 — Mining Engine Interface Contract

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §2 Mining Input Contract

## 1. Purpose

定义 Mining Engine 的完整接口契约。

§2 只冻结**接口形状**——参数种类、输入/输出签名、确定性条件。
算法实现、具体参数值、发现策略全部留在 §3。

## 2. 接口签名

```
def mine(
    snapshot: EvidenceGraphSnapshot,
    config: MiningConfig
) -> list[PatternCandidate]:
    """
    Pattern Discovery 的唯一入口。

    参数:
        snapshot: Evidence Graph 不可变快照
        config:   Mining 参数配置

    返回:
        PatternCandidate 列表 (可能为空)
    """
```

## 3. 输入契约

### 3.1 EvidenceGraphSnapshot

(详见 `mining_input_snapshot.md`)

- 必须包含有效 UUID 作为 snapshot_id
- 必须包含版本追溯信息 (versions)
- 节点和关系数据必须符合 Allow List 约束
- 不得包含 Deny List 中的字段

### 3.2 MiningConfig

```
MiningConfig:
  config_id: str                         # 配置标识 (UUID)
  config_version: str                    # 配置格式版本 (e.g. "1.0")

  # ── 观察范围参数 ──
  scope_filter: str | None               # 范围过滤 (e.g. "scene:action", None=全部)
  relation_type_filter: list[str] | None # 关系类型过滤 (e.g. ["CO_OCCURRENCE"], None=全部)

  # ── 统计阈值 ──
  frequency_threshold: float             # 最低频率 [0.0, 1.0]
  min_occurrence_count: int              # 最低出现次数 (>= 1)

  # ── 窗口与采样 ──
  window_definition: dict | None         # 窗口定义 (用于序列/转换模式, None=不限制)
  sampling_policy: str | None            # 采样策略 (e.g. "uniform", None=全量)
```

### 3.3 禁止的参数字段

| 参数 | 原因 |
|------|------|
| `optimize_for: "reader_retention"` | 引入价值目标 |
| `target: "commercial_success"` | 引入商业目标 |
| `maximize: "reader_score"` | 引入评价目标 |
| `prefer_style: "action_scene"` | 引入风格偏好 |
| `minimize: "counter_evidence"` | 引入优化目标 |

## 4. 输出契约

### 4.1 输出形状

```
返回: list[PatternCandidate]
```

### 4.2 输出约束

| 规则 | 描述 |
|------|------|
| OC1 | 输出只能包含 PatternCandidate, **不能直接产生 Pattern** |
| OC2 | 每个 Candidate 必须引用 source_relation_ids (可追溯) |
| OC3 | 输出长度 >= 0 (允许空结果) |
| OC4 | 每个 Candidate 必须符合 PatternCandidate ABI (§1 冻结) |
| OC5 | 输出不得包含 Deny List 中的字段/值 |

### 4.3 禁止输出

```
Pattern[]                           — 必须经过 Validation 后生成
Principle[]                         — 属于 Phase14.4
Capability[]                        — 属于 Phase14.5
Recommendation[]                    — 属于 Phase15
StyleDefinition[]                   — 属于 Phase14.7+
```

## 5. 确定性执行契约

```
给定:
  相同 snapshot_id (指向相同数据)
  + 相同 config_id (指向相同配置)
  + 相同 mining_algorithm_version
→ 输出必须为相同的 PatternCandidate 集
  (以 candidate_id + feature_set + frequency 三元组判定)
```

### 5.1 确定性条件

| 组件 | 如何参与确定性 |
|------|---------------|
| snapshot_id | 同一 UUID → 同一份不可变数据 |
| config_id | 同一 UUID → 同一份参数 |
| mining_algorithm_version | 同一版本 → 同一算法逻辑 |
| 种子 (seed) | 若有随机性组件,必须暴露 seed 参数 |

### 5.2 违规后果

确定性被违反将导致：

- Pattern ↓ Principle ↓ Capability ↓ Control 整条审计链断裂
- 无法判断"这个模式是在数据中发现的还是偶然出现的"
- Phase15 无法追溯更改来源

## 6. 完整审计链

```
EvidenceGraphSnapshot (snapshot_id)
  + MiningConfig (config_id)
  + MiningAlgorithm (algorithm_version)
  ↓
PatternCandidate[] (每个引用 source_relation_ids)
  ↓
Pattern[] (每个引用 pattern_id 追溯回 candidate_id)
  ↓
Principle[] → Capability[] → ChangeProposal
```

每一环都可追溯回上一环的输入身份。

## 7. 接口规则

| 规则 | 描述 |
|------|------|
| IF1 | mine() 是 Mining Engine 唯一的公开入口 |
| IF2 | 输入必须通过 Allow/Deny 边界验证后才能进入算法逻辑 |
| IF3 | 输出必须符合 PatternCandidate ABI (§1) |
| IF4 | 同一 snapshot_id + config_id + algorithm_version → 同一输出 |
| IF5 | 禁止直接输出 Pattern (绕过 Validation) |
