"""OCOS Capability Agents — 真实子代理实现。

Freeze Phase 46: 每个 agent 实现统一 ABI `execute(**inputs) -> dict`。
不 import 任何 OCOS 内部模块（单向依赖原则）。
"""

from ocos.capability.agents.research_agent import ResearchAgent
from ocos.capability.agents.code_agent import CodeAgent
from ocos.capability.agents.summarizer_agent import SummarizerAgent
from ocos.capability.agents.planner_agent import PlannerAgent

__all__ = [
    "ResearchAgent",
    "CodeAgent",
    "SummarizerAgent",
    "PlannerAgent",
]
