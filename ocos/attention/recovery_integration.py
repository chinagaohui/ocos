"""Phase 39.5: Attention Recovery — 注意力状态的持久化与恢复。

集成到 Phase 39.4 RecoveryManager:
    - Snapshot: 保存 AttentionState 到 RuntimeSnapshot
    - Restore: 从 Snapshot 恢复 AttentionState
    - Trace: 注意力恢复过程可审计

约束:
    - 不修改 RecoveryManager 核心逻辑 (39.4 冻结)
    - 注意力状态通过 Snapshot.attention_state 字段传播
"""

from __future__ import annotations

from typing import Any

from .attention_types import AttentionState, FocusType


def attention_state_to_snapshot(state: AttentionState | None) -> dict[str, Any] | None:
    """将 AttentionState 序列化为 snapshot dict。"""
    if state is None:
        return None
    return state.to_dict()


def attention_state_from_snapshot(data: dict[str, Any] | None) -> AttentionState | None:
    """从 snapshot dict 恢复 AttentionState。"""
    if data is None:
        return None
    return AttentionState.from_dict(data)


def validate_attention_restore(
    restored: AttentionState | None,
    original: AttentionState | None,
) -> tuple[bool, str]:
    """验证恢复后的注意力状态是否一致。

    Returns:
        (is_valid, message)
    """
    if original is None and restored is None:
        return True, "both None (no attention state)"
    if original is None and restored is not None:
        return False, "restored has attention state but original was None"
    if original is not None and restored is None:
        return False, "original had attention state but restored is None"

    # Compare key fields
    checks = []
    if restored.focus_id != original.focus_id:  # type: ignore[union-attr]
        checks.append(f"focus_id mismatch: {restored.focus_id} != {original.focus_id}")  # type: ignore[union-attr]
    if restored.focus_type != original.focus_type:  # type: ignore[union-attr]
        checks.append(f"focus_type mismatch: {restored.focus_type} != {original.focus_type}")  # type: ignore[union-attr]
    if abs(restored.focus_priority - original.focus_priority) > 0.01:  # type: ignore[union-attr]
        checks.append(f"priority mismatch: {restored.focus_priority} != {original.focus_priority}")  # type: ignore[union-attr]

    if checks:
        return False, "; ".join(checks)
    return True, "attention state restored correctly"
