"""P2-D: Proactive 主动输出模块。

ProactiveEngine — 空闲期主动输出（问候/观察/提问），全确定性触发链：
频率闸门 → SELF 目标待办 → 疲劳闸门 → 模板轮换 → 权限双检 → 输出 → 审计。
无 LLM；Telegram 等外部通道仅留 output_callback 注入接口。
"""

from ocos.proactive.audit import ProactiveAuditStore
from ocos.proactive.engine import ProactiveEngine
from ocos.proactive.templates import TEMPLATE_POOL, ProactiveTemplate, select_template

__all__ = [
    "ProactiveEngine",
    "ProactiveAuditStore",
    "TEMPLATE_POOL",
    "ProactiveTemplate",
    "select_template",
]
