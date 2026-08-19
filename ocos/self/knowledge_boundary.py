"""Phase 40: KnowledgeBoundary — 知识边界认知。

回答: "我知道什么？"

不是 Knowledge Store（知识内容），而是对知识状态的认知。
Knowledge Store 存内容，KnowledgeBoundary 存"我对这些内容的信心"。

结构:
    known_domains        — 确信掌握
    uncertain_domains    — 不确定
    missing_information  — 已知缺失
    verification_required — 需要外部验证
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import DomainStatement, KnowledgeConfidence


@dataclass
class KnowledgeBoundary:
    """SelfModel 的知识边界认知。

    每个域有三层:
        domain     — 领域名称
        confidence — 置信级别 (KNOWN/UNCERTAIN/PARTIAL/SURFACE/UNKNOWN/NEEDS_VERIFICATION)
        evidence   — 证据数量
    """

    domains: dict[str, DomainStatement] = field(default_factory=dict)

    # ── 快速分类查询 ──

    @property
    def known_domains(self) -> dict[str, DomainStatement]:
        return {
            k: v for k, v in self.domains.items()
            if v.confidence == KnowledgeConfidence.KNOWN
        }

    @property
    def uncertain_domains(self) -> dict[str, DomainStatement]:
        return {
            k: v for k, v in self.domains.items()
            if v.confidence in (
                KnowledgeConfidence.UNCERTAIN,
                KnowledgeConfidence.PARTIAL,
                KnowledgeConfidence.SURFACE,
            )
        }

    @property
    def needs_verification(self) -> dict[str, DomainStatement]:
        return {
            k: v for k, v in self.domains.items()
            if v.confidence == KnowledgeConfidence.NEEDS_VERIFICATION
        }

    @property
    def unknown_domains(self) -> dict[str, DomainStatement]:
        return {
            k: v for k, v in self.domains.items()
            if v.confidence == KnowledgeConfidence.UNKNOWN
        }

    @property
    def total_domains(self) -> int:
        return len(self.domains)

    @property
    def overall_confidence(self) -> float:
        """整体知识置信度 (KNOWN 域比例)。"""
        if not self.domains:
            return 0.5
        return len(self.known_domains) / len(self.domains)

    # ── 操作 ──

    def declare(self, stmt: DomainStatement) -> None:
        """声明一个知识域的认知。"""
        self.domains[stmt.domain] = stmt

    def get(self, domain: str) -> Optional[DomainStatement]:
        return self.domains.get(domain)

    def is_known(self, domain: str) -> Optional[bool]:
        """返回是否确信掌握该域，None = 未声明。"""
        stmt = self.domains.get(domain)
        if stmt is None:
            return None
        return stmt.confidence == KnowledgeConfidence.KNOWN

    def downgrade(self, domain: str, new_confidence: KnowledgeConfidence,
                  reason: str, tick_id: int) -> None:
        """降级知识置信度。"""
        if domain in self.domains:
            stmt = self.domains[domain]
            self.domains[domain] = DomainStatement(
                domain=domain,
                confidence=new_confidence,
                evidence_count=stmt.evidence_count,
                last_updated_tick=tick_id,
                note=reason,
            )

    def mark_needs_verification(self, domain: str, tick_id: int) -> None:
        """标记需要外部验证。"""
        if domain in self.domains:
            self.downgrade(domain, KnowledgeConfidence.NEEDS_VERIFICATION,
                           "marked for verification", tick_id)

    def summary(self) -> str:
        return (
            f"KnowledgeBoundary: {len(self.known_domains)} known, "
            f"{len(self.uncertain_domains)} uncertain, "
            f"{len(self.unknown_domains)} unknown, "
            f"{len(self.needs_verification)} needs verification"
        )
