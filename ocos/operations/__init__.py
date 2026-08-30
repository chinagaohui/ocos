# operations — OCOS search_ops + sandbox_ops
#
# 分工裁决（AUD-F5, 2026-08-30）:
#   本包（Phase 22-E）= 高危操作的安全执行层 —— 命令黑名单(30+) + 白名单前缀
#   + 路径沙盒 + URL/API 白名单 + 审计，通过后真实执行（subprocess/urllib）。
#   ocos/digital_world/（Phase 29）= 面向"数字世界"语义的宽操作库
#   （file/git/api/db/search/sandbox，默认 dry_run，DLQ 审计）。
#
#   两者非重复实现：operations 是"默认闭合、白名单优先"的执行闸门模型，
#   与 DecisionBridge（ocos/execution）的 AUTO/ASK/DENY 风险分级天然契合，
#   定位为未来高危能力（shell/HTTP）经 ASK 批准后的执行层候选；
#   digital_world 是宽语义操作面，维持 dry_run 默认。
#
#   现状：两者当前均无生产调用者（仅 gate 脚本与测试引用）——接线时按上述
#   分工选择，不合并。
