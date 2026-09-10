"""OCOS CLI: evolution artifact 审核命令.

用法:
  ocos evolution list              # 列出所有 PENDING 待审产物
  ocos evolution list --all        # 列出所有状态产物
  ocos evolution list --type plan  # 按类型过滤
  ocos evolution show EVO-XXX      # 查看完整内容
  ocos evolution approve EVO-XXX   # 批准 (沉淀到 knowledge principle)
  ocos evolution reject EVO-XXX    # 拒绝
  ocos evolution stats             # 统计概览
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _db_path() -> str:
    """动态计算 DB 路径（和 daemon 用同一个）。"""
    return str(Path.home() / ".ocos" / "ocos.db")


def _get_store():
    from ocos.evolution.artifacts import EvolutionArtifactStore
    return EvolutionArtifactStore(str(_db_path()))


def _cmd_list(args) -> int:
    from ocos.evolution.artifacts import ArtifactStatus, ArtifactType

    store = _get_store()
    status = None
    if not args.all and not args.status:
        status = ArtifactStatus.PENDING
    elif args.status:
        status = ArtifactStatus(args.status)

    type_filter = ArtifactType(args.type) if args.type else None

    items = store.list(status=status, type=type_filter, limit=args.limit or 50)
    if not items:
        print("  (无待审产物)")
        return 0

    # 表头
    print(f"  {'ID':<18} {'类型':<10} {'状态':<10} {'风险':<8} {'摘要'}")
    print(f"  {'─' * 70}")
    for a in items:
        print(
            f"  {a.artifact_id:<18} {a.type.value:<10} {a.status.value:<10} "
            f"{a.risk_level:<8} {a.summary[:35]}"
        )
    print(f"\n  共 {len(items)} 条")
    return 0


def _cmd_show(args) -> int:
    store = _get_store()
    art = store.get(args.id)
    if art is None:
        print(f"❌ 找不到 {args.id}", file=sys.stderr)
        return 1

    # 直接读 Markdown 文件
    md_path = Path.home() / ".ocos" / "artifacts" / {
        "plan": "plans", "patch": "patches",
        "report": "reports", "experiment": "experiments",
    }.get(art.type.value, "plans") / f"{art.artifact_id}.md"

    if md_path.exists():
        print(md_path.read_text())
    else:
        # fallback 直接打印 content
        print(f"# {art.title}\n\n{art.content}")
    return 0


def _cmd_approve(args) -> int:
    from ocos.evolution.artifacts import ArtifactStatus, EvolutionArtifact
    from ocos.learning.unified_ingestor import (
        UnifiedIngestor, IngestArtifact, SourceChannel, IngestStatus,
    )
    from ocos.memory.semantic.store import SemanticStore
    from ocos.knowledge.store.registry import KnowledgeRegistry, AccessMatrix
    from ocos.knowledge.store.ontology import KnowledgeLevel

    store = _get_store()
    art = store.get(args.id)
    if art is None:
        print(f"❌ 找不到 {args.id}", file=sys.stderr)
        return 1
    if art.status != EvolutionArtifact.__dataclass_fields__["status"].default:
        # 已审核过
        if art.status.value != "pending":
            print(f"⚠️  该产物已经是 {art.status.value} 状态，不能重复审核")
            return 1

    comment = args.comment or "(CLI approve)"
    approved = store.review(args.id, ArtifactStatus.APPROVED,
                            reviewer=args.reviewer or "cli_user",
                            comment=comment)
    if approved is None:
        print(f"❌ 审核失败", file=sys.stderr)
        return 1

    print(f"✅ 已批准 {art.artifact_id}")

    # 如果是 PLAN 类型 — 同步沉淀到 knowledge (principle 层)
    if art.type.value == "plan":
        try:
            ss = SemanticStore(db_path=str(_db_path()))
            ss.initialize()
            am = AccessMatrix()
            for lvl in KnowledgeLevel:
                am.set_permission("evolution_approve", lvl,
                                  can_read=True, can_write=True)
            kr = KnowledgeRegistry(semantic_store=ss, access_matrix=am)
            ingestor = UnifiedIngestor(knowledge_registry=kr,
                                       db_path=str(_db_path()))

            plan_art = IngestArtifact(
                channel=SourceChannel.LLM_QA,
                content=f"[自进化方案·人工批准] {art.content[:500]}",
                title=art.title[:80],
                confidence=art.confidence,
                tags=["self_evolution", "approved", *art.tags],
                knowledge_type="principle",
            )
            results = ingestor.ingest(plan_art, owner="evolution_approve")
            for r in results:
                if r.status == IngestStatus.STORED:
                    print(f"  📝 已沉淀到 knowledge principle 层 (auto)")
        except Exception as e:
            print(f"  ⚠️  knowledge 沉淀失败 (不影响审核): {e}")

    return 0


def _cmd_reject(args) -> int:
    from ocos.evolution.artifacts import ArtifactStatus

    store = _get_store()
    art = store.get(args.id)
    if art is None:
        print(f"❌ 找不到 {args.id}", file=sys.stderr)
        return 1

    store.review(
        args.id, ArtifactStatus.REJECTED,
        reviewer=args.reviewer or "cli_user",
        comment=args.comment or "(CLI reject)",
    )
    print(f"❌ 已拒绝 {art.artifact_id}")
    return 0


def _cmd_stats(args) -> int:
    store = _get_store()
    items = store.list(limit=200)

    from collections import Counter
    status_counts = Counter(a.status.value for a in items)
    type_counts = Counter(a.type.value for a in items)
    risk_counts = Counter(a.risk_level for a in items)

    print(f"  总产物: {len(items)}")
    print(f"\n  状态分布:")
    for s, c in status_counts.most_common():
        print(f"    {s:<12} {c}")
    print(f"\n  类型分布:")
    for t, c in type_counts.most_common():
        print(f"    {t:<12} {c}")
    print(f"\n  风险分布:")
    for r, c in risk_counts.most_common():
        print(f"    {r:<8} {c}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "evolution", help="自进化产物审核 (plan/patch/report)")
    sub = p.add_subparsers(dest="evo_cmd")

    # list
    p_list = sub.add_parser("list", help="列出待审产物")
    p_list.add_argument("--all", action="store_true",
                        help="列出所有状态 (不仅 PENDING)")
    p_list.add_argument("--type", choices=["plan", "patch", "report", "experiment"],
                        help="按类型过滤")
    p_list.add_argument("--status", choices=["pending", "approved", "rejected",
                                             "applied", "superseded"],
                        help="按状态过滤")
    p_list.add_argument("--limit", type=int, default=50)

    # show
    p_show = sub.add_parser("show", help="查看产物完整内容")
    p_show.add_argument("id", help="EVO-XXXXXX")

    # approve
    p_approve = sub.add_parser("approve", help="人工批准 (同步沉淀 knowledge)")
    p_approve.add_argument("id", help="EVO-XXXXXX")
    p_approve.add_argument("--reviewer", default="cli_user")
    p_approve.add_argument("--comment", default="")

    # reject
    p_reject = sub.add_parser("reject", help="人工拒绝")
    p_reject.add_argument("id", help="EVO-XXXXXX")
    p_reject.add_argument("--reviewer", default="cli_user")
    p_reject.add_argument("--comment", default="")

    # stats
    sub.add_parser("stats", help="统计概览")


def dispatch(args) -> int:
    cmd = getattr(args, "evo_cmd", None)
    if cmd is None or cmd == "list":
        return _cmd_list(args)
    elif cmd == "show":
        return _cmd_show(args)
    elif cmd == "approve":
        return _cmd_approve(args)
    elif cmd == "reject":
        return _cmd_reject(args)
    elif cmd == "stats":
        return _cmd_stats(args)
    return 1
