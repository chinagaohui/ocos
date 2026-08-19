"""MasterAgent 单元测试（S5：OCOS 真实写作决策引擎）。

覆盖：
- 情感题材 → relationship + warmth（优势区）
- 科幻冲突 → conflict + tension
- 科幻悬疑 → investigation + suspense（S5 补充关键词，防误判）
- 显式提示覆盖
- 章节节奏（开局加速/收尾减速）
- 决策 → Organ 设定契约（characters/roles/world 绑定）
"""

from __future__ import annotations

from ocos.opentale_bridge.master_agent import MasterAgent, WritingIntent


def test_relationship_genre_decides_relationship_warmth() -> None:
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="离婚冷静期的三十天里重新面对感情与家庭责任，关系在误解与和解间摇摆。",
        genre="urban_romance", characters=["沈知意"], total_chapters=10))
    assert d.primary_focus == "relationship"
    assert d.emotional_tone == "warmth"
    assert d.pacing_directive == "accelerate"  # 开局加速


def test_conflict_genre_decides_conflict_tension() -> None:
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="星系殖民地的矿工起义，工程师与管理者在生存与秩序之间爆发对抗。",
        genre="sci_fi", total_chapters=12))
    assert d.primary_focus in ("conflict", "world")
    assert d.emotional_tone == "tension"


def test_investigation_genre_not_misjudged_as_relationship() -> None:
    """S5 补充关键词后：悬疑/调查题材不得误判为 relationship。"""
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="信号塔夜班检修员收到来自7天后的求救信号，信号里的声音是她自己。她必须查明谁在发信号、能否改变未来，而城市隐藏的秘密正浮出水面。",
        genre="sci_fi", characters=["林澈"], total_chapters=10))
    assert d.primary_focus == "investigation"
    assert d.emotional_tone in ("suspense", "tension")
    assert "线索浮现" in d.key_scenes


def test_explicit_hints_override_keywords() -> None:
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="一段足够长度的故事内容，用于测试提示覆盖逻辑。",
        focus_hint="character", tone_hint="warmth", total_chapters=5))
    assert d.primary_focus == "character"
    assert d.emotional_tone == "warmth"


def test_pacing_accelerate_open_decelerate_end() -> None:
    ma = MasterAgent()
    d_open = ma.decide(WritingIntent(premise="x" * 20, total_chapters=10), chapter=1)
    d_end = ma.decide(WritingIntent(premise="x" * 20, total_chapters=10), chapter=10)
    assert d_open.pacing_directive == "accelerate"
    assert d_end.pacing_directive == "decelerate"


def test_decision_has_character_instructions() -> None:
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="一段足够长度的故事内容，主角与反派的对抗。",
        characters=["林澈", "韩峥"],
        roles={"林澈": "主角", "韩峥": "反派"}, total_chapters=10))
    assert d.character_instructions.get("林澈")
    assert d.character_instructions.get("韩峥")
    assert d.confidence >= 0.8
    assert d.reasoning  # 决策可解释


def test_to_organ_contract_binds_setting() -> None:
    ma = MasterAgent()
    intent = WritingIntent(
        premise="一段足够长度的故事内容。",
        title="测试书", genre="sci_fi",
        characters=["林澈"], roles={"林澈": "主角"},
        world=["城市被浓雾笼罩"], total_chapters=8)
    contract = ma.to_organ_contract(intent)
    assert contract["title"] == "测试书"
    assert contract["chapters"] == 8
    assert contract["characters"] == ["林澈"]
    assert contract["roles"] == {"林澈": "主角"}
    assert contract["world"] == ["城市被浓雾笼罩"]
    assert contract["target_words"] == 8 * 2500


# ── P1-2/P1-3（S8 续）：词表修复 + R5 门禁 + E7 认知 ──


def test_capability_suspense_intent_investigation() -> None:
    """P1-2：能力系悬疑（大脑过载/预知）不得误判 relationship。"""
    ma = MasterAgent()
    d = ma.decide(WritingIntent(
        premise="我想写一部都市悬疑小说，主角有大脑过载的能力，能回忆所有记忆",
        genre="urban"))
    assert d.primary_focus == "investigation"
    assert d.emotional_tone in ("suspense", "tension")


def test_r5_decision_gate_fixes_invalid_values() -> None:
    """P1-3 R5：门禁修正非法枚举（不阻断 + 记录）。"""
    ma = MasterAgent()
    # 构造非法决策直接过门禁
    from ocos.opentale_bridge.bridge_model import OcosDecision
    bad = OcosDecision(decision_id="d1", primary_focus="invalid_focus",
                       emotional_tone="invalid_tone", pacing_directive="invalid",
                       word_target=99999999)
    ma._writing_decision_gate(bad)
    assert bad.primary_focus == "relationship"
    assert bad.emotional_tone == "tension"
    assert bad.pacing_directive == "maintain"
    assert bad.word_target == 3000


def test_e7_cognition_context_references_feedback(monkeypatch, tmp_path) -> None:
    """P1-3 E7：决策上下文引用项目反馈（C3 数据打通）。"""
    import json
    fb_dir = tmp_path / "feedback"
    fb_dir.mkdir()
    (fb_dir / "认知书.json").write_text(json.dumps([
        {"project": "认知书", "book_review_score": 91.0, "chapters": 5}
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("OCOS_FEEDBACK_DIR", str(fb_dir))
    ma = MasterAgent()
    ctx = ma._collect_cognition_context(WritingIntent(premise="x", title="认知书"))
    assert "91.0" in ctx and "5" in ctx
