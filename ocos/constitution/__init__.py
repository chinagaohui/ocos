"""OCOS Constitution Layer — Phase 24-B 单向流加固。

§2 禁令矩阵:
  L1: 调用者身份验证 (→ PermissionGateway)
  L2: 内部模块隔离 (→ import rules)
  L3: 外部输出净化 (→ StatementValidator)
  L4: 反向控制检测 (→ PermissionGateway)
  L5: 语句层面禁止词汇 (→ StatementValidator)
  L6: Belief 禁止声明 (→ memory.belief)

单向流原则: Self 层零外部导入验证 (→ test_import_rules)
"""
