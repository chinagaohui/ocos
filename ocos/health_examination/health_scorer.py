"""Phase 58.0: HealthScorer — 100分健康评分系统。

评分标准:
    结构健康    20分  (模块完整, ABI一致, 无孤儿模块)
    连接健康    25分  (数据流通, 调用链完整, Trace完整)
    认知健康    20分  (Memory/Decision/World 无疾病)
    免疫健康    20分  (权限/Identity/Evolution 攻击全拦截)
    运行健康    15分  (稳定/恢复/性能)

评级:
    90-100  HEALTHY
    75-90   STABLE
    60-75   WARNING
    <60     UNHEALTHY
"""

from __future__ import annotations
from dataclasses import dataclass, field

from ocos.health_examination.health_model import (
    HealthCategory, CategoryScore, HealthCertification,
)


@dataclass
class HealthScorer:
    """100分健康评分器。"""

    # 各分类最高分
    MAX_SCORES: dict[str, float] = field(default_factory=lambda: {
        "structural": 20.0,
        "connectivity": 25.0,
        "cognitive": 20.0,
        "immune": 20.0,
        "runtime": 15.0,
    })

    def score(self, category_scores: dict[str, CategoryScore]) -> HealthCertification:
        """根据五大类得分生成健康认证。

        综合评分 = sum(category.normalized * max_score)
        """
        total = 0.0
        all_scores: dict[str, CategoryScore] = {}

        for cat_name, max_score in self.MAX_SCORES.items():
            cs = category_scores.get(cat_name)
            if cs:
                cs.max_score = max_score
                all_scores[cat_name] = cs
                total += cs.normalized * max_score
            else:
                # 缺失类别 = 0分
                all_scores[cat_name] = CategoryScore(
                    category=HealthCategory(cat_name),
                    raw_score=0.0,
                    max_score=max_score,
                    normalized=0.0,
                )

        total = round(total, 1)

        # 评级
        if total >= 90:
            grade = "HEALTHY"
        elif total >= 75:
            grade = "STABLE"
        elif total >= 60:
            grade = "WARNING"
        else:
            grade = "UNHEALTHY"

        all_pass = all(cs.passed for cs in all_scores.values())
        ready = total >= 90 and all_pass

        # 收集建议
        recommendations = []
        for cat_name, cs in all_scores.items():
            if not cs.passed:
                recommendations.append(f"{cat_name}: needs attention")
            for w in cs.warnings:
                recommendations.append(f"[{cat_name}] {w}")

        return HealthCertification(
            total_score=total,
            grade=grade,
            category_scores=all_scores,
            all_pass=all_pass,
            ready_for_production=ready,
            recommendations=recommendations,
        )


__all__ = ["HealthScorer"]
