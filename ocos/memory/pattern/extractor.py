"""Phase 24.3-A — Pattern Extractor。

从 Episode 集合中提取 PatternCandidate。

提取规则:
    1. 至少 3 个 Episode 共享相似条件 → pattern
    2. 或: 单个 Episode prediction_error > 0.8 + reflection → 异常 pattern
    3. 必须存在"条件 → 结果"因果链
    4. 提取物不含 Self 语义

使用:
    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from ocos.memory.episode.models import Episode
from ocos.memory.pattern.models import PatternCandidate, PatternStatus


class PatternExtractor:
    """从 Episode 集合中提取 PatternCandidate。"""

    def __init__(self, min_samples: int = 3, single_event_threshold: float = 0.8) -> None:
        self.min_samples = min_samples
        self.single_event_threshold = single_event_threshold

    def extract(self, episodes: list[Episode]) -> list[PatternCandidate]:
        """从 Episode 列表中提取所有 PatternCandidate。

        分两步:
            1. 聚合提取: 寻找 3+ 共享条件组
            2. 异常提取: 寻找高 significance 单事件
        """
        candidates: list[PatternCandidate] = []

        if not episodes:
            return candidates

        # Step 1: 聚合提取
        candidates.extend(self._extract_aggregated(episodes))

        # Step 2: 异常提取
        candidates.extend(self._extract_anomalies(episodes))

        return candidates

    # ── 聚合提取 ──────────────────────────────────────────────────────────

    def _extract_aggregated(self, episodes: list[Episode]) -> list[PatternCandidate]:
        """按 condition 分组，提取重复 Pattern。"""
        # 归一化 condition 并分组
        groups: dict[str, list[Episode]] = defaultdict(list)
        for ep in episodes:
            key = self._normalize_condition(ep.condition)
            if key:
                groups[key].append(ep)

        candidates: list[PatternCandidate] = []

        for condition_key, group in groups.items():
            if len(group) < self.min_samples:
                continue

            # 检查是否共享 outcome
            outcome_groups = self._group_by_outcome(group)
            for outcome_key, outcome_eps in outcome_groups.items():
                if len(outcome_eps) < self.min_samples:
                    continue

                candidate = self._build_candidate(
                    condition_key=condition_key,
                    outcome_key=outcome_key,
                    episodes=outcome_eps,
                    source="episode_aggregation",
                )
                candidates.append(candidate)

        return candidates

    # ── 异常提取 ──────────────────────────────────────────────────────────

    def _extract_anomalies(self, episodes: list[Episode]) -> list[PatternCandidate]:
        """提取高 significance 单事件 Pattern。跳过空 condition 的 Episode。"""
        candidates: list[PatternCandidate] = []

        for ep in episodes:
            condition_key = self._normalize_condition(ep.condition)
            if not condition_key:
                continue  # 跳过空 condition

            if ep.significance_score < self.single_event_threshold:
                continue

            # 需要 prediction_error 维度在 evaluation_trace 中分数较高
            trace = ep.evaluation_trace
            dims = trace.get("dimensions", {})
            pred_error = dims.get("prediction_error", 0)

            if pred_error < self.single_event_threshold:
                continue

            candidate = self._build_candidate(
                condition_key=condition_key,
                outcome_key=str(ep.outcome.get("error", "anomaly")),
                episodes=[ep],
                source="single_anomaly",
            )
            candidates.append(candidate)

        return candidates

    # ── 辅助 ──────────────────────────────────────────────────────────────

    def _build_candidate(
        self,
        condition_key: str,
        outcome_key: str,
        episodes: list[Episode],
        source: str,
    ) -> PatternCandidate:
        """从一组 Episode 构建 PatternCandidate。"""
        n = len(episodes)
        avg_significance = sum(e.significance_score for e in episodes) / n

        # 置信度: 基于样本量和平均 significance
        confidence = min(1.0, (n / self.min_samples) * avg_significance)

        # 构建因果解释
        causal = self._describe_causal(condition_key, outcome_key, episodes)

        return PatternCandidate.create(
            trigger_condition=condition_key,
            observed_relation=outcome_key,
            causal_explanation=causal,
            confidence=confidence,
            supporting_episode_count=n,
            source=source,
        )

    @staticmethod
    def _normalize_condition(condition: str) -> str:
        """归一化 condition 字符串。"""
        if not condition:
            return ""
        # 去掉 Episode ID 引用和多余空格
        cleaned = condition.strip()
        # 截断过长 condition
        if len(cleaned) > 100:
            cleaned = cleaned[:97] + "..."
        return cleaned

    @staticmethod
    def _group_by_outcome(episodes: list[Episode]) -> dict[str, list[Episode]]:
        """按 outcome 分组 Episode。"""
        groups: dict[str, list[Episode]] = defaultdict(list)
        for ep in episodes:
            outcome = ep.outcome
            success = outcome.get("success", False)
            error = outcome.get("error", "")
            result = outcome.get("result", "")

            if error:
                key = f"error: {error}"
            elif not success:
                key = "failure"
            elif result:
                key = f"success: {str(result)[:40]}"
            else:
                key = "success"

            groups[key].append(ep)
        return groups

    @staticmethod
    def _describe_causal(
        condition_key: str,
        outcome_key: str,
        episodes: list[Episode],
    ) -> str:
        """生成因果解释文本。"""
        decisions = set()
        for ep in episodes:
            if ep.decision:
                decisions.add(ep.decision)

        decision_str = " / ".join(sorted(decisions)[:3])
        if decision_str:
            return (
                f"Under condition '{condition_key}', "
                f"the selected approach ({decision_str}) "
                f"resulted in '{outcome_key}' "
                f"across {len(episodes)} occurrence(s)."
            )
        else:
            return (
                f"Under condition '{condition_key}', "
                f"observed outcome '{outcome_key}' "
                f"across {len(episodes)} occurrence(s)."
            )
