"""Phase A0: CauseToProcedure 端到端链路验证。

验证链路:
    FailureDiagnosis(cause=TIMEOUT, goal含关键词)
      → build_lesson_artifact_c() 产出 C 类 procedure
      → cause_to_procedure() 关键词匹配正确
      → recall.format_for_prompt() C 类优先注入

通过门槛（A0 手动触发类，非 CI）:
    - 所有 cause→procedure 映射正确
    - 注入链优先 C 类而非 B 类
    - 自动生成 C 类与 gold standard C 类格式一致

不做: 真实 LLM Behavioral Delta 实验（A5 再做）。
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def timeout_diagnosis_batch():
    """timeout + 批量场景 diagnosis."""
    from ocos.learning.experience_learning import (
        FailureDiagnosis, FailureCause,
    )
    return FailureDiagnosis(
        episode_id="EP-A0-batch-001",
        cause=FailureCause.TIMEOUT,
        hypothesis="批量图片转码执行超时",
        evidence="timeout after 30s while batch processing 100 images",
        signals_hit=("timeout",),
    )


@pytest.fixture
def timeout_diagnosis_files():
    """timeout + 多文件场景 diagnosis."""
    from ocos.learning.experience_learning import (
        FailureDiagnosis, FailureCause,
    )
    return FailureDiagnosis(
        episode_id="EP-A0-files-001",
        cause=FailureCause.TIMEOUT,
        hypothesis="展示 docs 目录所有文件超时",
        evidence="cat 10 files caused timeout after 30s",
        signals_hit=("timeout",),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: cause_to_procedure 关键词匹配
# ═══════════════════════════════════════════════════════════════════════════════


class TestCauseToProcedureMapping:
    """A0 核心: (cause, goal_pattern) → C 类 procedure 映射正确性。"""

    def test_timeout_batch_keywords(self):
        """批量关键词 → 批量操作程序模板。"""
        from ocos.learning.experience_learning import (
            cause_to_procedure, FailureCause,
        )
        templates = [
            "批量图片转码超时",
            "batch processing images",
            "一次性处理全部数据",
            "批量数据迁移",
        ]
        for goal in templates:
            p = cause_to_procedure(FailureCause.TIMEOUT, goal)
            assert "批量操作程序" in p, f"goal='{goal}' 应匹配批量模板, got: {p}"
            # 五要素完整性检查
            assert "先" in p and "每批" in p and "禁止" in p and "成功=" in p

    def test_timeout_file_keywords(self):
        """文件关键词 → 多文件展示程序模板（ER-2 原版）。"""
        from ocos.learning.experience_learning import (
            cause_to_procedure, FailureCause,
        )
        templates = [
            "展示 docs 目录下所有文件",
            "list all files and read them",
            "浏览 folder 内容",
        ]
        for goal in templates:
            p = cause_to_procedure(FailureCause.TIMEOUT, goal)
            assert "多文件展示程序" in p, f"goal='{goal}' 应匹配文件模板, got: {p}"

    def test_timeout_fallback_generic(self):
        """无关键词 → 通用退化模板。"""
        from ocos.learning.experience_learning import (
            cause_to_procedure, FailureCause,
        )
        p = cause_to_procedure(FailureCause.TIMEOUT, "某个完全不相关的任务超时了")
        assert "超时规避程序" in p
        # 五要素仍完整
        assert "先" in p and "每批" in p and "禁止" in p and "成功=" in p

    def test_non_timeout_cause_returns_empty(self):
        """P1+ 扩展后：只有 AMBIGUOUS / TOOL_UNAVAILABLE / LLM_CONVERSION / UNKNOWN
        仍返回空；PERMISSION_DENIED 和 EXECUTION_ERROR 现在也有 C 类模板了。"""
        from ocos.learning.experience_learning import (
            cause_to_procedure, FailureCause,
        )
        # 仍无模板的 cause → 空
        for cause in (
            FailureCause.TOOL_UNAVAILABLE,
            FailureCause.AMBIGUOUS_TASK,
            FailureCause.LLM_CONVERSION_FAILED,
            FailureCause.UNKNOWN,
        ):
            p = cause_to_procedure(cause, "批量操作超时")
            assert p == "", f"cause={cause.value} 应返回空, got: {p}"
        # PHASE-LIFE 新增的两个 cause → 都有 C 类模板
        p = cause_to_procedure(FailureCause.EXECUTION_ERROR, "模块探查失败")
        assert "【" in p and "程序】" in p, f"execution_error 应返回 C 类, got: {p}"
        p = cause_to_procedure(FailureCause.PERMISSION_DENIED, "沙盒外操作")
        assert "【" in p and "程序】" in p, f"permission_denied 应返回 C 类, got: {p}"

    def test_cause_to_procedure_accepts_string_cause(self):
        """cause 参数接受 str（FailureCause.value）。"""
        from ocos.learning.experience_learning import cause_to_procedure
        p = cause_to_procedure("timeout", "批量图片转码")
        assert "批量操作程序" in p


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: build_lesson_artifact_c 完整链路
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildLessonArtifactC:
    """build_lesson_artifact_c → learned_rule.procedure 字段正确。"""

    def test_c_artifact_has_procedure(self, timeout_diagnosis_batch):
        """build_lesson_artifact_c 在 learned_rule 中追加 procedure。"""
        from ocos.learning.experience_learning import build_lesson_artifact_c
        artifact = build_lesson_artifact_c(
            timeout_diagnosis_batch, "批量图片转码任务",
            {"fail_count": 3, "success_rate": 0.0},
        )
        # 旧字段保留
        lr = artifact.learned_rule
        assert lr["cause"] == "timeout"
        assert lr["goal_pattern"] == "批量图片转码任务"[:60]
        assert lr["fail_count"] == 3
        # 新字段 procedure 存在
        assert "procedure" in lr
        assert "批量操作程序" in lr["procedure"]

    def test_original_build_lesson_artifact_unchanged(self, timeout_diagnosis_batch):
        """原版 build_lesson_artifact 不被修改（向后兼容）。"""
        from ocos.learning.experience_learning import build_lesson_artifact
        artifact = build_lesson_artifact(
            timeout_diagnosis_batch, "批量图片转码任务",
            {"fail_count": 3},
        )
        assert "procedure" not in artifact.learned_rule

    def test_c_artifact_forwards_to_original(self, timeout_diagnosis_files):
        """build_lesson_artifact_c 先调原版，再追加 procedure。"""
        from ocos.learning.experience_learning import build_lesson_artifact_c
        artifact = build_lesson_artifact_c(
            timeout_diagnosis_files, "展示 docs 目录所有文件",
        )
        assert artifact.learned_rule["cause"] == "timeout"
        assert "procedure" in artifact.learned_rule
        assert "多文件展示程序" in artifact.learned_rule["procedure"]

    def test_behavioral_delta_mentions_procedure(self, timeout_diagnosis_batch):
        """behavioral_delta 包含 procedure 信息。"""
        from ocos.learning.experience_learning import build_lesson_artifact_c
        artifact = build_lesson_artifact_c(
            timeout_diagnosis_batch, "批量图片转码",
        )
        assert "procedure" in artifact.behavioral_delta
        assert "批量操作程序" in artifact.behavioral_delta


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: recall.format_for_prompt C 类优先注入
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecallFormatForPromptCClass:
    """recall.format_for_prompt C 类 procedure 优先注入.

    注: recall 不自动从 failure_causes 推导 procedure（依赖方向约束:
    memory 层不依赖 learning 层）。procedure 字段必须由调用方预填充。
    """

    def test_timeout_rule_injects_procedure(self):
        """rule 预填充 procedure → C 类注入（recall 不自动推导）。"""
        from ocos.memory.recall import MemoryRecall
        from ocos.learning.experience_learning import cause_to_procedure
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        # 调用方（converse 侧）负责预填充 procedure
        rules = [{
            "task_pattern": "批量图片转码",
            "success_count": 0,
            "fail_count": 3,
            "success_rate": 0.0,
            "failure_causes": {"timeout": 3},
        }]
        for rule in rules:
            fc = rule.get("failure_causes") or {}
            causes_str = " ".join(str(c) for c in fc.keys()) if isinstance(fc, dict) else str(fc)
            proc = cause_to_procedure(causes_str, rule.get("task_pattern", ""))
            if proc:
                rule["procedure"] = proc
        out = recall.format_for_prompt(context="转码图片", learning_rules=rules)
        assert "批量操作程序" in out
        assert "💡" in out  # C 类图标

    def test_procedure_field_override_auto(self):
        """rule 自身带 procedure → 用自身值（覆盖自动推导）。"""
        from ocos.memory.recall import MemoryRecall
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        my_proc = "【自定义程序】先检查X；每批Y≤5；等Z。禁A。成功=B"
        rules = [{
            "task_pattern": "批量图片转码",
            "success_count": 0,
            "fail_count": 3,
            "success_rate": 0.0,
            "failure_causes": {"timeout": 3},
            "procedure": my_proc,  # 显式覆盖
        }]
        out = recall.format_for_prompt(context="转码", learning_rules=rules)
        assert my_proc in out  # 用了显式值
        assert "批量操作程序" not in out  # 没用自动推导

    def test_non_timeout_rule_falls_back_to_b_class(self):
        """非 timeout 失败原因 → 退化到 B 类 warning 格式。"""
        from ocos.memory.recall import MemoryRecall
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        rules = [{
            "task_pattern": "API 调用",
            "success_count": 1,
            "fail_count": 3,
            "success_rate": 0.25,
            "failure_causes": {"permission_denied": 3},  # 非 timeout
        }]
        out = recall.format_for_prompt(context="调用API", learning_rules=rules)
        # 不应有 C 类 procedure
        assert "💡" not in out
        # 应有 B 类 warning
        assert "⚠️" in out

    def test_procedure_priority_over_conflict(self):
        """C 类 procedure 优先于 B 类 conflict 显示。"""
        from ocos.memory.recall import MemoryRecall
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        rules = [
            {
                "task_pattern": "批量图片转码",
                "success_count": 0,
                "fail_count": 3,
                "success_rate": 0.0,
                "failure_causes": {"timeout": 3},
            },
            {
                "task_pattern": "API 调用",
                "success_count": 1,
                "fail_count": 3,
                "success_rate": 0.25,
                "failure_causes": {"permission_denied": 3},
            },
        ]
        out = recall.format_for_prompt(context="转码 API", learning_rules=rules)
        # C 类排在前面（💡 before ⚠️）
        proc_pos = out.find("💡")
        conf_pos = out.find("⚠️")
        assert proc_pos < conf_pos, "C 类应在 B 类之前"

    def test_rule_without_failure_causes_degrades(self):
        """rule 无 failure_causes（旧数据兼容）→ 退化 B 类。"""
        from ocos.memory.recall import MemoryRecall
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        rules = [{
            "task_pattern": "某个任务",
            "success_count": 0,
            "fail_count": 2,
            "success_rate": 0.0,
            # 无 failure_causes
        }]
        out = recall.format_for_prompt(context="任务", learning_rules=rules)
        assert "⚠️" in out  # B 类退化
        assert "💡" not in out  # 无 C 类

    def test_sample_count_threshold_preserved(self):
        """样本数 < 2 仍被排除（A0 不改此逻辑）。"""
        from ocos.memory.recall import MemoryRecall
        recall = MemoryRecall(memory_hub=SimpleNamespace())
        rules = [{
            "task_pattern": "批量图片转码",
            "success_count": 0,
            "fail_count": 1,
            "success_rate": 0.0,
            "failure_causes": {"timeout": 1},
        }]
        out = recall.format_for_prompt(context="转码", learning_rules=rules)
        assert "学习规则" not in out  # 单样本不注入


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: 治理隔离 — A0 不改 Runtime 权限
# ═══════════════════════════════════════════════════════════════════════════════


class TestA0GovernanceIsolation:
    """Phase A0 全局约束检查（冻结令）。"""

    def test_no_execute_method(self):
        """新增模块无 execute/act 方法。"""
        from ocos.learning.experience_learning import (
            build_lesson_artifact_c, cause_to_procedure,
        )
        assert not hasattr(cause_to_procedure, "execute")
        assert not hasattr(cause_to_procedure, "act")

    def test_learning_artifact_unchanged_structure(self):
        """LearningArtifact 数据结构未新增 Runtime 字段。"""
        from ocos.learning.experience_learning import LearningArtifact
        la = LearningArtifact(
            id="ART-x", artifact_type="lesson", hypothesis="h", confidence=0.6,
        )
        # 不应有 Runtime 相关字段
        for field_name in ("mutation_authority", "runtime_permission",
                           "can_execute", "action_queue"):
            assert not hasattr(la, field_name), f"不应有字段: {field_name}"

    def test_parallel_not_replace(self):
        """build_lesson_artifact_c 并行存在，不替换原版。"""
        from ocos.learning.experience_learning import (
            build_lesson_artifact, build_lesson_artifact_c,
        )
        assert callable(build_lesson_artifact)
        assert callable(build_lesson_artifact_c)
        assert build_lesson_artifact is not build_lesson_artifact_c


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5: 注入链完整性 — memory hub → converse 消费点 mock
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectionChainEndToEnd:
    """模拟 converse._recall_context 的完整注入链路。"""

    def test_converse_injection_smoke(self):
        """rule（含 timeout）→ load_learning_rules → converse 侧 cause_to_procedure 预填充
        → format_for_prompt → C 类注入。"""
        import tempfile, os, sqlite3, json
        from ocos.learning.persistence import load_learning_rules
        from ocos.learning.experience_learning import cause_to_procedure
        from ocos.memory.recall import MemoryRecall

        db_path = tempfile.mktemp(suffix=".db")
        try:
            # 模拟 daemon dream 后落库的 rules
            rules_data = [{
                "rule_id": "rule:batch",
                "task_pattern": "批量图片转码",
                "success_count": 0,
                "fail_count": 3,
                "success_rate": 0.0,
                "failure_causes": {"timeout": 3},
                "samples": ["EP1", "EP2", "EP3"],
            }]

            # 直接写 learning_models 表（跳过 persist_latest_rules 依赖）
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE learning_models (
                    id INTEGER PRIMARY KEY,
                    model_id TEXT, strategy TEXT,
                    rules_json TEXT, skills_json TEXT,
                    created_at TEXT
                )
            """)
            conn.execute(
                "INSERT INTO learning_models (model_id, strategy, rules_json, skills_json, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                ("test-model", "supervised",
                 json.dumps(rules_data, ensure_ascii=False), "[]")
            )
            conn.commit()
            conn.close()

            # load_learning_rules 读取
            loaded = load_learning_rules(db_path, limit=5)
            assert len(loaded) == 1
            assert loaded[0]["task_pattern"] == "批量图片转码"

            # converse 侧预填充 procedure（A0+ 新增逻辑）
            for rule in loaded:
                if rule.get("procedure"):
                    continue
                fc = rule.get("failure_causes") or {}
                causes_str = " ".join(str(c) for c in fc.keys()) if isinstance(fc, dict) else str(fc)
                proc = cause_to_procedure(causes_str, rule.get("task_pattern", ""))
                if proc:
                    rule["procedure"] = proc

            # format_for_prompt → C 类注入
            recall = MemoryRecall(memory_hub=SimpleNamespace())
            out = recall.format_for_prompt(
                context="帮我批量转码这些图片",
                learning_rules=loaded,
            )
            assert "批量操作程序" in out
            assert "💡" in out
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
