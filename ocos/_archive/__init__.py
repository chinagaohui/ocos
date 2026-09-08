"""ocos._archive — 架构收敛冻结快照（ARCHIVED，非生产代码）。

来源: docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md (FROZEN DECISION) P1 批次。
本命名空间为冻结快照:
  - 不被 pytest 收集、不被任何生产 import;
  - 模块间 import 不保证可运行（历史快照仅作追溯）;
  - 严禁从中 import 进生产路径（违冻条款见来源文档第七节）。
处置批次: P1 (2026-09-08) — 依据 A-J 二级审计五档定级。
"""
