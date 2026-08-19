# ADR-016: Knowledge Plane Freeze

## 上下文

OCOS Platform Roadmap v2.0 将 Knowledge Plane 拆分为 M0–M4 五个阶段。截至冻结日：
- M0 (Knowledge Ontology): 原子单元定义 + 提升关系冻结
- M0.5 (Promotion Rules): 提升触发条件/权限/条件冻结
- M1 (Knowledge Ownership): 注册中心边界 + 权限矩阵冻结
- M2 (ABI + Lifecycle): 接口定义 + 状态机冻结
- M3 (Validation + Evolution): 验证器 + 提案流程冻结

## 决策

冻结 `ocos.knowledge.*` 全部模块为 OCOS Platform v1.0 的稳定基石。

## 理由

1. **架构完整性**: Knowledge Plane 是 OCOS 的元认知层，不冻结则后续 Runtime (B1-B6) 和 Platform (C1-D4) 的依赖不稳定
2. **测试覆盖率**: 121 个单元测试全部通过，零失败
3. **审计通过率**: AFP F1-F14 共 68 项检查全部通过
4. **API 稳定性**: `__init__.py` 已设置完整公开导出，内部实现可独立演进

## 替代方案

| 方案 | 评价 |
|------|------|
| 延迟冻结直到 B1 | 风险：后续开发会不断修改 knowledge 接口，引入行为漂移 |
| 部分冻结（只冻 M0+M2）| 拒绝：验证和演化是知识平面的核心能力，不冻结会留下架构缺口 |

## 后果

- ✅ **正向**: Runtime 开发可在稳定 Knowledge ABI 上构建
- ✅ **正向**: 任何对 Knowledge Plane 的修改必须经过 AFP 豁免流程
- ⚠️ **注意**: PromotionRuleEngine 当前为最小实现，未来 Policy 扩展需遵循 F13 防火墙规则

## 验证结果

```
审计: tests/phase16/knowledge_freeze_audit.py → 68/68 ✅
回归: ocos/tests/test_knowledge*.py → 121/121 ✅
```

## 关联文件

| 文件 | 说明 |
|------|------|
| `audit/phase16_knowledge_freeze_certificate.md` | 冻结证书 |
| `tests/phase16/knowledge_freeze_audit.py` | 审计脚本 |
| `ocos/knowledge/__init__.py` | 公开 API 导出 |
| `docs/PLATFORM_ROADMAP.md` | 路线图 v2.0 |

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-22 | Knowledge Plane 全部 7 个模块冻结 M4 认证通过 |
