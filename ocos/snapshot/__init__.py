"""ocos/snapshot/ — agent 专用快照(SQLite)。

职责分工(GAP-P3-2 裁决): 本包 = agent 专用快照(SQLite 落盘,
生产路径在用, SnapshotManager.save/load_latest/mark_recovered +
CrashRecovery.recover, resurrection_drill 演练依赖);
ocos/persistence/ = 通用多域快照框架(JSON 落盘, Phase 51 契约
测试锁定)。两套并存、职责不重叠, 不作合并; 统一抽象收敛留待
后续阶段, 不在 GAP-P3 范围内。
"""
