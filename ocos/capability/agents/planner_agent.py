"""planner_agent — 任务规划代理。

Freeze Phase 46: 纯逻辑实现，不 import OCOS 内部模块。
"""

from __future__ import annotations
import re
from typing import Any


class PlannerAgent:
    """将复杂目标分解为有序子任务的规划代理。

    ABI: execute(goal, context=None, max_subtasks=5) -> dict
    """

    DETECTORS: list[tuple[str, re.Pattern, str]] = [  # type: ignore[type-arg]
        (r"(code|program|software|api|implement|build|develop)", "software", "Implementation"),
        (r"(write|essay|article|blog|book|document|report)", "writing", "Writing"),
        (r"(research|investigate|find|gather|survey|analyze data)", "research", "Research"),
        (r"(plan|schedule|organize|coordinate|design process)", "planning", "Planning"),
        (r"(test|debug|fix|verify|validate|qa)", "testing", "Quality Assurance"),
        (r"(teach|explain|tutorial|course|lesson)", "education", "Education"),
    ]

    def __init__(self, prefix: str = "Planner") -> None:
        self._prefix = prefix

    def _detect_domain(self, goal: str) -> str:
        for pattern, domain, label in self.DETECTORS:
            if re.search(pattern, goal, re.IGNORECASE):
                return domain
        return "general"

    def _generate_tasks(self, goal: str, domain: str, max_subtasks: int) -> list[dict]:
        """根据领域生成标准任务模板。"""
        templates: dict[str, list[dict]] = {
            "software": [
                {"description": "Gather requirements and define scope", "type": "analysis", "priority": 3},
                {"description": "Design architecture and data models", "type": "design", "priority": 2},
                {"description": "Implement core logic and interfaces", "type": "implementation", "priority": 1},
                {"description": "Write tests and verify correctness", "type": "testing", "priority": 1},
                {"description": "Deploy and monitor production", "type": "deployment", "priority": 2},
            ],
            "writing": [
                {"description": "Define target audience and purpose", "type": "planning", "priority": 3},
                {"description": "Research key topics and gather sources", "type": "research", "priority": 2},
                {"description": "Create outline and structure", "type": "design", "priority": 2},
                {"description": "Draft the first version", "type": "writing", "priority": 1},
                {"description": "Edit, polish, and format", "type": "editing", "priority": 1},
            ],
            "research": [
                {"description": "Define research question and hypothesis", "type": "planning", "priority": 3},
                {"description": "Conduct literature search", "type": "research", "priority": 2},
                {"description": "Collect and organize data", "type": "collection", "priority": 2},
                {"description": "Analyze results and draw conclusions", "type": "analysis", "priority": 1},
                {"description": "Write findings report", "type": "writing", "priority": 1},
            ],
            "testing": [
                {"description": "Identify test scope and coverage goals", "type": "planning", "priority": 3},
                {"description": "Design test cases and scenarios", "type": "design", "priority": 2},
                {"description": "Execute manual test cases", "type": "execution", "priority": 1},
                {"description": "Run automated test suite", "type": "automation", "priority": 1},
                {"description": "Document bugs and track fixes", "type": "reporting", "priority": 1},
            ],
        }
        default = [
            {"description": "Clarify requirements and constraints", "type": "analysis", "priority": 3},
            {"description": "Break goal into ordered sub-tasks", "type": "planning", "priority": 2},
            {"description": "Execute sub-tasks in priority order", "type": "execution", "priority": 1},
            {"description": "Verify outputs and validate results", "type": "verification", "priority": 1},
            {"description": "Document outcomes and lessons learned", "type": "reporting", "priority": 2},
        ]
        tasks = templates.get(domain, default)
        return tasks[:max_subtasks]

    def execute(self, **inputs: Any) -> dict[str, Any]:
        goal = ""
        for key in ("goal", "prompt", "task", "input", "text"):
            if key in inputs and inputs[key]:
                goal = str(inputs[key])
                break
        if not goal:
            return {"output": f"{self._prefix}: no goal provided", "success": False}

        context = str(inputs.get("context", ""))
        max_subtasks = min(int(inputs.get("max_subtasks", 5)), 10)

        domain = self._detect_domain(goal)
        tasks = self._generate_tasks(goal, domain, max_subtasks)

        lines: list[str] = [
            f"# Plan for: {goal}",
            f"Domain: {domain}",
            f"Sub-tasks: {len(tasks)}/{max_subtasks}",
            "",
            "| # | Type | Description | Priority |",
            "|---|------|-------------|----------|",
        ]
        for i, t in enumerate(tasks, 1):
            pbar = "HIGH" if t["priority"] <= 2 else "MED" if t["priority"] <= 3 else "LOW"
            lines.append(f"| {i} | {t['type']} | {t['description']} | {pbar} |")

        if context:
            lines += [
                "",
                "## Context Considerations",
                f"- {context[:300]}",
            ]

        lines += [
            "",
            f"> Generated by {self._prefix}. "
            "For production use, integrate with planning APIs (e.g., OpenTale pipeline).",
        ]

        return {
            "output": "\n".join(lines),
            "domain": domain,
            "task_count": len(tasks),
            "success": True,
        }
