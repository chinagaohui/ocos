"""experience_learning — 经验学习适配器（Blueprint L1/L4 Phase A）。

Freeze Phase 49-A: 纯逻辑实现，不 import OCOS 内部模块（单向依赖原则）。

职责（三合一，全部确定性规则，无 LLM）:
  1. Episode → LearningExample 转换（快通路样本注入）— A1
  2. Failure Diagnoser — 失败原因结构化分类 — A2
  3. 规则型 learn_fn — 从样本聚合成 LearningModel.rules — A3

输出统一为 LearningArtifact 语义（Blueprint v1.1 §1.2）:
    LearningArtifact 是 BELIEF/PATTERN/LESSON/SKILL_CANDIDATE 的统一契约。
    Phase A 只实现 LESSON（失败教训）与 RULE（成功率统计）。

验收对应:
    ER-1 失败样本入库 → LearningArtifact(CANDIDATE, LESSON)
    ER-2 Behavioral Delta — 由调用方（MasterAgent._fast_path_learning）验证
    ER-3 快通路非空 — learn 收到 examples ≥ 1
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# 失败原因分类（A2 — Failure Diagnoser）
# ═══════════════════════════════════════════════════════════════════════════════


class FailureCause(str, Enum):
    """失败原因分类（确定性规则提取）。"""

    AMBIGUOUS_TASK = "ambiguous_task"        # 任务描述模糊，无法转动作
    EXECUTION_ERROR = "execution_error"      # 执行层错误
    PERMISSION_DENIED = "permission_denied"  # 权限拒绝（ASK 未批 / 拦截）
    TIMEOUT = "timeout"                      # 超时
    TOOL_UNAVAILABLE = "tool_unavailable"    # 工具/能力不可用
    LLM_CONVERSION_FAILED = "llm_conversion_failed"  # LLM 无法将描述转动作
    UNKNOWN = "unknown"                      # 无法分类


# 从文本信号分类失败原因（确定性，无 LLM）
_AMBIGUOUS_SIGNALS = [
    "过于模糊", "未指定", "无法执行", "ambiguous", "not specific",
    "no data source", "missing input", "无法转为", "无法转换",
    "cannot execute", "no action", "不清楚",
]
_PERMISSION_SIGNALS = ["permission", "denied", "approval", "待批", "pending_approval", "被拒绝", "blocked"]
_TIMEOUT_SIGNALS = ["timeout", "超时", "timed out"]
_TOOL_SIGNALS = ["not available", "unavailable", "not registered", "no capability", "no tool", "找不到"]
_EXECUTION_SIGNALS = ["exit=", "traceback", "exception", "error", "失败", "failed", "returncode"]


@dataclass(frozen=True)
class FailureDiagnosis:
    """失败诊断结果。"""

    episode_id: str
    cause: FailureCause
    hypothesis: str          # 失败假设（人类可读）
    evidence: str            # 原始失败文本（截断）
    signals_hit: tuple[str, ...] = ()


class FailureDiagnoser:
    """A2: 失败原因诊断器 — Episode.outcome/decision 文本 → 结构化分类。"""

    @classmethod
    def diagnose(cls, episode: Any) -> FailureDiagnosis | None:
        """从 Episode 诊断失败原因。成功或无结果返回 None。"""
        outcome = getattr(episode, "outcome", None) or {}
        decision = getattr(episode, "decision", "") or ""
        # 是否失败
        ok = outcome.get("success", True)
        if ok is not False and ok != 0 and "failed" not in str(decision).lower() \
                and "失败" not in str(decision):
            return None

        # 收集证据文本
        parts: list[str] = []
        if isinstance(outcome, dict):
            for key in ("error", "reason", "result"):
                v = outcome.get(key)
                if v:
                    parts.append(str(v))
        parts.append(str(decision))
        evidence = " ".join(parts)[:500]
        signals_hit: list[str] = []

        cause = FailureCause.UNKNOWN
        for sig in _AMBIGUOUS_SIGNALS:
            if sig in evidence:
                cause = FailureCause.AMBIGUOUS_TASK
                signals_hit.append(sig)
                break
        if cause == FailureCause.UNKNOWN:
            for sig in _PERMISSION_SIGNALS:
                if sig.lower() in evidence.lower():
                    cause = FailureCause.PERMISSION_DENIED
                    signals_hit.append(sig)
                    break
        if cause == FailureCause.UNKNOWN:
            for sig in _TIMEOUT_SIGNALS:
                if sig.lower() in evidence.lower():
                    cause = FailureCause.TIMEOUT
                    signals_hit.append(sig)
                    break
        if cause == FailureCause.UNKNOWN:
            for sig in _TOOL_SIGNALS:
                if sig.lower() in evidence.lower():
                    cause = FailureCause.TOOL_UNAVAILABLE
                    signals_hit.append(sig)
                    break
        if cause == FailureCause.UNKNOWN:
            for sig in _EXECUTION_SIGNALS:
                if sig.lower() in evidence.lower():
                    cause = FailureCause.EXECUTION_ERROR
                    signals_hit.append(sig)
                    break

        # hypothesis 模板
        hypotheses = {
            FailureCause.AMBIGUOUS_TASK: (
                "任务描述缺少可执行的具体动作或数据源，LLM 无法转换为行动"),
            FailureCause.EXECUTION_ERROR: "执行层发生错误（命令/脚本失败）",
            FailureCause.PERMISSION_DENIED: "动作被权限系统拒绝或等待人工审批",
            FailureCause.TIMEOUT: "执行超时",
            FailureCause.TOOL_UNAVAILABLE: "所需工具/能力未注册或不可用",
            FailureCause.LLM_CONVERSION_FAILED: "LLM 无法将任务描述转换为动作",
            FailureCause.UNKNOWN: "失败原因无法从现有证据分类",
        }
        return FailureDiagnosis(
            episode_id=getattr(episode, "id", "unknown"),
            cause=cause,
            hypothesis=hypotheses[cause],
            evidence=evidence,
            signals_hit=tuple(signals_hit),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# A1 — Episode → LearningExample 转换
# ═══════════════════════════════════════════════════════════════════════════════


class EpisodeExampleConverter:
    """A1: Episode → LearningExample 转换器。

    LearningExample.input_data  = {goal/task 描述, 条件}
    LearningExample.output_data = {action/agent/task_type}
    LearningExample.reward      = success ? 1.0 : 0.0
    LearningExample.feedback    = 失败原因（诊断）或成功摘要
    LearningExample.metadata    = {episode_id, task_id, goal_id, source}
    """

    @classmethod
    def convert(cls, episode: Any, diagnosis: FailureDiagnosis | None = None) -> Any:
        """单个 Episode → LearningExample。

        Returns None 若 Episode 缺关键字段（无法构造样本）。
        """
        from ocos.models.learning import LearningExample  # 延迟 import: 类型在 OCOS 层

        goal = getattr(episode, "goal", None) or ""
        outcome = getattr(episode, "outcome", None) or {}
        decision = getattr(episode, "decision", "") or ""
        action = getattr(episode, "action", "") or ""
        context = getattr(episode, "context", None) or {}
        tags = list(getattr(episode, "tags", None) or [])

        task_desc = goal or (decision or "")[:200]
        if not task_desc:
            return None

        success = outcome.get("success", True) if isinstance(outcome, dict) else True
        feedback = ""
        if not success and diagnosis is not None:
            feedback = f"{diagnosis.cause.value}: {diagnosis.hypothesis}"
        elif not success:
            feedback = "failed"
        else:
            feedback = "succeeded"

        return LearningExample(
            input_data={
                "task": task_desc[:300],
                "context": {
                    "agent": context.get("agent", "") if isinstance(context, dict) else "",
                    "tags": tags[:5],
                },
            },
            output_data={
                "action": action[:200] if action else decision[:200],
                "task_type": context.get("task_type", "") if isinstance(context, dict) else "",
            },
            reward=1.0 if success else 0.0,
            feedback=feedback[:200],
            metadata={
                "episode_id": getattr(episode, "id", ""),
                "experience_id": getattr(episode, "experience_id", ""),
                "goal": goal,
                "source": "experience_learning",
            },
        )

    @classmethod
    def convert_many(
        cls, episodes: list[Any]
    ) -> tuple[list[Any], list[FailureDiagnosis], list[Any]]:
        """批量转换: (examples, diagnoses, skipped)。

        失败 Episode 同时产出诊断（A2 融合）。
        """
        examples: list[Any] = []
        diagnoses: list[FailureDiagnosis] = []
        skipped: list[Any] = []
        for ep in episodes:
            try:
                diag = FailureDiagnoser.diagnose(ep)
                ex = cls.convert(ep, diag)
                if ex is None:
                    skipped.append(ep)
                else:
                    examples.append(ex)
                    if diag is not None:
                        diagnoses.append(diag)
            except Exception:
                skipped.append(ep)
        return examples, diagnoses, skipped


# ═══════════════════════════════════════════════════════════════════════════════
# A3 — 规则型 learn_fn（确定性聚合 → LearningModel.rules）
# ═══════════════════════════════════════════════════════════════════════════════


class RuleBasedLearner:
    """规则型学习函数 — 从 LearningExample 聚合成规则。

    产出规则形态（写入 LearningModel.rules）:
        {
          "rule_id": "rule:<sha1>",
          "task_pattern": goal/task 的前 60 字符,
          "success_count": N, "fail_count": M,
          "success_rate": float,
          "failure_causes": {cause: count},     # 失败原因分布
          "samples": [episode_id...],
        }
    """

    @classmethod
    def learn_fn(
        cls,
        model: Any | None,
        examples: list[Any],
        strategy: Any,
    ) -> Any:
        """learn_fn 签名: (LearningModel|None, examples, strategy) → LearningModel"""
        from ocos.models.learning import LearningModel, LearningStrategy  # 延迟 import

        # 任务指纹: goal 描述归一化（去空白/小写/截断）
        rule_map: dict[str, dict[str, Any]] = {}

        for ex in examples:
            task = str(ex.input_data.get("task", "")) if ex.input_data else ""
            fingerprint = cls._fingerprint(task)
            if not fingerprint:
                continue
            rule = rule_map.setdefault(fingerprint, {
                "task_pattern": task[:60],
                "success_count": 0,
                "fail_count": 0,
                "failure_causes": {},
                "samples": [],
            })
            reward = ex.reward
            success = bool(reward) and reward > 0.5
            if success:
                rule["success_count"] += 1
            else:
                rule["fail_count"] += 1
                cause = ex.feedback.split(":", 1)[0] if ex.feedback else "unknown"
                rule["failure_causes"][cause] = rule["failure_causes"].get(cause, 0) + 1
            meta = ex.metadata or {}
            if meta.get("episode_id"):
                rule["samples"].append(meta["episode_id"])

        # 组装 rules
        rules: list[dict[str, Any]] = []
        for fp, rule in rule_map.items():
            total = rule["success_count"] + rule["fail_count"]
            if total == 0:
                continue
            rules.append({
                "rule_id": f"rule:{fp}",
                "task_pattern": rule["task_pattern"],
                "success_count": rule["success_count"],
                "fail_count": rule["fail_count"],
                "success_rate": round(rule["success_count"] / total, 4),
                "failure_causes": rule["failure_causes"],
                "samples": rule["samples"][:20],
            })
        rules.sort(key=lambda r: r["fail_count"], reverse=True)

        # 正确率 = 平均成功率
        accuracy = None
        if rules:
            accuracy = round(
                sum(r["success_rate"] for r in rules) / len(rules), 4
            )

        # 已有模型 → 保留原 model_id 与策略（增量）；否则新模型
        existing_params = dict(model.parameters) if model is not None else {}
        existing_rules: tuple[dict[str, Any], ...] = ()
        if model is not None:
            existing_rules = tuple(dict(r) for r in (model.rules or ()))
        merged_rules = cls._merge_rules(existing_rules, rules)

        strategy_val = strategy if isinstance(strategy, LearningStrategy) else LearningStrategy.SUPERVISED
        return LearningModel(
            model_id=(model.model_id if model is not None else ""),
            strategy=strategy_val,
            parameters={**existing_params, "rule_count": len(merged_rules)},
            rules=tuple(merged_rules),
            accuracy=accuracy,
            metadata={
                "source": "experience_learning",
                "rule_count": len(merged_rules),
                "example_count": len(examples),
            },
        )

    @classmethod
    def _fingerprint(cls, task: str) -> str:
        """任务指纹 — 归一化前 40 字符哈希。"""
        norm = re.sub(r"\s+", "", task).lower()[:40]
        if not norm:
            return ""
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def _merge_rules(
        cls, existing: tuple[dict[str, Any], ...], new: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """合并新旧规则（同 rule_id 就地累计，保留 provenance）。"""
        merged: dict[str, dict[str, Any]] = {}
        for r in existing:
            merged[r["rule_id"]] = dict(r)
        for r in new:
            rid = r["rule_id"]
            if rid in merged:
                old = merged[rid]
                old["success_count"] += r["success_count"]
                old["fail_count"] += r["fail_count"]
                total = old["success_count"] + old["fail_count"]
                old["success_rate"] = round(old["success_count"] / total, 4)
                for cause, cnt in r["failure_causes"].items():
                    old["failure_causes"][cause] = old["failure_causes"].get(cause, 0) + cnt
                old["samples"] = list(dict.fromkeys(old["samples"] + r["samples"]))[:20]
            else:
                merged[rid] = dict(r)
        return sorted(merged.values(), key=lambda x: x["fail_count"], reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# LearningArtifact 统一语义（Blueprint v1.1 §1.2 — Phase A 子集）
# ═══════════════════════════════════════════════════════════════════════════════


class ArtifactType(str, Enum):
    """学习产物类型（v1.1 四型，Phase A 实现 LESSON + RULE）。"""

    BELIEF = "belief"
    PATTERN = "pattern"
    LESSON = "lesson"          # 失败教训（Phase A 主产物）
    SKILL_CANDIDATE = "skill_candidate"


class ArtifactStatus(str, Enum):
    """Validation 状态机（v1.1 §7: CANDIDATE→VALIDATED/REJECTED→COMMITTED）。"""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"
    COMMITTED = "committed"


@dataclass(frozen=True)
class LearningArtifact:
    """统一学习产物数据契约（Blueprint v1.1 §1.2）。

    Phase A 子集：LESSON（来自失败诊断）+ RULE（成功率规则）。
    字段对齐 v1.1 契约；BELIEF/PATTERN/SKILL_CANDIDATE 为后续阶段扩展。
    """

    id: str
    artifact_type: ArtifactType
    hypothesis: str
    confidence: float
    status: ArtifactStatus = ArtifactStatus.CANDIDATE
    source_episodes: tuple[str, ...] = ()
    applicable_context: str = ""
    learned_rule: dict[str, Any] = field(default_factory=dict)
    behavioral_delta: str = ""        # ER-2 验收字段
    approval_required: bool = False
    approval_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def commit(self) -> "LearningArtifact":
        """CANDIDATE → COMMITTED（Validation 通过后）。"""
        return LearningArtifact(
            id=self.id, artifact_type=self.artifact_type,
            hypothesis=self.hypothesis, confidence=self.confidence,
            status=ArtifactStatus.COMMITTED,
            source_episodes=self.source_episodes,
            applicable_context=self.applicable_context,
            learned_rule=self.learned_rule,
            behavioral_delta=self.behavioral_delta,
            approval_required=self.approval_required,
            approval_id=self.approval_id,
            created_at=self.created_at,
        )


def build_lesson_artifact(
    diagnosis: FailureDiagnosis,
    goal: str,
    rule: dict[str, Any] | None = None,
) -> LearningArtifact:
    """从失败诊断构建 LESSON artifact（ER-1 主产物）。"""
    from ocos.models.learning import LearningExample  # noqa: F401 (签名对齐)

    confidence = 0.6  # 单次失败起步（PatternCandidate 同款）
    rid = hashlib.sha1(
        f"{diagnosis.cause.value}:{goal}".encode("utf-8")
    ).hexdigest()[:12]
    learned_rule: dict[str, Any] = {
        "cause": diagnosis.cause.value,
        "goal_pattern": goal[:60],
        "avoid": diagnosis.hypothesis,
    }
    if rule:
        sr = rule.get("success_rate")
        if sr is not None:
            learned_rule["success_rate"] = float(sr)
        learned_rule["fail_count"] = int(rule.get("fail_count", 0))
    return LearningArtifact(
        id=f"ART-{rid}",
        artifact_type=ArtifactType.LESSON,
        hypothesis=f"[{diagnosis.cause.value}] {diagnosis.hypothesis}",
        confidence=confidence,
        status=ArtifactStatus.CANDIDATE,
        source_episodes=(diagnosis.episode_id,),
        applicable_context=goal[:100],
        learned_rule=learned_rule,
        behavioral_delta=(
            f"avoid {diagnosis.cause.value} for task pattern: {goal[:50]}"
        ),
    )


def check_behavioral_delta(
    artifact: LearningArtifact, rule: dict[str, Any] | None
) -> str:
    """ER-2: Behavioral Delta 描述 — 学习产物对未来行为的预期改变。"""
    if artifact.artifact_type == ArtifactType.LESSON:
        cause = artifact.learned_rule.get("cause", "unknown")
        return (
            f"future tasks matching '{artifact.applicable_context[:40]}...' "
            f"should avoid cause={cause}"
        )
    if rule:
        return (
            f"task success_rate={rule.get('success_rate')}, "
            f"fail_count={rule.get('fail_count')}"
        )
    return "no behavioral change expected"


__all__ = [
    "FailureCause", "FailureDiagnosis", "FailureDiagnoser",
    "EpisodeExampleConverter", "RuleBasedLearner",
    "ArtifactType", "ArtifactStatus", "LearningArtifact",
    "build_lesson_artifact", "check_behavioral_delta",
]
