"""Phase 47: SelfModificationAgent tests."""

from __future__ import annotations

import pytest
from ocos.capability.agents.self_modification_agent import (
    SelfModificationAgent,
    ModificationPlan,
    validate_path,
    preview_change,
)


class TestSelfModificationAgent:
    """SelfModificationAgent 单元测试。"""

    @pytest.fixture
    def agent(self, tmp_path):
        return SelfModificationAgent(str(tmp_path))

    @pytest.fixture
    def sample_file(self, tmp_path):
        """创建样本文件。"""
        file = tmp_path / "test_module.py"
        file.write_text("def hello():\n    return 'hello'\n")
        return file

    def test_validate_path_safe(self, agent, tmp_path):
        """安全路径验证。"""
        valid, resolved = agent._validate_path("ocos/test.py")
        assert valid is True
        assert "ocos" in resolved

    def test_validate_path_forbidden_dir(self, agent, tmp_path):
        """禁止目录验证。"""
        valid, _ = agent._validate_path(".venv/foo.py")
        assert valid is False

    def test_validate_path_forbidden_file(self, agent, tmp_path):
        """禁止文件验证。"""
        valid, _ = agent._validate_path("config.json")
        assert valid is False

    def test_validate_path_invalid_extension(self, agent, tmp_path):
        """无效扩展名验证。"""
        valid, _ = agent._validate_path("test.exe")
        assert valid is False

    def test_preview_edit(self, agent, sample_file):
        """预览编辑操作。"""
        result = agent.execute(
            task="修改函数",
            file=str(sample_file.relative_to(agent._project_root)),
            content="def hello():\n    return 'world'\n",
            dry_run=True,
        )
        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["plan"]["operation"] == "edit"

    def test_preview_add(self, agent, tmp_path):
        """预览添加操作。"""
        result = agent.execute(
            task="添加新模块",
            file="new_module.py",
            content="def new_func():\n    pass\n",
            dry_run=True,
        )
        assert result["success"] is True
        assert result["plan"]["operation"] == "add"

    def test_missing_task(self, agent):
        """缺失任务参数。"""
        result = agent.execute()
        assert result["success"] is False
        assert "Missing 'task'" in result["error"]

    def test_missing_file(self, agent):
        """缺失文件参数。"""
        result = agent.execute(task="test")
        assert result["success"] is False
        assert "Missing 'file'" in result["error"]

    def test_missing_content(self, agent, sample_file):
        """编辑操作缺少内容。"""
        result = agent.execute(
            task="test",
            file=str(sample_file),
            dry_run=True,
        )
        assert result["success"] is False
        assert "Missing 'content'" in result["error"]

    def test_high_risk_detection(self, agent, sample_file):
        """高风险操作检测。"""
        risky_content = "import os\nos.system('rm -rf /')\n"
        result = agent.execute(
            task="高危操作",
            file=str(sample_file.relative_to(agent._project_root)),
            content=risky_content,
            dry_run=True,
        )
        assert result["success"] is True
        # 高风险需要确认
        assert result["plan"]["approval_required"] is True

    def test_risk_analysis(self, agent):
        """风险分析功能。"""
        risks = agent._analyze_risks("test.py", "import subprocess\nsubprocess.run('ls')\n")
        assert len(risks) > 0
        assert "Contains risky pattern" in risks[0]

    def test_generate_diff(self, agent, sample_file):
        """Diff 生成。"""
        original = "def old():\n    return 1\n"
        new = "def new():\n    return 2\n"
        diff = agent._generate_diff("test.py", new, original)
        assert "---" in diff
        assert "+++" in diff

    def test_delete_preview(self, agent, sample_file):
        """删除预览。"""
        result = agent.execute(
            task="删除文件",
            file=str(sample_file.relative_to(agent._project_root)),
            delete=True,
            dry_run=True,
        )
        assert result["success"] is True
        assert result["plan"]["operation"] == "delete"


class TestModificationPlan:
    """ModificationPlan 测试。"""

    def test_is_safe_no_risks(self):
        plan = ModificationPlan(risks=[], approval_required=False)
        assert plan.is_safe is True

    def test_is_unsafe_with_risks(self):
        plan = ModificationPlan(risks=["high risk"], approval_required=True)
        assert plan.is_safe is False


class TestModuleFunctions:
    """模块级函数测试。"""

    def test_validate_path(self, tmp_path):
        valid, resolved = validate_path(str(tmp_path), "test.py")
        assert valid is True

    def test_preview_change(self, tmp_path):
        agent_path = str(tmp_path)
        result = preview_change(
            agent_path,
            "test.py",
            "def foo():\n    pass\n",
            "添加函数",
        )
        assert result["success"] is True
        assert result["dry_run"] is True
