"""S2.12: 健康体检器官注册表修正回归（白皮书 P1-9）。

- 12 器官模块路径全部真实存在
- required_exports 全部命中（修复前全 missing）
- StructuralExaminer 对真实仓库不再误报 MISSING
"""

from __future__ import annotations

import importlib

from ocos.health_examination.health_model import OCOS_ORGANS
from ocos.health_examination.structural_examiner import StructuralExaminer


class TestOrganRegistry:
    def test_all_module_paths_exist(self):
        for organ in OCOS_ORGANS:
            importlib.import_module(organ.module_path)  # 不抛即通过

    def test_all_exports_present(self):
        for organ in OCOS_ORGANS:
            m = importlib.import_module(organ.module_path)
            for export in organ.required_exports:
                assert hasattr(m, export), \
                    f"{organ.module_path} 缺少导出 {export}"

    def test_structural_examiner_no_false_missing(self):
        """结构体检对真实仓库 0 个 MISSING（逐器官断言）。"""
        examiner = StructuralExaminer()
        for organ in OCOS_ORGANS:
            oh = examiner._examine_organ(organ)
            assert oh.status.name != "MISSING", \
                f"{organ.name} ({organ.module_path}) 误报 MISSING"
            assert oh.status.name == "PRESENT", \
                f"{organ.name}: {oh.status.name} {oh.detail}"
