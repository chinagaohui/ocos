"""Phase 24.3-A / COG-V2 Phase 3.2 — Pattern Extractor。

从 Episode 集合中提取 PatternCandidate。

提取规则:
    1. 至少 3 个 Episode 共享相似条件 → pattern
    2. 或: 单个 Episode prediction_error > 0.8 + reflection → 异常 pattern
    3. 必须存在"条件 → 结果"因果链
    4. 提取物不含 Self 语义

COG-V2 Phase 3.2（多维 trigger）:
    旧版按 condition 原文分组，而生产主链 condition 恒为
    "agent=X, success=true/false" 两维 → 只有 N 个 agent × 2 种结局
    的 ~8 条低信息量 pattern 饱和（生产实证）。现改为从结构化
    context/tags 派生多维条件键：
      - 成功侧: task_type × agent（research/build/analysis/file）
      - 失败侧: tool × cause（真正可干预的维度）
    旧的一维 agent+success condition 不再单独成组；其余无结构
    context 的 episode（如 boot_awareness）保留原文分组兜底。

使用:
    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from ocos.memory.episode.models import Episode
from ocos.memory.pattern.models import PatternCandidate, PatternStatus

# 失败 cause 白名单（与 FailureDiagnoser / failure_lesson tags 对齐）
_CAUSE_TOKENS = frozenset({
    "goal_ambiguous", "tool_unavailable", "dependency_missing",
    "execution_error", "timeout", "permission_denied",
    "sql_schema_mismatch", "unknown",
})
_TASK_TYPE_RULES = (
    ("research", re.compile(r"检索|搜索|调研|查阅|文献|论文|资料|research|search|arxiv", re.I)),
    ("build", re.compile(r"开发|构建|实现|编写|部署|代码|脚本|build|implement|deploy", re.I)),
    ("analysis", re.compile(r"分析|评估|诊断|复盘|总结|统计|analy[sz]e|review|audit", re.I)),
    ("file", re.compile(r"文件|目录|读取|写入|备份|file|path", re.I)),
)
_CMD_RE = re.compile(r"(?:^|\n)\s*\$\s+([A-Za-z0-9_./-]+)")
# 一维饱和 condition 形态（本模块多维化后不再单独成组）
_FLAT_AGENT_SUCCESS_RE = re.compile(r"^agent=[^,\s]+,\s*success=(?:true|false)$")


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
        """多维条件分组，提取重复 Pattern（COG-V2 Phase 3.2）。

        每条 episode 经 _dimension_keys() 派生 0-2 个结构化条件键；
        同键 ≥min_samples 且结局一致 → pattern。一条 episode 可同时
        进入"任务类型×agent"与"工具×cause"两组。无结构化键的 episode
        回退原文 condition（显式跳过一维 agent+success 饱和键）。
        """
        # key → {ep.id: (ep, outcome_key)}
        dim_groups: dict[str, dict[str, tuple[Episode, str]]] = defaultdict(dict)
        legacy_groups: dict[str, list[Episode]] = defaultdict(list)
        for ep in episodes:
            keys = self._dimension_keys(ep)
            if keys:
                outcome_key = "success" if ep.outcome.get("success") else "failure"
                for key in keys:
                    dim_groups[key].setdefault(ep.id, (ep, outcome_key))
            else:
                raw = self._normalize_condition(ep.condition)
                if raw and not _FLAT_AGENT_SUCCESS_RE.match(raw):
                    legacy_groups[raw].append(ep)

        candidates: list[PatternCandidate] = []

        # 多维组：结局已编进键后缀，组内结局天然一致
        for condition_key, bucket in dim_groups.items():
            if len(bucket) < self.min_samples:
                continue
            eps = [v[0] for v in bucket.values()]
            outcome_key = "success" if condition_key.endswith("success=true") else "failure"
            candidates.append(self._build_candidate(
                condition_key=condition_key,
                outcome_key=outcome_key,
                episodes=eps,
                source="episode_aggregation",
            ))

        # 兜底组：保留原 condition → outcome 两段分组逻辑
        for condition_key, group in legacy_groups.items():
            if len(group) < self.min_samples:
                continue
            for outcome_key, outcome_eps in self._group_by_outcome(group).items():
                if len(outcome_eps) < self.min_samples:
                    continue
                candidates.append(self._build_candidate(
                    condition_key=condition_key,
                    outcome_key=outcome_key,
                    episodes=outcome_eps,
                    source="episode_aggregation",
                ))
        return candidates

    # ── 多维 trigger（任务类型 / 工具 / cause）──────────────────────────

    def _dimension_keys(self, ep: Episode) -> list[str]:
        """从 episode 结构化字段派生 0-2 个多维条件键。

        成功: task_type=<t>, agent=<a>, success=true
        失败: tool=<tool>, cause=<c>, success=false（cause 缺失时退回
              task_type×agent 失败键）。"""
        ctx = ep.context if isinstance(ep.context, dict) else {}
        success = bool(ep.outcome.get("success"))
        agent = (str(ctx.get("agent") or "").strip()
                 or self._agent_from_action(ep.action))
        text = " ".join(str(x) for x in (
            ep.goal or "", ctx.get("description") or "",
        ) if x)
        task_type = self._task_type(text)
        tags = ep.tags if isinstance(ep.tags, (list, tuple)) else []
        cause = next((str(t) for t in tags
                      if t in _CAUSE_TOKENS and t != "unknown"), "")
        cause = cause or str(ep.outcome.get("cause") or "")
        if cause not in _CAUSE_TOKENS:
            cause = ""

        keys: list[str] = []
        if success:
            if task_type and agent:
                keys.append(
                    f"task_type={task_type}, agent={agent}, success=true")
        else:
            if cause:
                tool = self._tool_of(ep, ctx, agent)
                if tool:
                    keys.append(
                        f"tool={tool}, cause={cause}, success=false")
            if task_type and agent:
                keys.append(
                    f"task_type={task_type}, agent={agent}, success=false")
        return keys

    @staticmethod
    def _agent_from_action(action: str) -> str:
        if not action:
            return ""
        head = action.split(".", 1)[0].strip()
        return head if head and head != action else ""

    @staticmethod
    def _task_type(text: str) -> str:
        for name, rx in _TASK_TYPE_RULES:
            if rx.search(text or ""):
                return name
        return ""

    @staticmethod
    def _tool_of(ep: Episode, ctx: dict, agent: str) -> str:
        hay = "\n".join(str(x) for x in (
            ep.decision or "", ctx.get("output_excerpt") or "",
            ctx.get("description") or "",
        ) if x)
        m = _CMD_RE.search(hay)
        if m:
            return m.group(1).rsplit("/", 1)[-1]
        return agent or ""

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
