"""Phase 58.0: StructuralExaminer — P39-P50 结构体检。

检查 OCOS 所有设计器官是否真实存在，无空壳。
"""

from __future__ import annotations
import importlib
from dataclasses import dataclass, field

from ocos.health_examination.health_model import (
    OrganDef, OrganHealth, OrganStatus, OCOS_ORGANS, HealthCategory, CategoryScore,
)


@dataclass
class StructuralExaminer:
    """P39-P50 结构性体检器。"""

    organs: list[OrganDef] = field(default_factory=lambda: list(OCOS_ORGANS))
    organ_health: dict[str, OrganHealth] = field(default_factory=dict)

    def examine(self) -> CategoryScore:
        """执行完整结构体检。"""
        self.organ_health.clear()
        for organ in self.organs:
            oh = self._examine_organ(organ)
            self.organ_health[organ.name] = oh

        present = sum(1 for oh in self.organ_health.values() if oh.healthy)
        total = len(self.organs)
        score = (present / total) * 20.0 if total > 0 else 0.0

        warnings = []
        for name, oh in self.organ_health.items():
            if not oh.healthy:
                warnings.append(f"{name}({oh.organ.phase}): {oh.status.value} — {oh.detail}")
            if oh.exports_missing:
                warnings.append(f"{name}: missing exports {oh.exports_missing}")

        return CategoryScore(
            category=HealthCategory.STRUCTURAL,
            raw_score=score,
            max_score=20.0,
            normalized=present / total if total > 0 else 0.0,
            details={
                "organs_present": present,
                "organs_total": total,
                "findings": {name: oh.status.value for name, oh in self.organ_health.items()},
            },
            warnings=warnings,
        )

    def _examine_organ(self, organ: OrganDef) -> OrganHealth:
        oh = OrganHealth(organ=organ)
        try:
            mod = importlib.import_module(organ.module_path)
        except ModuleNotFoundError:
            oh.status = OrganStatus.MISSING
            oh.detail = f"module {organ.module_path} not found"
            return oh
        except ImportError as e:
            oh.status = OrganStatus.INCOMPLETE
            oh.detail = f"import error: {e}"
            return oh

        # 检查导出
        mod_dir = dir(mod)
        for exp in organ.required_exports:
            if exp in mod_dir:
                oh.exports_found.append(exp)
            else:
                oh.exports_missing.append(exp)

        if oh.exports_missing:
            if len(oh.exports_missing) == len(organ.required_exports):
                oh.status = OrganStatus.MISSING
                oh.detail = "all required exports missing"
            else:
                oh.status = OrganStatus.INCOMPLETE
                oh.detail = f"partial: missing {oh.exports_missing}"
        else:
            oh.status = OrganStatus.PRESENT
            if organ.required_exports:
                oh.detail = f"all {len(organ.required_exports)} exports found"
            else:
                oh.detail = "module present"

        return oh

    def is_organ_healthy(self, name: str) -> bool:
        oh = self.organ_health.get(name)
        return oh.healthy if oh else False

    def unhealthy_organs(self) -> list[str]:
        return [name for name, oh in self.organ_health.items() if not oh.healthy]


__all__ = ["StructuralExaminer"]
