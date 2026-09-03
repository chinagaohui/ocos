"""metacognition — 元认知与泛化 (Blueprint L7/L8, Phase 49-D).

Freeze Phase 49-D: 纯逻辑实现 + 有限 OCOS 类型依赖。

职责:
  L7 (D1): SkillSemanticMatcher — 跨表面形式技能迁移
           (Generalization = Cross-surface transfer with preserved semantics)
  L8 (D2): CapabilityConfidence — 历史成功率查询 + 决策保守化建议
           (Metacognition 只调置信度/升级 ASK, 不授权 — 治理增强非削弱)

治理纪律 (Blueprint v1.1 §9/§10):
  - 低置信写类动作 → 升级 ASK (更严, 非放宽)
  - Metacognition 产物无 Action 路径
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# L7 — Skill 语义匹配 (Cross-surface Transfer)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SkillMatch:
    """语义匹配结果。"""

    skill_id: str
    skill_name: str
    trigger_pattern: str
    procedure: tuple[str, ...]
    similarity: float
    matched: bool

    def summary(self) -> str:
        return (f"skill={self.skill_name} sim={self.similarity:.2f} "
                f"procedure={self.procedure}")


# 语义同义词组 (确定性 — 跨表面形式的关键)
_SEMANTIC_GROUPS = [
    # 环境检查类
    ({"检查", "查看", "查询", "获取", "确认", "check", "inspect",
      "query", "verify", "confirm"},
     "environment-inspection"),
    # 系统状态类
    ({"系统", "状态", "内核", "版本", "磁盘", "内存", "负载", "端口",
      "system", "status", "kernel", "version", "disk", "memory",
      "load", "port", "uptime"},
     "system-state"),
    # 数据分析类
    ({"分析", "统计", "汇总", "趋势", "analyze", "analysis", "stats",
      "summarize", "trend"},
     "data-analysis"),
    # 文件操作类
    ({"读取", "写", "创建", "删除", "read", "write", "create",
      "delete", "file", "目录", "路径"},
     "file-operation"),
]


def _extract_semantic_tags(text: str) -> set[str]:
    """提取任务描述的语义标签 (中英混合, 确定性)。"""
    lower = text.lower()
    tags: set[str] = set()
    for words, tag in _SEMANTIC_GROUPS:
        if any(w in lower or w in text for w in words):
            tags.add(tag)
    return tags


def _surface_tokens(text: str) -> set[str]:
    """表面词元 (用于相似度补充)。"""
    toks = re.findall(r"[a-z0-9]{3,}", text.lower())
    toks += [t for t in re.split(r"[\s,，。:：]+", text)
             if 1 < len(t) <= 8]  # 中文词
    return set(toks)


class SkillSemanticMatcher:
    """L7: 跨表面形式技能迁移匹配器 (无 LLM, 确定性)。

    命中 = 语义标签重叠 (task semantics 保持) + 表面词元 Jaccard 补充,
    而非单纯字符串相同。
    """

    @classmethod
    def match(cls, task_description: str,
              skills: list[Any],
              threshold: float = 0.4) -> Optional[SkillMatch]:
        """在候选技能中找语义匹配。

        Args:
            task_description: 新任务描述 (表面形式可与原技能不同)
            skills: Skill 对象列表 (含 input_state.trigger_pattern /
                    output_state.procedure 或 id/name)
            threshold: 语义标签重合率下限

        Returns:
            SkillMatch 或 None (无匹配)
        """
        if not task_description or not skills:
            return None

        new_tags = _extract_semantic_tags(task_description)
        new_tokens = _surface_tokens(task_description)
        if not new_tags:
            return None

        best: Optional[SkillMatch] = None
        best_score = 0.0

        for skill in skills:
            # 提取技能 trigger (Applicable context)
            trigger = ""
            is_dict = isinstance(skill, dict)
            if is_dict:
                trigger = str(skill.get("trigger_pattern")
                              or skill.get("task_pattern")
                              or skill.get("description") or "")
                proc = tuple(skill.get("procedure") or ())
                sid = str(skill.get("id") or skill.get("rule_id")
                          or skill.get("skill_id") or "")
                sname = str(skill.get("name") or sid)
            else:
                trigger = str(getattr(skill, "description", "")
                              or "")
                ist = getattr(skill, "input_state", None)
                if isinstance(ist, dict):
                    trigger = str(ist.get("trigger_pattern")
                                  or trigger)
                ost = getattr(skill, "output_state", None)
                proc = tuple((ost or {}).get("procedure", ())) \
                    if isinstance(ost, dict) else ()
                sid = getattr(skill, "id", "")
                sname = getattr(skill, "name", sid)

            if not trigger:
                continue

            skill_tags = _extract_semantic_tags(trigger)
            if not skill_tags:
                continue

            # 语义标签重合率 (核心判据 — preserved semantics)
            overlap = len(new_tags & skill_tags)
            union = len(new_tags | skill_tags)
            semantic_sim = overlap / union if union else 0.0

            # 表面词元 Jaccard (弱补充, 不主导)
            skill_tokens = _surface_tokens(trigger)
            tok_inter = len(new_tokens & skill_tokens)
            tok_union = len(new_tokens | skill_tokens)
            token_sim = tok_inter / tok_union if tok_union else 0.0

            # 综合: 语义 70% + 表面 30%
            score = 0.7 * semantic_sim + 0.3 * token_sim

            if score > best_score:
                best_score = score
                best = SkillMatch(
                    skill_id=sid,
                    skill_name=sname,
                    trigger_pattern=trigger[:60],
                    procedure=proc,
                    similarity=round(score, 3),
                    matched=score >= threshold,
                )

        if best is not None and best.matched:
            return best
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# L8 — CapabilityConfidence (Metacognition → 决策保守化)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ConfidenceVerdict:
    """置信度评估结果 — 供 DecisionBridge 决策前消费。"""

    task_pattern: str
    success_rate: float | None     # None = 无历史
    evidence_count: int
    confidence: float              # 0-1 综合置信
    escalation: str                # "none" | "ask" | "deny" (保守化建议)
    reason: str

    @property
    def should_escalate(self) -> bool:
        return self.escalation == "ask"


# 低置信阈值 — 低于此成功率的写类动作升级 ASK
LOW_CONFIDENCE_THRESHOLD = 0.4
# 最小证据数 — 不足则视为无历史 (不升级, 保持默认分级)
MIN_EVIDENCE = 3


class CapabilityConfidence:
    """L8: 任务类型历史成功率 → 决策保守化建议。

    确定性规则 (无 LLM), 消费 LearningModel.rules:
      - 有历史 + 成功率 < 阈值 + 写类 → 升级 ASK (治理增强)
      - 有历史 + 低成功率 + 只读 → 保持 AUTO (只读仍低风险)
      - 无历史 (证据不足) → 不干预 (默认分级)
    """

    @classmethod
    def _find_matching_rule(cls, task_description: str,
                            learning_rules: list[dict]) -> Optional[dict]:
        """先精确/包含匹配 (归一化), 再语义匹配 (L7 跨表面)。"""
        norm = re.sub(r"\s+", "", task_description).lower()
        # 1. 归一化精确/包含匹配
        for r in learning_rules:
            rp = re.sub(r"\s+", "", str(
                r.get("task_pattern") or r.get("trigger_pattern") or "")).lower()
            if rp and (rp == norm or rp in norm or norm in rp):
                return r
        # 2. 语义匹配 (跨表面形式)
        match = SkillSemanticMatcher.match(
            task_description, learning_rules, threshold=0.3)
        if match is not None and match.matched:
            for r in learning_rules:
                rid = r.get("rule_id") or r.get("id") or ""
                if rid == match.skill_id:
                    return r
                # 兜底: trigger 前缀
                if match.skill_id and str(rid) == match.skill_id:
                    return r
        return None

    @classmethod
    def evaluate(cls, task_description: str,
                 learning_rules: list[dict],
                 task_type: str = "analyze",
                 low_threshold: float = LOW_CONFIDENCE_THRESHOLD,
                 min_evidence: int = MIN_EVIDENCE) -> ConfidenceVerdict:
        """评估某任务的元认知置信度。

        Args:
            task_description: 任务描述
            learning_rules: Phase 49-A LearningModel.rules
            task_type: analyze/verify (只读) | create/modify/execute (写类)
            low_threshold: 低置信阈值
            min_evidence: 最小证据数 (不足=无历史)
        """
        if not learning_rules:
            return ConfidenceVerdict(
                task_pattern=task_description[:60],
                success_rate=None, evidence_count=0,
                confidence=0.5, escalation="none",
                reason="no learning history",
            )

        rule = cls._find_matching_rule(task_description, learning_rules)
        if rule is None:
            return ConfidenceVerdict(
                task_pattern=task_description[:60],
                success_rate=None, evidence_count=0,
                confidence=0.5, escalation="none",
                reason="no semantic rule match",
            )

        succ = int(rule.get("success_count", 0) or 0)
        fail = int(rule.get("fail_count", 0) or 0)
        evidence = succ + fail
        raw_rate = rule.get("success_rate")
        rate = float(raw_rate) if raw_rate is not None else 0.5

        if evidence < min_evidence:
            return ConfidenceVerdict(
                task_pattern=task_description[:60],
                success_rate=rate, evidence_count=evidence,
                confidence=0.5, escalation="none",
                reason=f"insufficient evidence ({evidence}<{min_evidence})",
            )

        is_write = task_type in ("create", "modify", "delete", "execute")
        if is_write and rate < low_threshold:
            return ConfidenceVerdict(
                task_pattern=task_description[:60],
                success_rate=rate, evidence_count=evidence,
                confidence=rate,
                escalation="ask",
                reason=(f"write action with low success_rate "
                        f"{rate:.2f} < {low_threshold} (evidence={evidence})"),
            )

        return ConfidenceVerdict(
            task_pattern=task_description[:60],
            success_rate=rate, evidence_count=evidence,
            confidence=rate,
            escalation="none",
            reason=f"success_rate={rate:.2f} evidence={evidence}",
        )


__all__ = [
    "SkillMatch", "SkillSemanticMatcher",
    "ConfidenceVerdict", "CapabilityConfidence",
    "LOW_CONFIDENCE_THRESHOLD", "MIN_EVIDENCE",
]
