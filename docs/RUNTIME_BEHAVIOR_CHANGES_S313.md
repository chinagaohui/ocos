# 运行时行为变更说明（S3.13，2026-09-06）

> 修复方案评审版 Sprint 3 收尾项。本批为**有意的默认值变更**，
> 环境变量可整体回退，代码无需 revert。

## 1. 审批默认值：auto → ask

- 变更：`OCOS_APPROVAL_MODE` 未设置时，ASK 类动作
  （WRITE_CHAPTER / SEARCH_WEB / RUN_COMMAND / HTTP_FETCH）与
  低置信 DAG 写类任务现在**进入待批队列等待人工批准**（`ocos approvals approve`），
  不再自动执行。
- 不受影响：只读 AUTO 类动作照常自动执行；FILE_WRITE 在两种模式下
  均强制审批（S1.1）。
- 回滚开关：`OCOS_APPROVAL_MODE=auto`（恢复旧行为，daemon 启动时
  打印警告横幅）。
- 生产部署注意：需人工消化 pending_actions 队列，或明确设置 auto
  并接受无人工审批风险（生产验证报告 §六 的建议为 ask）。

## 2. 经验边界门控默认：仅记录 → 阻断

- 变更：`OCOS_EXPERIENCE_BOUNDARY_STRICT` 未设置时，Self 污染候选
  （第一人称/身份归因/行为准则语汇）状态置 REJECTED，
  SignificanceGate 直接 FAIL，**不再写入 Episode**。
- 回滚开关：`OCOS_EXPERIENCE_BOUNDARY_STRICT=false`（恢复仅记录）。

## 3. 相关连带

- daemon 启动横幅：仅在 auto 模式下打印警告（新默认 ask 不再打印）。
- API GET /ocos/goal/{id}：不存在目标返回 404（原 TBD 占位恒 200）。
- 恢复数据目录：/tmp → ~/.ocos/recovery（旧 /tmp 数据不迁移，视为易失）。
