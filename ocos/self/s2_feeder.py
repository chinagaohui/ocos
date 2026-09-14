"""S1 → S2 生产供数线（2026-09-14 恢复性迁移，P1 Production SelfState Restore）。

背景：P0-1/P1-1 把 S2 结构与三个生产读口（converse/bridge/recall_router）
上线后，S1→S2 的生产写入方缺位 —— S2 永远停在空骨架 v1，MEMORY_CTX 的
self 槽由 Phase 2 的「有数据」退化为 0。本模块只做一件事：把 S1 实测
画像经既有 frozen 证据管线喂给 committed S2，恢复生产生命线。

FROZEN 语义（与 P0-1 Step 2 一致，本模块不发明新路径）：

    旧 S1（历史经验性能力证据）
      │ bootstrap（一次性，S2 boot 后读 S1 已持久化快照）
      ▼
    S2 committed state
      ▲
      │ feed（每个 goal_result 闭合点，S1 calibrate 之后）
    S1 snapshot → capture_s1_snapshot → SelfEvidencePipeline
                  → recognition 门 → 治理门 → governed commit

硬约束：
  - S1 永远只是 Evidence 来源；本模块不调用 S1.render/render_brief，
    生产 Thinking 也绝不回退读 S1（读口只认 S2 accessor）。
  - 确定性、零 LLM：装箱/识别/提交全是规则与 SQL。
  - 幂等：同一 S1 内容重复喂（重启补偿、内容未变的闭合 tick）→
    管线语义 noop 门全部跳过 → 0 新版本、不灌 update_history。
  - 不新建 SelfStateManager：调用方（AgentRuntime）必须传入其 boot 时
    持有的同一 manager 实例 —— 注册表 accessor 绑定该实例，另建 manager
    提交后读路径看不到新 committed 态。
  - 失败只记日志/返回 0，绝不阻断 goal_result 主链（与 calibrate 同档）。
"""

from __future__ import annotations

import logging
from typing import Any

from ocos.self.agent_self_model import AgentSelfModel
from ocos.self.self_evidence import (
    SelfEvidencePipeline,
    UnrecognizableEvidence,
    capture_s1_snapshot,
)

logger = logging.getLogger(__name__)


def feed_s1_snapshot(manager: Any, snapshot: dict | None) -> int:
    """把一次 S1 实测快照经证据治理管线喂给 committed S2。

    返回本次新增的 committed 版本数（语义计数，非 claims 数）：
      0 = 无新信息（空快照 / 未跨 recognition 门 / 与 committed 语义相同）；
      n = 真实自我变化条目数（每条一个 governed version）。
    """
    if manager is None or not snapshot:
        return 0
    try:
        evidence = capture_s1_snapshot(snapshot)
    except Exception as e:  # noqa: BLE001 — 装箱失败不得阻断主链
        logger.debug("S1 snapshot → evidence skipped: %s", e)
        return 0
    if evidence is None:
        return 0
    try:
        committed = SelfEvidencePipeline(manager).ingest(evidence)
    except UnrecognizableEvidence as e:
        # 全小样本 / 无过门槛观测是正常态（全新部署、证据积累不足），非错误。
        logger.debug("S1 snapshot crossed no S2 recognition gate: %s", e)
        return 0
    except Exception as e:  # noqa: BLE001 — 治理/存储异常按 tick 隔离
        logger.warning("S2 feed from S1 snapshot failed this cycle: %s", e)
        return 0
    if committed:
        logger.info(
            "S2 fed from S1: +%d committed version(s) → v%d",
            len(committed), manager.version,
        )
    return len(committed)


def bootstrap_from_s1(manager: Any, s1_model: AgentSelfModel | None) -> int:
    """一次性 S1→S2 恢复性迁移：S2 boot 后读 S1 已持久化最新快照供数。

    幂等：
      - S1 从未校准（全新部署）→ 0，后续 goal_result feeder 自然供数；
      - S2 已反映该快照（重复启动/已喂过）→ 管线语义 noop 门 → 0。
    只在 S2 boot 路径调用一次；不是第二个持续供数源。
    """
    if manager is None or s1_model is None:
        return 0
    try:
        snap = s1_model.load()
    except Exception as e:  # noqa: BLE001
        logger.debug("S2 bootstrap: S1 load skipped: %s", e)
        return 0
    if not snap:
        logger.info("S2 bootstrap: S1 无持久化画像，跳过（等待 goal_result 供数）")
        return 0
    n = feed_s1_snapshot(manager, snap)
    logger.info(
        "S2 bootstrap from S1 v%s: %d committed version(s) → S2 v%d",
        snap.get("version"), n, manager.version,
    )
    return n


__all__ = ["feed_s1_snapshot", "bootstrap_from_s1"]
