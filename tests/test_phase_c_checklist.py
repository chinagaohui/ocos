"""Phase C ER-2 Phase 4 检查清单回归保护测试。

固化结论：NOT TRIGGERED ⏸ — 5 项检查 C1-C4 全部 FAIL，C0 PASS。
本测试防止意外引入 Candidate 层（BehaviorCandidate 类 / bridge 消费路径）。

如果未来要触发 Phase 4（Candidate 层设计），**必须先修改本测试**，
并在修改前走 SELF_EVOLUTION_ROADMAP Phase C 路线图的正式重闸门流程。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _grep(glob_pattern: str, patterns: list[str]) -> list[str]:
    """对仓库做 ripgrep，返回所有匹配行。"""
    results = []
    for pattern in patterns:
        try:
            out = subprocess.run(
                ["grep", "-rn", "--include=" + glob_pattern,
                 pattern, str(REPO_ROOT / "ocos")],
                capture_output=True, text=True, timeout=10,
            )
            results.extend(out.stdout.strip().split("\n"))
        except subprocess.TimeoutExpired:
            pass
    # 排除 _archive 和 .pyc
    return [l for l in results if l and "_archive" not in l and ".pyc" not in l]


class TestPhaseCChecklist:
    """固化 NOT TRIGGERED 结论的回归保护。"""

    def test_c1_no_behavior_candidate_class(self):
        """C1 必须 FAIL：仓库中不存在 BehaviorCandidate / ActionCandidate 类。

        注意: ExtensionCandidate / InteractionCandidate 等是其他层概念，
        不是 ER-2 Phase 4 定义的 Action 层 BehaviorCandidate。
        """
        matches = _grep("*.py", [
            "class BehaviorCandidate",
            "class ActionCandidate",
        ])
        assert matches == [], (
            f"⛔ Phase C NOT TRIGGERED — 不允许创建 BehaviorCandidate 类。"
            f"意外发现: {matches}. 如需重新评估 Phase 4，"
            f"请修改本测试并走 roadmap Phase C 闸门流程。"
        )

    def test_c2_no_candidate_production_path(self):
        """C2 必须 FAIL：无独立 BehaviorCandidate 产生路径。

        注意：ExperienceCandidate / PatternCandidate 是 Memory 层内部
        数据（Episode 提升过程中的中间态），不是 ER-2 Phase 4 定义的
        "DecisionBridge 可消费的 Action 层 BehaviorCandidate"。
        """
        # 精确匹配：类定义 + 工厂函数 + Store + DAO（全部是 Behavior 层语义）
        matches = _grep("*.py", [
            # 类定义：带 Behavior 前缀或明确是 Action 层
            "class BehaviorCandidate[(:]",
            "class ActionCandidate[(:]",
            # 工厂/产生函数
            "def generate_behavior_candidate",
            "def generate_action_candidate",
            "def produce_behavior_candidate",
            "BehaviorCandidateFactory",
            "ActionCandidateFactory",
            # 持久化
            "class CandidateStore",
            "class BehaviorCandidateStore",
            "class ActionCandidateStore",
            "CandidateDAO",
        ])
        assert matches == [], (
            f"⛔ Phase C NOT TRIGGERED — 不允许新增 BehaviorCandidate 产生路径。"
            f"意外发现: {matches}. 如需重新评估 Phase 4，"
            f"请修改本测试并走 roadmap Phase C 闸门流程。"
        )

    def test_c3_bridge_does_not_consume_candidates(self):
        """C3 必须 FAIL：DecisionBridge 不消费 Candidate 实体。

        bridge.py 里允许出现 "candidate" 这个词作为局部变量名
        （如 path_candidates 路径匹配），但**不允许**出现
        "candidate" 作为外部持久化实体的消费路径。
        这里的简化保护：bridge.py 中不出现 "Candidate"（大写开头，
        暗示类名引用）。
        """
        bridge_path = REPO_ROOT / "ocos" / "execution" / "bridge.py"
        content = bridge_path.read_text(encoding="utf-8")
        # 允许 "candidate" 小写（局部变量），禁止 "Candidate" 大写（类引用）
        forbidden = [
            "BehaviorCandidate",
            "ActionCandidate",
            "CandidateStore",
            "CandidateDAO",
        ]
        found = [w for w in forbidden if w in content]
        assert found == [], (
            f"⛔ Phase C NOT TRIGGERED — DecisionBridge 不允许消费 Candidate。"
            f"意外发现: {found}. 如需重新评估 Phase 4，"
            f"请修改本测试并走 roadmap Phase C 闸门流程。"
        )

    def test_c4_no_behavior_candidate_persistence(self):
        """C4 必须 FAIL：不存在 BehaviorCandidate 持久化表。"""
        matches = _grep("*.py", [
            "CREATE TABLE.*behavior_candidate",
            "CREATE TABLE.*action_candidate",
            "behavior_candidate.*table",
            "INSERT INTO behavior_candidate",
            "behavior_candidate",  # 整体词搜索
        ])
        # 排除 PatternCandidate / ExperienceCandidate（Memory 层内部概念）
        matches = [m for m in matches
                   if "PatternCandidate" not in m
                   and "ExperienceCandidate" not in m]
        assert matches == [], (
            f"⛔ Phase C NOT TRIGGERED — 不允许新增 BehaviorCandidate 持久化表。"
            f"意外发现: {matches}. 如需重新评估 Phase 4，"
            f"请修改本测试并走 roadmap Phase C 闸门流程。"
        )

    def test_c0_er2_evidence_exists(self):
        """C0 必须 PASS：ER-2 B 类负效应证据必须存在。"""
        er2_path = REPO_ROOT / "docs" / "ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md"
        assert er2_path.exists(), "ER-2 原始决策文档缺失"
        content = er2_path.read_text(encoding="utf-8")
        # 关键证据：B=0/10
        assert "0/10" in content, "ER-2 B 类负效应证据 (0/10) 缺失"
        assert "三代" in content or "R4" in content, "ER-2 三代复现证据缺失"
