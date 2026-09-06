"""记忆直接参与决策 — 统一记忆决策上下文测试。

验证（用户方向：ocos 是调用软件智能体干活的"生命体"，记忆应作为决策
一等依据，而非仅为抽象 Skill）:
  - learning_source 命中 → 输出结构化【记忆决策上下文】含量化摘要 + 归因条目
  - 无记忆/未注入 → 返回空（基线路径不变）
  - 量化: 命中数/类型统计/高置信计数 存在且可审计
  - 记忆覆盖 skill/belief/knowledge 等类型（不强制 Skill 参与）
"""

from __future__ import annotations


def _artifact(atype, text, conf=0.8, score=1, aid=None):
    return {"artifact_id": aid or f"{atype}:{text}",
            "type": atype, "text": text, "confidence": conf, "score": score}


# 典型记忆集: 一次"调 openclaw 干活"成功后沉淀的各类记忆
_MEMORY_HIT = [
    _artifact("skill", "技能[宿主机分析]: 用 openclaw 分析宿主机状态", conf=0.9,
              score=3, aid="skill:SKL-1"),
    _artifact("belief", "当需要分析宿主机时, 调用 openclaw 有效", conf=0.85,
              score=2, aid="belief:b1"),
    _artifact("knowledge", "openclaw agent -m 可执行单轮任务", conf=0.8,
              score=1, aid="kn:openclaw"),
]


class TestMemoryDecisionContext:
    def _ctx(self, artifacts=_MEMORY_HIT):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(agent_id="test-mem")
        bridge.attach_learning_source(lambda _d: artifacts)
        return bridge

    def test_outputs_unified_block(self):
        """命中 → 输出【记忆决策上下文】结构化块。"""
        block = self._ctx()._memory_decision_context("分析宿主机状态")
        assert "【记忆决策上下文】" in block
        assert "openclaw" in block

    def test_includes_quantified_summary(self):
        """含量化摘要: 命中记忆条数 / 类型计数 / 高置信计数。"""
        block = self._ctx()._memory_decision_context("分析宿主机状态")
        assert "3 条相关记忆" in block or "相关记忆" in block
        assert "skill" in block.lower() or "技能" in block

    def test_includes_attribution_artifact_id(self):
        """每条目含 artifact_id（可审计/ER-2 归因）。"""
        block = self._ctx()._memory_decision_context("分析宿主机状态")
        assert "skill:SKL-1" in block
        assert "belief:b1" in block

    def test_supports_non_skill_memory(self):
        """不强制 Skill: belief/knowledge 单独命中也能产出决策上下文。"""
        bridge = self._ctx([_artifact("knowledge", "df -h 查看磁盘", conf=0.9)])
        block = bridge._memory_decision_context("查看磁盘使用")
        assert "【记忆决策上下文】" in block
        assert "df -h" in block

    def test_empty_without_learning_source(self):
        """未注入学习源 → 空（基线不变，不伪造记忆）。"""
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(agent_id="test-mem")  # 无 learning_source
        assert bridge._memory_decision_context("任意任务") == ""

    def test_empty_when_no_match(self):
        """学习源返回空 → 空。"""
        assert self._ctx([])._memory_decision_context("任意任务") == ""

    def test_prioritizes_skill_then_belief_then_knowledge(self):
        """排序依 score（技能 > 信念 > 知识）— openclaw 技能排首。"""
        block = self._ctx()._memory_decision_context("分析宿主机状态")
        i_skill = block.find("技能[宿主机分析]")
        i_belief = block.find("调用 openclaw 有效")
        i_know = block.find("可执行单轮任务")
        assert 0 <= i_skill < i_belief < i_know, block[:400]