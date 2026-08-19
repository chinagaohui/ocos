"""Phase 26 — GoalParser: 自然语言 → UserGoal。

纯规则解析，不依赖 LLM。提取：
  - objective: 核心目标
  - domain: writing/analysis/research/development
  - constraints: 约束条件
  - priority: 1-5
  - success_criteria: 成功标准
"""

from __future__ import annotations

import re

from ocos.goal.models import GoalDomain, SuccessCriteria, UserGoal


class GoalParser:
    """自然语言 Goal 解析器。"""

    # ── domain 关键词匹配 ──
    DOMAIN_KEYWORDS: dict[GoalDomain, list[str]] = {
        GoalDomain.WRITING: [
            "小说", "写作", "创作", "文章", "写", "故事", "章节",
            "故事", "作品", "文案", "剧情",
        ],
        GoalDomain.ANALYSIS: [
            "分析", "评估", "审核", "审查", "诊断",
        ],
        GoalDomain.RESEARCH: [
            "研究", "调查", "探索", "调研",
        ],
        GoalDomain.DEVELOPMENT: [
            "开发", "构建", "实现", "编程", "代码", "模块", "系统",
        ],
    }

    # ── priority 关键词 ──
    PRIORITY_INDICATORS: dict[str, int] = {
        "紧急": 5, "urgent": 5, "尽快": 5,
        "重要": 4, "important": 4,
        "优先": 3, "priority": 3,
    }

    # ── 数字提取 ──
    NUMBER_PATTERN = re.compile(r"(\d+)\s*([万字kK]+)")

    @classmethod
    def parse(cls, raw_input: str) -> UserGoal:
        """解析自然语言输入为 UserGoal。"""
        # 1. domain 检测
        domain = cls._detect_domain(raw_input)

        # 2. objective 提取（去掉"请"/"帮我"等前缀）
        objective = cls._extract_objective(raw_input)

        # 3. constraints 提取
        constraints = cls._extract_constraints(raw_input)

        # 4. success_criteria 提取
        criteria = cls._extract_success_criteria(raw_input)

        # 5. priority 推断
        priority = cls._infer_priority(raw_input)

        return UserGoal.create(
            raw_input=raw_input,
            objective=objective,
            domain=domain,
            caller="goal_parser",
            constraints=tuple(constraints),
            success_criteria=tuple(criteria),
            priority=priority,
        )

    @classmethod
    def _detect_domain(cls, text: str) -> GoalDomain:
        """基于关键词检测领域。"""
        scores: dict[GoalDomain, int] = {}
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[domain] = score
        if not scores:
            return GoalDomain.DEVELOPMENT  # default
        return max(scores, key=lambda d: scores[d])

    @classmethod
    def _extract_objective(cls, text: str) -> str:
        """提取核心目标。移除礼貌前缀。"""
        # 移除常见前缀
        for prefix in ["请帮我", "请", "帮我", "帮忙", "来"]:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        # 截断过长的 objective
        if len(text) > 80:
            text = text[:77] + "..."
        return text.strip() or text

    @classmethod
    def _extract_constraints(cls, text: str) -> list[str]:
        """提取数量/条件约束。"""
        constraints: list[str] = []

        # 数字约束
        matches = cls.NUMBER_PATTERN.findall(text)
        for num, unit in matches:
            unit_lower = unit.lower()
            if unit_lower in ("字", "万字", "万"):
                word_count = int(num) * 10000 if unit_lower.startswith("万") else int(num)
                constraints.append(f"字数 ≥ {word_count}")
            elif unit_lower in ("k",):
                constraints.append(f"字数 ≥ {int(num) * 1000}")

        # "主角"/"主题"约束
        if "主角" in text:
            constraints.append("含人物设定要求")
        if "主题" in text:
            constraints.append("含主题要求")

        return constraints

    @classmethod
    def _extract_success_criteria(cls, text: str) -> list[SuccessCriteria]:
        """从文本中提取可验证的成功标准。"""
        criteria: list[SuccessCriteria] = []

        matches = cls.NUMBER_PATTERN.findall(text)
        for num, unit in matches:
            unit_lower = unit.lower()
            if unit_lower in ("字", "万字", "万"):
                word_count = int(num) * 10000 if unit_lower.startswith("万") else int(num)
                criteria.append(
                    SuccessCriteria(
                        description=f"完成草稿 ≥ {word_count} 字",
                        measurable=True,
                        threshold=str(word_count),
                    )
                )

        return criteria

    @classmethod
    def _infer_priority(cls, text: str) -> int:
        """从关键词推断优先级。"""
        max_p = 1
        for kw, p in cls.PRIORITY_INDICATORS.items():
            if kw in text.lower() and p > max_p:
                max_p = p
        return max_p
