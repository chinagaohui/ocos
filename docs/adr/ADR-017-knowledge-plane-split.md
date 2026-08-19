# ADR-017: Knowledge Plane 分离 — Store / Process

> **状态**: Approved (冻结后执行)
> **关联**: ADR-016 Knowledge Plane Freeze

## 背景

当前 `ocos.knowledge.*` 包含 7 个模块，实际承担了两类不同性质的职责：

| 类别 | 文件 | 行数 | 性质 |
|------|------|------|------|
| **Storage** | `knowledge_registry.py` | 333 | 数据存储 + 访问控制 |
| **Storage** | `knowledge_lifecycle.py` | 248 | 生命周期 + 版本管理 |
| **Storage** | `knowledge_ontology.py` | 167 | 层级/状态/单元定义 |
| **Process** | `knowledge_validator.py` | 250 | 校验逻辑 |
| **Process** | `knowledge_evolution.py` | 498 | 演化提案 + 审批 |
| **Process** | `promotion_rules.py` | 288 | 提升策略引擎 |
| **门面** | `knowledge_abi.py` | 266 | 统一 ABI |

这种混合结构导致：
- Process 模块直接操作 Storage 数据结构，绕过 ABI
- 新增一种 Knowledge Process（如 `compression`、`conflict_resolution`）需要修改现有模块
- 测试边界不清晰：Storage 测试 vs Process 测试混在同一个目录

## 决策

冻结后第一件事：将 Knowledge Plane 拆分为两个子平面：

```
ocos/knowledge/
├── __init__.py            # 统一门面，向后兼容导出
├── knowledge_abi.py       # 统一 ABI（保持在根目录）
├── store/                 # 知识存储子平面
│   ├── registry.py        # ← knowledge_registry.py
│   ├── lifecycle.py       # ← knowledge_lifecycle.py
│   └── ontology.py        # ← knowledge_ontology.py
└── process/               # 知识处理子平面
    ├── validator.py       # ← knowledge_validator.py
    ├── evolution.py       # ← knowledge_evolution.py
    └── promotion_rules.py # ← promotion_rules.py
```

## 迁移规则

1. **Storage 层不依赖 Process**: `store/` 中的所有模块不能 import `process/` 中的任何东西
2. **Process 通过 ABI 访问 Storage**: Process 模块必须通过 `knowledge_abi.py` 访问存储，不能直接操作 registry 数据结构
3. **门面保持向后兼容**: `knowledge/__init__.py` 保持现有导出路径，现有 import 不受影响
4. **测试同步拆分**: `tests/test_knowledge_*.py` 按 `tests/store/` 和 `tests/process/` 分组

## 新增 Process 的准入规则

任何新增 Knowledge Process 必须：
1. 创建在 `process/` 子目录下
2. 只通过 `knowledge_abi.py` 访问存储
3. 注册到 `__init__.py` 门面导出
4. 有独立测试文件

## 未来可扩展的 Process

- `compression.py` — 知识压缩/合并
- `conflict_resolution.py` — 知识冲突裁决
- `inference.py` — 基于知识的推理（非 LLM 版本）

## 不做的范围

- 不拆分 `knowledge_abi.py`（保持单一 ABI 门面）
- 不引入新的数据库/存储后端（仍然是内存 + Event Store）
- 不修改 existing tests 的导入路径（向后兼容）
