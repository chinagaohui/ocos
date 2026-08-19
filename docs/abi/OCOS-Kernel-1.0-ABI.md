# OCOS Kernel 1.0 ABI

**版本**: 1.0
**冻结日期**: 2026-07-20
**状态**: Frozen

---

## 一、内核不可变区域 (Kernel Immutable Zone)

以下模块的任何修改必须经过 Architecture Review：

| 模块 | 不可变性 |
|------|----------|
| `contracts/event.py` | Event 结构 |
| `contracts/decision.py` | Decision 结构 |
| `contracts/validation.py` | ValidationResult 结构 |
| `reality/event_store.py` | append/load_stream/snapshot API |
| `cognition/constitution.py` | can_commit/validate/assert_invariant |
| `cognition/decision.py` | Decision 作为唯一写入口 |

## 二、能力接入边界 (Capability Boundary)

### 允许接入
- `capability/` — 外部能力提供者（LLM、工具、人类专家）
- `reasoning/` — 候选方案生成与权衡（不修改 Decision）
- `adaptation/` — 性能监控与改进提案（不执行修改）
- 未来 `agent/` — 多 Agent 协作（必须通过 Decision 写入）

### 禁止行为
- 绕过 Event Store 直接修改状态
- 绕过 Constitution 直接写入 Event Store
- 绕过 Decision 直接执行动作
- Capability 层输出直接进入 Knowledge/Principle 层

## 三、数据流向约束

```
允许: 上层 → 下层 (通过 Contract 转换)
禁止: 下层 → 上层 (直接导入)
允许: 同层模块间通信 (通过 EventBus)
禁止: 跨层直接调用
```

## 四、删除回退保证

| 删除层 | 系统应回退到 |
|--------|-------------|
| `adaptation/` | Phase 5 (575 tests) |
| `capability/` | Phase 4 (528 tests) |
| `principle/` | Phase 2 (442 tests) |
| `pattern/` | Phase 1 (320 tests) |
| `experience/` + `learning/` | Phase 0 (186 tests) |

删除验证已纳入 CI（`tests/kernel/test_architecture_rules.py`）。
