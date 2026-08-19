"""Phase 32: Memory Consolidation Loop — 执行结果 → 记忆 + 信念 + 注意力."""
import pytest
from unittest.mock import MagicMock, patch


class TestPhase32MemoryConsolidation:
    """测试 AgentRuntime 的记忆回流管道。"""

    def _make_runtime(self):
        from ocos.agent.agent_runtime import AgentRuntime
        agent = MagicMock()
        rt = AgentRuntime(agent, max_cycles=20)
        rt._recent_results = []
        rt._result_cursor = 0
        return rt

    def _fake_result(self, task_id="T1", agent="echo", desc="test task",
                     success=True, output="echo output"):
        return {
            "task_id": task_id, "agent": agent,
            "description": desc, "success": success,
            "output": output,
        }

    # ── Step 9: Result Ingest ──

    def test_ingest_writes_to_working_memory(self):
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result()]
        r = rt._tick_step_result_ingest()
        assert r["ingested"] is True
        assert rt.memory.working_count >= 1
        assert r["memory"]["working_now"] >= 1

    def test_ingest_advances_cursor(self):
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result("A"), self._fake_result("B")]
        r1 = rt._tick_step_result_ingest()
        assert r1["ingested"] is True
        r2 = rt._tick_step_result_ingest()
        assert r2["ingested"] is True
        # cursor exhausted
        r3 = rt._tick_step_result_ingest()
        assert r3["ingested"] is False

    def test_ingest_preserves_results_for_belief_extraction(self):
        """cursor 不 pop，step 10 仍能读取完整列表。"""
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result(f"T{i}") for i in range(3)]
        for _ in range(3):
            rt._tick_step_result_ingest()
        assert len(rt._recent_results) == 3  # preserved
        assert rt._result_cursor == 3

    def test_ingest_no_results_idle(self):
        rt = self._make_runtime()
        r = rt._tick_step_result_ingest()
        assert r["ingested"] is False
        assert r["memory"] is None

    # ── Step 10: Belief Extraction ──

    def test_extract_belief_all_success_chain(self):
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result(f"T{i}") for i in range(4)]
        n = rt._extract_beliefs_from_results()
        assert n >= 1  # 100% success pattern
        beliefs = rt.beliefs.get_all()
        assert any("100%" in b.statement for b in beliefs)

    def test_extract_belief_too_few_results(self):
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result()]
        n = rt._extract_beliefs_from_results()
        assert n == 0

    def test_extract_belief_agent_reliability(self):
        rt = self._make_runtime()
        rt._recent_results = [
            self._fake_result(agent="researcher") for _ in range(3)
        ]
        rt._recent_results.append(self._fake_result(agent="writer", success=False))
        n = rt._extract_beliefs_from_results()
        assert n >= 1  # at least "100% success" or "researcher reliable"
        beliefs = rt.beliefs.get_all()
        assert len(beliefs) >= 1

    # ── Attention ──

    def test_ingest_pushes_attention_focus(self):
        rt = self._make_runtime()
        rt._recent_results = [self._fake_result(task_id="T42")]
        mock_attn = MagicMock()
        rt._attention = mock_attn  # bypass lazy property init
        rt._tick_step_result_ingest()
        mock_attn.push_focus.assert_called_once()

    def test_ingest_attention_does_not_block_on_error(self):
        rt = self._make_runtime()
        rt._attention = None  # not a stub, will fail on push_focus
        rt._recent_results = [self._fake_result()]
        r = rt._tick_step_result_ingest()
        assert r["ingested"] is True  # still ingested despite attention failure
