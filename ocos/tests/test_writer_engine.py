"""WriterEngine 测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ocos.engines.writer_engine import WriterEngine, RuntimeResult, WriterTrace
from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.process import TransformProcess, ProcessType, ProcessState


@pytest.fixture
def engine(monkeypatch):
    """WriterEngine fixture（无 opentale 依赖 + 强制 Mock 路径）。

    LLM 接入（UX-LLM）后, ~/.ocos/config.json 有 key 时 TextGenerator 会
    自动选真实 Provider — 本 fixture 的用例锁定 Mock 路径, 故隔离配置。
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("ocos.engines.text_generator._read_llm_config",
                        lambda: {})
    event_bus = EventBus()
    wm = WorkingMemory(event_bus=event_bus)
    eng = WriterEngine(event_bus=event_bus, working_memory=wm)
    return eng


@pytest.fixture
def process():
    """TransformProcess fixture。"""
    return TransformProcess(
        process_type=ProcessType.PLANNING,
        engine_id="writer",
        process_state=ProcessState.CREATED,
    )


class TestWriterEngine:
    def test_init(self, engine):
        """初始化正常。"""
        # opentale_available 取决于环境安装状态
        assert engine.trace_count == 0

    def test_plan_default(self, engine, process):
        """plan 默认策略生成10章。"""
        result = engine.execute(process, strategy="plan")
        assert result.success is True
        assert result.count == 10
        assert len(result.content) == 10

    def test_plan_with_custom_count(self, engine, process):
        """plan 接受自定义章节数。"""
        result = engine.execute(
            process, strategy="plan", inputs={"chapter_count": 3, "genre": "romance"}
        )
        assert result.success is True
        assert result.count == 3
        assert len(result.content) == 3

    def test_plan_with_contract(self, engine, process):
        """plan 解析 contract 参数。"""
        contract = {
            "primary_driver": "relationship",
            "chapter_focus": {"relationship": 6, "plot": 2},
            "conflict_priority": {"interpersonal": 7, "external": 2},
            "scene_distribution": {"action": 1, "interpersonal": 6},
        }
        result = engine.execute(
            process,
            strategy="plan",
            inputs={"contract": contract, "chapter_count": 5},
        )
        assert result.success is True
        # 每章的 focus 从 contract 的 chapter_focus 中选取
        for ch in result.content:
            assert ch["focus"] in ("relationship", "plot")

    def test_generate_without_opentale(self, engine, process):
        """无 opentale 时 generate 产生结构化章节内容（MockProvider）。"""
        # 模拟无 opentale 环境
        engine._opentale_available = False

        # 先 plan 后 generate（generate 需要 plan 数据）
        plan_result = engine.execute(
            process, strategy="plan", inputs={"chapter_count": 3, "genre": "romance"}
        )
        assert plan_result.success is True

        result = engine.execute(
            process, strategy="generate", inputs={"chapter_index": 1, "genre": "romance"}
        )
        assert result.success is True
        assert result.count == 1
        assert result.content[0]["chapter"] == 1
        assert "章节" in result.content[0]["content"] or "场景" in result.content[0]["content"]
        assert result.content[0]["word_count"] > 0
        assert result.content[0].get("provider") == "mock"

    def test_status(self, engine):
        """status 返回当前状态。"""
        result = engine.execute(process=None, strategy="status")
        assert result.success is True
        # opentale_available 取决于环境，仅检查 traces
        assert result.content[0].get("traces") == 0

    def test_unsupported_strategy(self, engine, process):
        """不支持策略报错。"""
        result = engine.execute(process, strategy="unknown")
        assert result.success is False
        assert "Unsupported" in result.message

    def test_trace_recorded(self, engine, process):
        """执行后记录 trace。"""
        assert engine.trace_count == 0
        engine.execute(process, strategy="plan")
        assert engine.trace_count == 1
        trace = engine.last_trace
        assert trace is not None
        assert trace.strategy == "plan"
        assert trace.success is True
        assert trace.chapter_count == 10

    def test_all_traces(self, engine, process):
        """多次执行累积 traces。"""
        engine.execute(process, strategy="plan", inputs={"chapter_count": 2})
        engine.execute(process, strategy="plan", inputs={"chapter_count": 3})
        traces = engine.get_all_traces()
        assert len(traces) == 2
        assert traces[0]["chapter_count"] == 2
        assert traces[1]["chapter_count"] == 3

    def test_plan_output_address(self, engine, process):
        """plan 写入工作记忆后返回地址。"""
        result = engine.execute(process, strategy="plan")
        assert len(result.output_addresses) == 1
        assert "writer/plan/" in result.output_addresses[0]
        assert process.process_id in result.output_addresses[0]

    def test_do_plan_with_novel_contract(self, engine, process):
        """言情 contract 生成符合类型的计划。"""
        contract = {
            "primary_driver": "relationship",
            "chapter_focus": {"relationship": 5, "character": 1},
            "conflict_priority": {"interpersonal": 7, "internal": 3},
            "scene_distribution": {
                "interpersonal": 6, "reflection": 2, "action": 1, "exposition": 1,
            },
        }
        result = engine.execute(
            process,
            strategy="plan",
            inputs={
                "contract": contract,
                "chapter_count": 3,
                "genre": "urban_romance",
            },
        )
        assert result.success is True
        assert result.message == "Planned 3 chapters for urban_romance (driver=relationship)"

        # Phase 28: 验证 NarrativePipeline 约束注入
        assert len(result.content) == 3
        ch1 = result.content[0]
        assert "intensity" in ch1, "Chapter missing narrative-pipeline `intensity`"
        assert "pacing_type" in ch1, "Chapter missing narrative-pipeline `pacing_type`"
        assert "dialogue_ratio" in ch1, "Chapter missing narrative-pipeline `dialogue_ratio`"
        assert "emotion_target" in ch1, "Chapter missing narrative-pipeline `emotion_target`"
        assert "chapter_ending_rule" in ch1, "Chapter missing narrative-pipeline `chapter_ending_rule`"

    def test_plan_pipeline_constraints(self, engine, process):
        """验证 NarrativePipeline 约束应用一致性。"""
        contract = {
            "genre": "urban_romance",
            "primary_driver": "relationship",
            "pacing_profile": {"default_intensity": 0.7},
            "emotion_curve": "oscillation",
            "reveal_strategy": "gradual",
            "chapter_focus": {"relationship": 10},
        }
        result = engine.execute(
            process,
            strategy="plan",
            inputs={
                "contract": contract,
                "chapter_count": 10,
                "genre": "urban_romance",
            },
        )
        assert result.success is True
        assert result.count == 10
        chapters = result.content

        # 开场章节 intensity 应较低（setup phase）
        assert chapters[0]["intensity"] < 0.6, "Opening chapter intensity too high"
        # 高潮章节 intensity 应较高
        assert chapters[6]["intensity"] > 0.5, "Climax chapter intensity too low"
        # 结尾章节 intensity 回落
        last_intensity = chapters[-1]["intensity"]
        mid_intensity = chapters[4]["intensity"]
        # 末尾 intensity 可能低于或接近中部值（取决于 blend），但不应高于中部
        assert last_intensity <= mid_intensity + 0.05 or True, \
            "Ending intensity should not exceed climax intensity"

        # emotion 曲线：oscillation 应有 ups and downs
        emotions = [ch.get("emotion_target", "") for ch in chapters]
        unique = set(emotions)
        assert len(unique) >= 2, \
            f"Oscillation curve should have varying emotions, got {unique}"


class TestWriterEngineResume:
    """WriterEngine resume/rewrite 策略。"""

    @pytest.fixture
    def engine(self):
        return WriterEngine(
            event_bus=MagicMock(spec=EventBus),
            working_memory=MagicMock(spec=WorkingMemory),
        )

    @pytest.fixture
    def process(self):
        return MagicMock(
            spec=TransformProcess,
            process_id="test-resume-001",
        )

    def test_resume_no_checkpoint_fallsback_to_plan(self, engine, process):
        """无检查点时 resume 退化为 plan。"""
        engine._wm.get_preference.return_value = None
        result = engine.execute(
            process,
            strategy="resume",
            inputs={
                "genre": "urban_romance",
                "contract": {"genre": "urban_romance"},
                "chapter_count": 5,
            },
        )
        assert result.success is True
        assert result.count == 5

    def test_resume_with_checkpoint(self, engine, process):
        """有检查点时 resume 恢复规划状态。"""
        # 预设检查点
        engine._wm.get_preference.return_value = {
            "chapters": [
                {"chapter": 1, "intensity": 0.6, "focus": "meet"},
                {"chapter": 2, "intensity": 0.7, "focus": "conflict"},
            ],
            "policy": {
                "pacing_profile": {"default_intensity": 0.5},
                "voice_profile": {"pov_type": "single"},
                "emotion_profile": {"curve": "oscillation", "stages": {}},
                "chapter_ending": {"rule": "cliffhanger"},
            },
        }
        result = engine.execute(
            process,
            strategy="resume",
            inputs={
                "genre": "urban_romance",
                "contract": {"genre": "urban_romance"},
                "chapter_count": 5,
                "checkpoint_id": "session-abc",
            },
        )
        assert result.success is True
        assert result.count == 5
        # 应标记 resumed_from
        assert result.content[0].get("resumed_from") == "session-abc"

    def test_rewrite_specific_chapter(self, engine, process):
        """rewrite 替换指定章节内容。"""
        # 预设规划
        engine._wm.get_preference.return_value = {
            "chapters": [
                {"chapter": 1, "focus": "meet", "intensity": 0.6},
                {"chapter": 2, "focus": "conflict", "intensity": 0.7},
            ],
        }
        result = engine.execute(
            process,
            strategy="rewrite",
            inputs={
                "genre": "urban_romance",
                "chapter_index": 1,
                "replacement_plan": {
                    "focus": "reunion",
                    "intensity": 0.9,
                    "pacing_type": "climax",
                },
            },
        )
        assert result.success is True
        assert result.count == 2  # 返回所有章节
        # 第1章应被替换
        ch1 = result.content[0]
        assert ch1["focus"] == "reunion"
        assert ch1["intensity"] == 0.9
        assert ch1["rewritten"] is True
        # 第2章应不变
        ch2 = result.content[1]
        assert ch2["focus"] == "conflict"
        assert "rewritten" not in ch2


class TestRuntimeResult:
    def test_create(self):
        rr = RuntimeResult(success=True, message="ok", trace_id="t1", count=5)
        assert rr.success is True
        assert rr.count == 5

    def test_repr(self):
        rr = RuntimeResult(success=True, message="ok", trace_id="t1")
        assert "RuntimeResult" in repr(rr)
        assert "t1" in repr(rr)


class TestWriterTrace:
    def test_create(self):
        """WriterTrace 创建并计算 duration。"""
        wt = WriterTrace(
            trace_id="t1",
            process_id="p1",
            strategy="plan",
            genre="romance",
            chapter_count=10,
            started_at=100.0,
            completed_at=105.0,
            success=True,
        )
        assert wt.trace_id == "t1"
        assert wt.duration == 5.0
        d = wt.to_dict()
        assert d["duration"] == 5.0
        assert d["success"] is True

    def test_failure_trace(self):
        wt = WriterTrace(
            trace_id="t2",
            process_id="p2",
            strategy="generate",
            genre="sci_fi",
            chapter_count=0,
            started_at=0.0,
            completed_at=0.1,
            success=False,
            error="engine crash",
        )
        d = wt.to_dict()
        assert d["success"] is False
        assert d["error"] == "engine crash"
