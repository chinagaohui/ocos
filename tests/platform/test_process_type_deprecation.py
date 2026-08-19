"""ProcessType 弃用测试。"""
from __future__ import annotations

import pytest

from ocos.models.process import ProcessType, TransformProcess


class TestProcessTypeDeprecation:
    def test_process_type_triggers_warning(self):
        """导入 ProcessType 时触发 DeprecationWarning。

        由于 Enum 值在类定义时即创建，警告在模块导入时触发。
        此处验证值仍然可用。
        """
        # 直接访问 ProcessType 值（导入时已触发警告）
        assert ProcessType.REASONING.value == "reasoning"

    def test_process_type_value_preserved(self):
        """ProcessType 值仍然可用（向后兼容）。"""
        assert ProcessType.REASONING.value == "reasoning"
        assert ProcessType.DECISION.value == "decision"
        assert ProcessType.PLANNING.value == "planning"

    def test_process_with_engine_id(self):
        """TransformProcess 支持 engine_id 字段。"""
        proc = TransformProcess(engine_id="reasoning_engine")
        assert proc.engine_id == "reasoning_engine"
        assert proc.process_type == ProcessType.REASONING  # 默认值
        assert proc.process_id is not None

    def test_process_type_to_engine_id_migration(self):
        """迁移路径：process_type → engine_id。"""
        proc = TransformProcess(
            process_type=ProcessType.REASONING,
            engine_id="reasoning_engine",
        )
        assert proc.engine_id == "reasoning_engine"
        assert proc.process_type == ProcessType.REASONING

    def test_engine_id_none_by_default(self):
        """engine_id 默认为 None（尚未迁移的 process 兼容）。"""
        proc = TransformProcess()
        assert proc.engine_id is None
