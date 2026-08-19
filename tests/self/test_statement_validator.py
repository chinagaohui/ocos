"""Phase 25.3 — Gate Tests: StatementValidator。

验证:
  25.3-SV01: 合法 statement 通过
  25.3-SV02: 空字符串拒绝
  25.3-SV03: 情感词汇拒绝
  25.3-SV04: 偏好词汇拒绝
  25.3-SV05: 价值词汇拒绝
  25.3-SV06: 目标词汇拒绝
  25.3-SV07: 人格词汇拒绝
  25.3-SV08: 叙事词汇拒绝
  25.3-SV09: 超长 statement 拒绝
  25.3-SV10: 无事实主语拒绝
  25.3-SV11: scan_for_forbidden 扫描
"""

import pytest
from ocos.self.statement_validator import StatementValidator


# ── 25.3-SV01: 合法 statement ────────────────────────────────────────────

def test_valid_statement():
    valid, reason = StatementValidator.validate(
        "当前系统是一个信息处理和分析系统"
    )
    assert valid, reason


def test_valid_statement_english():
    valid, reason = StatementValidator.validate(
        "The system processes information using frozen knowledge layers"
    )
    assert valid, reason


# ── 25.3-SV02: 空 ────────────────────────────────────────────────────────

def test_empty_statement():
    valid, reason = StatementValidator.validate("")
    assert not valid
    assert "empty" in reason


# ── 25.3-SV03: 情感 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["喜欢", "害怕", "渴望", "happy", "sad", "angry"])
def test_emotion_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统{word}处理信息")
    assert not valid, f"Should reject emotion word '{word}'"
    assert "情感" in reason


# ── 25.3-SV04: 偏好 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["倾向", "偏好", "prefer", "inclined"])
def test_preference_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统{word}使用数据分析方法")
    assert not valid, f"Should reject preference word '{word}'"
    assert "偏好" in reason


# ── 25.3-SV05: 价值 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["应该", "重要", "必要的", "should", "important"])
def test_value_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统认为{word}保持一致性")
    assert not valid, f"Should reject value word '{word}'"
    assert "价值判断" in reason


# ── 25.3-SV06: 目标 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["想要", "打算", "目标是", "want", "goal is"])
def test_goal_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统{word}优化处理流程")
    assert not valid, f"Should reject goal word '{word}'"
    assert "目标" in reason


# ── 25.3-SV07: 人格 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["友好", "诚实", "kind", "loyal"])
def test_personality_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统是一个{word}的工具")
    assert not valid, f"Should reject personality word '{word}'"
    assert "人格" in reason


# ── 25.3-SV08: 叙事 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["成为", "变成", "become", "evolve into"])
def test_narrative_forbidden(word: str):
    valid, reason = StatementValidator.validate(f"当前系统{word}更先进的系统")
    assert not valid, f"Should reject narrative word '{word}'"
    assert "叙事" in reason


# ── 25.3-SV09: 超长 ──────────────────────────────────────────────────────

def test_too_long():
    long_stmt = "当前系统" + "是一个" * 100 + "系统"
    valid, reason = StatementValidator.validate(long_stmt)
    assert not valid
    assert "200" in reason


# ── 25.3-SV10: 无事实主语 ────────────────────────────────────────────────

def test_no_factual_subject():
    valid, reason = StatementValidator.validate("我是一个数据处理系统")
    assert not valid
    assert "factual subject" in reason


# ── 25.3-SV11: scan_for_forbidden ────────────────────────────────────────

def test_scan_for_forbidden():
    """代码审计扫描——检测文本中的禁止词汇。"""
    text = "这个系统 happy 而且 prefer 处理 should 结果"
    hits = StatementValidator.scan_for_forbidden(text)
    assert len(hits) >= 3
    categories = {h[0] for h in hits}
    assert "emotion" in categories or "preference" in categories or "value" in categories
