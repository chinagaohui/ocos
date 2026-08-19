"""Phase 55: CapabilitySelector — 匹配决策到最佳适配器。

接收 Decision → 匹配 capabilities → 返回最佳 adapter。

选择策略:
    1. 名称精确匹配: decision.target 直接对应 capability name
    2. 分类匹配: 按 CapabilityCategory 筛选
    3. 健康检查: 跳过 FAILED/DISCONNECTED 适配器
    4. 风险排序: 同分类下优先低风险
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability_reality.adapter_types import (
    CapabilityCategory, AdapterHealth,
)
from ocos.capability_reality.capability_registry import (
    CapabilityRegistry, RegisteredCapability,
)


@dataclass
class SelectionResult:
    """选择结果。"""
    matched: bool = False
    capability: RegisteredCapability | None = None
    reason: str = ""
    alternatives: list[RegisteredCapability] = field(default_factory=list)


@dataclass
class CapabilitySelector:
    """能力选择器 — 从注册表中为决策选择最佳适配器。"""

    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)

    def select(self, target: str, category: CapabilityCategory | None = None) -> SelectionResult:
        """选择最佳能力。

        优先级:
            1. 精确名称匹配 (健康)
            2. 分类匹配 (健康, 低风险优先)
            3. 分类匹配 (降级也可接受)
        """

        # 1. 精确匹配
        cap = self.registry.get(target)
        if cap and cap.status.health not in (AdapterHealth.FAILED, AdapterHealth.DISCONNECTED):
            return SelectionResult(
                matched=True,
                capability=cap,
                reason=f"exact match: {target}",
            )

        # 2. 分类匹配
        if category is None:
            # 尝试从 target 推断分类
            category = self._infer_category(target)

        if category:
            candidates = [
                c for c in self.registry.list_by_category(category)
                if c.status.health not in (AdapterHealth.FAILED, AdapterHealth.DISCONNECTED)
            ]
            # 按风险排序 (低风险优先)
            candidates.sort(key=lambda c: c.descriptor.risk_level)

            if candidates:
                return SelectionResult(
                    matched=True,
                    capability=candidates[0],
                    reason=f"category match: {category.value}",
                    alternatives=candidates[1:],
                )

        # 未匹配
        return SelectionResult(
            matched=False,
            reason=f"no matching capability for '{target}'",
        )

    def select_by_intent(self, intent: str) -> SelectionResult:
        """根据意图字符串选择能力。

        意图 → 分类映射:
            "打开文件"/"读取" → filesystem:fs_read
            "运行命令"/"执行" → shell:shell_exec
            "请求API"/"获取数据" → network:http_get
            "写代码"/"生成" → code:code_exec
        """
        intent_lower = intent.lower()

        if any(w in intent_lower for w in ("打开", "读取", "读", "文件", "列表", "列出", "目录",
                                             "list", "ls", "dir", "read", "open", "file", "cat", "show")):
            return self.select("fs_read", CapabilityCategory.FILESYSTEM)
        if any(w in intent_lower for w in ("写入", "写", "保存", "write", "save", "create")):
            return self.select("fs_write", CapabilityCategory.FILESYSTEM)
        if any(w in intent_lower for w in ("运行", "执行", "命令", "run", "exec", "command", "shell")):
            return self.select("shell_exec", CapabilityCategory.SHELL)
        if any(w in intent_lower for w in ("请求", "api", "http", "fetch", "get", "post")):
            return self.select("http_get", CapabilityCategory.NETWORK)
        if any(w in intent_lower for w in ("代码", "编译", "code", "build")):
            return self.select("code_exec", CapabilityCategory.CODE)

        return SelectionResult(matched=False, reason=f"unknown intent: {intent}")

    def _infer_category(self, name: str) -> CapabilityCategory | None:
        """从名称推断分类。"""
        lower = name.lower()
        if any(w in lower for w in ("fs", "file", "path", "dir")):
            return CapabilityCategory.FILESYSTEM
        if any(w in lower for w in ("shell", "exec", "cmd", "run", "bash")):
            return CapabilityCategory.SHELL
        if any(w in lower for w in ("http", "api", "req", "curl", "fetch")):
            return CapabilityCategory.NETWORK
        if any(w in lower for w in ("code", "py", "js", "eval")):
            return CapabilityCategory.CODE
        if any(w in lower for w in ("browser", "selenium", "chrome")):
            return CapabilityCategory.BROWSER
        return None


__all__ = ["CapabilitySelector", "SelectionResult"]
