"""Phase 24 — Memory Intelligence。

Memory 不是新的存储层，而是认知的沉淀：
  Trace → Experience → Episode → Pattern → Belief

设计原则:
  1. Memory records experience. Memory does not interpret identity.
  2. 所有 Candidate 不可变 (frozen dataclass)
  3. INCOMPLETE 不丢弃 — 保留等待补充
  4. Self 字段从 Phase 24.1 开始扫描
"""