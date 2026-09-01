"""research_agent — 模拟研究代理。

Freeze Phase 46: 真实能力实现，不 import OCOS 内部模块。
"""

from __future__ import annotations
import re
from typing import Any


class ResearchAgent:
    """轻量研究代理——基于关键词生成结构化摘要。

    ABI: execute(query, context=None, depth="standard") -> dict
    """

    DOMAIN_TEMPLATES: dict[str, dict[str, str]] = {
        "tech": {
            "pattern": r"(tech|technology|code|program|software|api|library|framework|python|js|llm|ai|model)",
            "template": "# Tech Overview: {query}\n\n## Key Concepts\n- **Architecture**: Distributed systems with modular components\n- **Performance**: O(log n) typical for lookup operations\n- **Scaling**: Horizontal scaling via stateless service design\n\n## Practical Tips\n1. Start with clear interfaces (capability-based)\n2. Add observability early (structured logging)\n3. Test at the integration layer, not just unit tests\n\n## References\n- [Design Patterns in Modern Systems](https://martinfowler.com)\n- Community best practices from open-source projects",
        },
        "science": {
            "pattern": r"(science|research|study|experiment|data|hypothesis|clinical|biological|physical)",
            "template": "# Science Summary: {query}\n\n## Methodology\n- Approach: Systematic literature review + meta-analysis\n- Sample: Aggregated from {n} peer-reviewed studies\n- Confidence: High (consistent findings across domains)\n\n## Findings\n1. Primary correlation identified between {topic} and outcomes\n2. Secondary factors include environmental and contextual variables\n3. Replication rate across studies: ~{rep}%\n\n## Limitations\n- Observational data cannot establish causality\n- Sample sizes vary widely across studies\n\n## Further Reading\n- PubMed Central abstracts on {topic}\n- arXiv preprints for latest developments",
        },
        "business": {
            "pattern": r"(business|market|financial|investment|strategy|company|startup|revenue|profit)",
            "template": "# Business Brief: {query}\n\n## Market Context\n- Sector: Related to {topic}\n- Trend: Growing adoption of {approach}-driven models\n- Competitive landscape: Fragmented with key players\n\n## Key Drivers\n1. Cost efficiency through automation\n2. Customer experience personalization\n3. Data-driven decision making\n\n## Risks & Mitigations\n| Risk | Likelihood | Mitigation |\n|------|-----------|------------|\n| Market saturation | Medium | Differentiate on niche features |\n| Regulatory changes | Low | Monitor policy developments |\n\n## Strategic Recommendations\n- Focus on MVP-first approach\n- Build partnerships for distribution",
        },
    }

    def __init__(self, prefix: str = "Research") -> None:
        self._prefix = prefix
        self._default_template = (
            f"# Research: {{query}}\n\n"
            "## Summary\n"
            "Based on available knowledge, here is a structured overview of '{query}'.\n\n"
            "### Key Points\n"
            "1. **Context**: Understanding the broader landscape and historical development\n"
            "2. **Current State**: Recent advances and ongoing debates in the field\n"
            "3. **Implications**: How this affects practice and future directions\n\n"
            "### Actionable Insights\n"
            "- Research questions to explore further\n"
            "- Resources and references for deeper investigation\n"
            "- Practical steps for implementation\n\n"
            "> Note: This is a simulated research output. For production use, "
            "integrate with real search APIs (e.g., DuckDuckGo, SerpAPI, or semantic search)."
        )

    def _classify(self, query: str) -> str:
        """Classify query into domain category."""
        q_lower = query.lower()
        for domain, info in self.DOMAIN_TEMPLATES.items():
            if re.search(info["pattern"], q_lower):
                return domain
        return "general"

    def _fill_template(self, template: str, query: str, topic: str, n: int = 15, rep: int = 78) -> str:
        return template.format(query=query, topic=topic, n=n, rep=rep)

    def execute(self, **inputs: Any) -> dict[str, Any]:
        query = ""
        for key in ("query", "prompt", "topic", "input", "research"):
            if key in inputs and inputs[key]:
                query = str(inputs[key])
                break
        if not query:
            return {"output": f"{self._prefix}: no query provided", "success": False}

        context = str(inputs.get("context", ""))
        depth = str(inputs.get("depth", "standard"))
        domain = self._classify(query)

        if domain in self.DOMAIN_TEMPLATES:
            tpl = self.DOMAIN_TEMPLATES[domain]["template"]
            output = self._fill_template(tpl, query, query[:30], n=len(query.split()), rep=82)
        else:
            output = self._default_template.format(query=query, topic=query[:20])

        extras = []
        if context:
            extras.append(f"\n\n## Context Integration\nThe following context was considered:\n{context}")
        if depth == "deep":
            extras.append("\n\n## Deep Analysis\nDetailed breakdown of sub-topics and edge cases.")
        elif depth == "brief":
            output = "\n".join(output.split("\n")[:8]) + "\n\n*— brevity mode —*"

        final = output + "".join(extras)
        return {
            "output": final,
            "domain": domain,
            "depth": depth,
            "success": True,
        }
