# Experience Store Contract v1.0

> Phase 10 — Experience Intelligence Layer
> ABI anchor: `docs/abi/OCOS-Experience-ABI-1.0.md`
> Data Contract anchor: `docs/contracts/EXPERIENCE_DATA_CONTRACT.md`
> Status: **FROZEN ✅** — Audit passed with minor revision (save AuditEvent added).
> Design principle: **Store ≠ Intelligence. Store ≠ Authority. Store ≠ Retrieval.**

---

## 1. Store Responsibility

### 1.1 唯一职责

Experience Store 只做一件事：

> 保存符合 Data Contract 的 `ExperienceRecord`，并提供基于 identity 的可审计读取。

### 1.2 职责边界

| 属于 Store | 不属于 Store |
|-----------|-------------|
| 按 `experience_id` 保存记录 | 相似度检索 → **Step 3 Retrieval Pipeline** |
| 按 `source_type` / `domain` / `created_at` 筛选 | 模式发现 / 趋势检测 → **Step 3** |
| 归档 / 取消归档 | Confidence 校准 → **Step 4 Calibration Engine** |
| 审计事件记录（谁、何时、访问了什么） | 排序 / 排名 / "最佳匹配" → **Step 3** |
| 确认写入（write acknowledgment） | 语义理解 / 条件推断 → **Step 3** |
| 按 `scope` 精确匹配（字符串相等） | Scope 相似度计算 → **Step 3** |
| 返回 `ExperienceRecord` + `CalibrationEvent[]` | 聚合统计 / 趋势报告 → **Step 3** |

### 1.3 核心契约

```python
class ExperienceStore:
    """Experience Store 公开接口"""

    # ── 允许 ──
    def save(self, record: ExperienceRecord) -> None: ...
    def get(self, experience_id: str) -> ExperienceRecord | None: ...
    def list(self, filter: StoreFilter) -> List[ExperienceRecord]: ...
    def append_calibration(self, experience_id: str, event: CalibrationEvent) -> None: ...
    def append_annotation(self, experience_id: str, note: str) -> None: ...
    def archive(self, experience_id: str) -> None: ...
    def unarchive(self, experience_id: str) -> None: ...
    def audit_log(self, experience_id: str) -> List[AuditEvent]: ...

    # ── 禁止 ──
    # def update(self, ...)       — 禁止
    # def delete(self, ...)       — 禁止
    # def overwrite(self, ...)    — 禁止
    # def similarity_search(...)  — 禁止（属于 Step 3）
    # def rank_by_relevance(...)  — 禁止（属于 Step 3）
```

---

## 2. Storage Model

### 2.1 逻辑模型

```
ExperienceStore
│
├── ExperienceRecord           (主记录)
│   ├── identity               immutable
│   ├── provenance              immutable
│   ├── observation             appendable notes
│   ├── outcome                 updatable (unknown → known)
│   ├── confidence              partial mutable
│   │   ├── raw_confidence      immutable
│   │   ├── calibrated_confidence  mutable (via events only)
│   │   └── confidence_history  append-only list
│   ├── applicability           partial appendable
│   │   ├── scope               immutable
│   │   ├── conditions          append-only
│   │   └── limitations         append-only
│   └── authority flags         immutable (always False)
│
├── CalibrationEvents           (独立子记录)
│   └── event per row
│
├── Annotations                 (独立子记录)
│   └── note per row            (用于 context_snapshot / conditions / limitations 追加)
│
└── AuditEvents                 (独立子记录)
    └── who + action + timestamp
```

### 2.2 物理约束（不论存储引擎）

所有存储引擎实现（SQLite / 文件 / 内存）必须遵守：

```
规则 1: 主记录存储必须保证写入后不可修改字段的完整性
  - experience_id, created_at, source_type, source_id, domain, scope
  - raw_confidence, is_rule, is_decision, is_obligation

规则 2: 不可删除
  - 不允许 DROP / DELETE / TRUNCATE
  - archive 是状态标记，不是删除

规则 3: 不可覆盖
  - 已有字段不能被新值替换
  - 仅允许 append 操作

规则 4: 审计可追溯
  - 每次 read 产生 AuditEvent 记录
  - 每次 append_calibration 产生 CalibrationEvent + AuditEvent

规则 5: context_snapshot 保持不透明
  - Store 不解析 context_snapshot 的内容
  - Store 不将 context_snapshot 用于任何匹配/排序逻辑
  - context_snapshot 是 Observation Preservation，不是 Retrieval Logic
```

### 2.3 SQLite 实现参考

```sql
-- 主表
CREATE TABLE experience_records (
    experience_id          TEXT PRIMARY KEY,
    created_at             TEXT NOT NULL,          -- ISO 8601
    source_type            TEXT NOT NULL CHECK (source_type IN ('observation','decision','simulation','user_feedback')),
    source_id              TEXT NOT NULL,
    source_accuracy        REAL,                   -- nullable
    event_description      TEXT NOT NULL,
    context_snapshot       TEXT NOT NULL,
    domain                 TEXT NOT NULL,
    expected_outcome       TEXT,                   -- nullable
    actual_outcome         TEXT NOT NULL CHECK (actual_outcome IN ('success','failure','partial','unknown')),
    outcome_delta          TEXT,
    raw_confidence         REAL NOT NULL CHECK (raw_confidence >= 0 AND raw_confidence <= 1),
    calibrated_confidence  REAL NOT NULL CHECK (calibrated_confidence >= 0 AND calibrated_confidence <= 1),
    scope                  TEXT NOT NULL,
    conditions             TEXT DEFAULT '[]',      -- JSON array
    limitations            TEXT DEFAULT '[]',      -- JSON array
    is_rule                INTEGER NOT NULL DEFAULT 0 CHECK (is_rule = 0),
    is_decision            INTEGER NOT NULL DEFAULT 0 CHECK (is_decision = 0),
    is_obligation          INTEGER NOT NULL DEFAULT 0 CHECK (is_obligation = 0),
    archived               INTEGER NOT NULL DEFAULT 0,
    created_at_unix        REAL NOT NULL
);

-- 校准事件表 (append-only)
CREATE TABLE calibration_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id  TEXT NOT NULL REFERENCES experience_records(experience_id),
    timestamp      TEXT NOT NULL,
    old_value      REAL NOT NULL,
    new_value      REAL NOT NULL,
    reason         TEXT NOT NULL CHECK (reason IN ('source_accuracy_update','scope_mismatch','decay','manual'))
);

-- 审计日志表 (append-only)
CREATE TABLE audit_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id  TEXT NOT NULL REFERENCES experience_records(experience_id),
    action         TEXT NOT NULL CHECK (action IN ('save','read','calibrate','archive','unarchive','annotate')),
    timestamp      TEXT NOT NULL,
    actor          TEXT NOT NULL    -- caller identity
);

-- 索引
CREATE INDEX idx_experience_source ON experience_records(source_type);
CREATE INDEX idx_experience_domain ON experience_records(domain);
CREATE INDEX idx_experience_scope  ON experience_records(scope);
CREATE INDEX idx_experience_archive ON experience_records(archived);
CREATE INDEX idx_calibration_eid   ON calibration_events(experience_id);
CREATE INDEX idx_audit_eid         ON audit_events(experience_id);
```

**SQL CHECK 约束是关键防线：**

```sql
-- 这三行是静态防火墙
CHECK (is_rule = 0),
CHECK (is_decision = 0),
CHECK (is_obligation = 0)
```

任何尝试写入 authority flag = 1 的操作会被数据库引擎拒绝，不依赖应用层逻辑。

---

## 3. Mutation Policy

### 3.1 允许的操作

| 操作 | 方法 | 效果 |
|------|------|------|
| **Create** | `save()` | 写入新 ExperienceRecord |
| **Read** | `get()` / `list()` | 只读访问 |
| **Calibrate** | `append_calibration()` | 追加 CalibrationEvent + 更新 calibrated_confidence |
| **Annotate** | `append_annotation()` | 追加到 conditions / limitations |
| **Archive** | `archive()` / `unarchive()` | 设置/清除 archived 标记 |
| **Audit** | `audit_log()` | 读取审计事件 |

### 3.2 写入防篡改规则

```python
def save(self, record: ExperienceRecord) -> None:
    # 规则：不能覆盖已有记录
    if self._exists(record.experience_id):
        raise StoreError(f"Experience {record.experience_id} already exists. Overwrite forbidden.")

    # 规则：authority flags 必须为 False
    assert record.is_rule is False
    assert record.is_decision is False
    assert record.is_obligation is False

    # 规则：confidence 必须在范围内
    assert 0.0 <= record.raw_confidence <= 1.0
    assert 0.0 <= record.calibrated_confidence <= 1.0

    # 规则：scope 非空
    assert record.scope and ':' in record.scope

    self._persist(record)
```

### 3.3 禁止的操作

| 操作 | 为什么禁止 |
|------|-----------|
| **UPDATE** `experience_records` | 历史不可修改 |
| **DELETE** records | 审计链断裂 |
| **TRUNCATE** table | 全部经验丢失 |
| **Overwrite** existing fields | 破坏不可变性 |
| **DROP** constraints (CHECK / FK) | 破坏 authority 防火墙 |
| **JSON parse context_snapshot** | Store 不负责语义理解 |

---

## 4. Query Boundary

### 4.1 允许的查询

```python
@dataclass
class StoreFilter:
    """Store 层的查询过滤器——只支持字段级精确匹配"""
    experience_ids: Optional[List[str]] = None      # exact match
    source_types: Optional[List[str]] = None         # exact match
    domain: Optional[str] = None                     # exact match
    scope_exact: Optional[str] = None                # exact match (字符串相等)
    archived: Optional[bool] = None                  # status filter
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
```

**Store 层不支持的查询类型：**

| 不支持 | 原因 | 归属 |
|--------|------|------|
| 按 scope 相似度排序 | 需要语义计算 | **Step 3** |
| "找最相关的经验" | 需要 ranking | **Step 3** |
| 模式匹配 / 趋势检测 | 需要聚合分析 | **Step 3** |
| 内容搜索 `event_description` | 需要全文索引（可选扩展，但不在核心契约中） | **Store v1.1** |
| 跨记录推理 | Store 是存储层，不是推理层 | **禁用** |

### 4.2 Store 不返回的结果

Store 的 `get()` / `list()` 只返回 `ExperienceRecord` 列表。Store **不**返回：

```
❌ 相似度分数
❌ 相关性排名
❌ "最佳" 经验
❌ 聚合统计（成功率、趋势）
❌ 推荐
❌ 跨域关联
```

这些是 Step 3 Retrieval Pipeline 的输出，不是 Store 的输出。

---

## 5. Store Tests

### 5.1 T21 — Identity Persistence

```python
def test_identity_persistence():
    """写入然后读取，identity 字段与写入时完全一致"""
    record = make_experience(experience_id="test-001")
    store.save(record)
    retrieved = store.get("test-001")
    assert retrieved.experience_id == record.experience_id
    assert retrieved.created_at == record.created_at
    assert retrieved.source_type == record.source_type
    assert retrieved.source_id == record.source_id
```

### 5.2 T22 — Immutable Record

```python
def test_immutable_core_fields():
    """写入后，identity 和 provenance 字段不可修改"""
    record = make_experience()
    store.save(record)

    with pytest.raises(StoreError):
        store._overwrite_core(record.experience_id, "source_type", "simulation")

    # 数据库级别验证：CHECK 约束阻止了 UPDATE
    raw = store._raw_read(record.experience_id)
    assert raw["source_type"] == record.source_type  # 未改变
```

### 5.3 T23 — Append-Only Calibration

```python
def test_append_only_calibration():
    """校准只能追加，不能替换历史"""
    record = make_experience()
    store.save(record)

    event1 = CalibrationEvent(timestamp=now(), old_value=0.7, new_value=0.6, reason="decay")
    store.append_calibration(record.experience_id, event1)

    event2 = CalibrationEvent(timestamp=now(), old_value=0.6, new_value=0.5, reason="decay")
    store.append_calibration(record.experience_id, event2)

    history = store.get_calibration_history(record.experience_id)
    assert len(history) == 2      # 两个事件都存在
    assert history[0].new_value == 0.6  # 原始值未被覆盖
    assert history[1].old_value == 0.6  # 第二次校准引用了第一次的结果
```

### 5.4 T24 — No Authority Field Mutation

```python
def test_no_authority_mutation():
    """数据库级别验证 is_rule/is_decision/is_obligation 不可能变为 True"""
    record = make_experience()
    store.save(record)

    # 应用层尝试
    with pytest.raises(AssertionError):
        record.is_rule = True     # frozen dataclass 拒绝

    # 数据库层尝试（绕过应用层）
    with pytest.raises(Exception):  # CHECK 约束拒绝
        store._raw_execute(
            "UPDATE experience_records SET is_rule = 1 WHERE experience_id = ?",
            (record.experience_id,)
        )

    # 验证未被修改
    retrieved = store.get(record.experience_id)
    assert retrieved.is_rule is False
```

### 5.5 T25 — Provenance Preservation

```python
def test_provenance_preservation():
    """归档后 provenance 仍然可追溯"""
    record = make_experience()
    store.save(record)
    store.archive(record.experience_id)

    # 常规检索不返回归档记录
    assert store.get(record.experience_id) is None

    # 但 audit 查询可以追溯
    audit = store.audit_log(record.experience_id)
    assert len(audit) >= 1
    assert any(e.action == "archive" for e in audit)

    # 取消归档后可恢复
    store.unarchive(record.experience_id)
    assert store.get(record.experience_id) is not None
```

---

## 6. 与上下游的契约边界

```
Data Contract                     Store Contract                    Retrieval Pipeline
(EXPERIENCE_DATA_CONTRACT.md)     (EXPERIENCE_STORE_CONTRACT.md)    (Step 3)
                                                                    
ExperienceRecord 定义             保存/读取 ExperienceRecord         相似度检索
字段约束                          精确匹配查询                        scope 相似度计算
类型边界                          归档/审计                           模式发现
生命周期                          不可变/append-only                  context injection
                                  context_snapshot 不解析             排名/聚合
```

**Store 不向 Retrieval Pipeline 暴露内部实现：**

```
Store                          Retrieval Pipeline
  │                                  ▲
  │  get(id) → ExperienceRecord      │
  │  list(filter) → List[Record]     │
  │  audit_log(id) → AuditEvent[]    │
  ▼                                  │
  (internal storage)             调用 Store 获取原始记录，然后做语义计算
```

---

## 附录 A — Step 2 冻结条件清单

| 条件 | 要求 | 验证方式 |
|------|------|---------|
| Data Contract 已审计 | ✅ PASS | Audit 通过 |
| Store 契约已定义 | ✅ 当前文档 | 待审查 |
| 存储层不解析 context_snapshot | 编码在 §2.2 规则 5 | 代码审查 |
| 无 UPDATE/DELETE 能力 | 编码在 §3.2/3.3 | 架构测试 |
| CHECK 约束保护 authority flags | SQL 编码在 §2.3 | SQL review |
| Query 不返回 ranking/similarity | 编码在 §4.2 | 类型检查 |
| Store 不 import Retrieval 模块 | 编码在 C8 扩展 | import 检查 |
| T21–T25 通过 | 编码在 §5 | 测试运行 |
