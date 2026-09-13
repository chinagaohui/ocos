"""self_upgrade 应用侧去重闸回归（2026-09-07）。

缺陷史: 提案侧 _already_proposed 只比对 pending_actions，对话/引擎
直调 apply 的路径无防线 — 生产 self_knowledge.md "测试变更" 被重复
追加 128 次（246 行中 154 条重复）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ocos.agent.self_evolution_link as sel


@pytest.fixture
def knowledge_file(tmp_path, monkeypatch):
    """隔离宿主机 self_knowledge.md 与备份文件。"""
    kf = tmp_path / "self_knowledge.md"
    monkeypatch.setattr(sel, "_SELF_KNOWLEDGE", kf)
    monkeypatch.setattr(sel, "_BACKUP_FILE", tmp_path / "backup.json")
    return kf


class TestSelfUpgradeDedup:
    # P0-A 治理硬闸门 (2026-09-11): apply 必须携带 APPROVED state +
    # 真实 ApprovalRecord。用例统一经此助手调用以聚焦去重行为本身。
    _APPROVAL = {"actor": "test-approver", "timestamp": "2026-09-12T00:00:00+00:00"}

    @classmethod
    def _apply(cls, change: str) -> str:
        return sel.apply_self_upgrade(
            change, proposal_state="APPROVED", approval_record=cls._APPROVAL)

    def test_apply_appends_once(self, knowledge_file):
        out = self._apply("遇到超时应先重试一次再降级")
        assert "updated" in out
        content = knowledge_file.read_text(encoding="utf-8")
        assert content.count("遇到超时应先重试一次再降级") == 1

    def test_apply_same_change_is_skipped(self, knowledge_file):
        self._apply("遇到超时应先重试一次再降级")
        out = self._apply("遇到超时应先重试一次再降级")
        assert "already applied" in out
        # 两次日期不同也不追加 — 剥日期戳归一化比对
        content = knowledge_file.read_text(encoding="utf-8")
        assert content.count("遇到超时应先重试一次再降级") == 1

    def test_different_change_still_appends(self, knowledge_file):
        self._apply("规则 A")
        out = self._apply("规则 B")
        assert "updated" in out
        content = knowledge_file.read_text(encoding="utf-8")
        assert "规则 A" in content and "规则 B" in content

    def test_dedup_matches_without_date_stamp(self, knowledge_file):
        """手工预置旧条目（不同日期戳）→ 同文变更仍被识别为已应用。"""
        knowledge_file.write_text(
            "- [2026-09-05] 遇到超时应先重试一次再降级\n", encoding="utf-8")
        out = self._apply("遇到超时应先重试一次再降级")
        assert "already applied" in out

    def test_hard_gate_denies_unapproved_apply(self, knowledge_file):
        """P0-A: 无治理凭证的 apply 一律 DENY（fail-closed）。"""
        out = sel.apply_self_upgrade("无凭证变更")
        assert "GOVERNANCE-DENY" in out
        assert not knowledge_file.exists() or "无凭证变更" not in (
            knowledge_file.read_text(encoding="utf-8"))

    def test_apply_approved_goes_through_dedup(self, knowledge_file, tmp_path,
                                               monkeypatch):
        """治理链 apply_approved 同样受去重闸保护（重复批准不重复追加）。"""
        from ocos.evolution import evolution_memory as _em  # noqa: F401
        # propose_upgrade 需要真实治理链 — 直接用 apply_approved 的
        # 记账路径做单测（快照 + apply + EvolutionMemory）
        knowledge_file.write_text(
            "- [2026-09-05] 规则 A\n", encoding="utf-8")
        monkeypatch.setattr(sel, "_write_backup", lambda *a, **k: None)
        # EvolutionMemory 记账走 db — 隔离
        import sqlite3
        db = str(tmp_path / "evo.db")
        monkeypatch.setenv("OCOS_DB_PATH", db)
        out = sel.apply_approved(proposal_id="P1", title="t",
                                 change="规则 A")
        # 已存在同文 → 不追加（诚实返回，不假装成功）
        assert "already applied" in out["applied"]
        assert knowledge_file.read_text(encoding="utf-8").count("规则 A") == 1
