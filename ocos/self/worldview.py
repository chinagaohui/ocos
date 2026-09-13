"""P1-1 G1: WorldView — SelfModel 第六组件容器。

回答: "我如何理解世界/领域如何运作与我应如何判断？"

不是 Knowledge Store / KnowledgeBoundary（知识内容与置信度），而是 OCOS 自己
拥有的、由真实经历经 Recognition 形成的高层主体性理解框架（对齐 P1-1 Semantic
Contract §2）。G1 只做物理座位：容器保持哑（declare/get），Revision 语义由调用方
构造新 judgment 并带 continuity（与 KnowledgeBoundary 风格一致），不引入新 authority。

结构:
    judgments  — 每域一份 WorldViewJudgment（dict[domain, WorldViewJudgment]）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import WorldViewJudgment


@dataclass
class WorldView:
    """SelfModel 的世界观容器 — 每个领域当前一份立场。

    设计决策（G1 Shape Design §3.4）:
        - key = domain；每域当前一份立场（多立场/域 → G3+，不在 G1）
        - 容器操作保持哑：Revision 语义由调用方构造新 judgment 并带 continuity
    """

    judgments: dict[str, WorldViewJudgment] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.judgments)

    @property
    def overall_confidence(self) -> float:
        """整体立场置信度（均值）；空 → 0.5（对齐 KnowledgeBoundary 空态约定）。"""
        if not self.judgments:
            return 0.5
        confidences = [j.confidence for j in self.judgments.values()]
        return sum(confidences) / len(confidences)

    def get(self, domain: str) -> Optional[WorldViewJudgment]:
        return self.judgments.get(domain)

    def declare(self, judgment: WorldViewJudgment) -> None:
        """声明/替换一个领域的立场（按 domain 插/换）。"""
        self.judgments[judgment.domain] = judgment

    def summary(self) -> str:
        return (
            f"WorldView: {self.count} domain stances, "
            f"confidence={self.overall_confidence:.2f}"
        )


__all__ = ["WorldView"]
