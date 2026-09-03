"""ocos growth — 成长模块 CLI。

用法:
    ocos growth ingest --topic "..." --summary "..." [--source hermes] [--url ...]
    ocos growth analyze [--signal <id>]
    ocos growth execute <proposal_id>
    ocos growth status
    ocos growth grow --topic "..." --summary "..."   (注入→分析→执行 一键)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ocos.growth.engine import (
    GrowthAnalyzer,
    GrowthEngine,
    GrowthOptimizer,
    GrowthProposal,
    GrowthSignalStore,
    TechSignal,
    PROJECT_ROOT,
)
from ocos.interaction.base import InteractionSession


def _make_engine(llm: bool = True) -> GrowthEngine:
    """构建引擎。llm=True 时接入真实 TextGenerator (agnes)。"""
    store = GrowthSignalStore()
    optimizer = GrowthOptimizer(project_root=PROJECT_ROOT)
    analyzer = None
    if llm:
        def _llm(prompt: str) -> str:
            from ocos.engines.text_generator import get_text_generator
            import asyncio
            tg = get_text_generator()
            provider = getattr(tg, "_provider", tg)
            gen = getattr(provider, "generate", None)
            if gen is None:
                return '{"worthwhile": false, "rationale": "no LLM provider"}'
            try:
                result = asyncio.run(gen(prompt=prompt, system_prompt=(
                    "你是 OCOS 内核架构师，只输出 JSON。")))
                return str(result)
            except Exception as e:  # pragma: no cover
                return f'{{"worthwhile": false, "rationale": "llm error: {e}"}}'

        # 预检: LLM 依赖可用性 (openai 包) — 缺失时明确报错而非静默无提案
        try:
            import openai  # noqa: F401
        except ImportError:
            print(
                "Error: LLM 分析不可用 — 当前 Python 环境缺少 'openai' 包。\n"
                "  CLI venv 缺依赖时 growth analyze/grow 的 LLM 分析会静默失效。\n"
                "  修复: 安装依赖或改用含 openai 的环境运行 (如 daemon 的 opentale/.venv)。\n"
                "  信号已持久化, 环境修复后重跑 analyze 即可。",
                file=sys.stderr)
            # 返回仅存储引擎 (无 LLM), 不伪装分析成功
            engine = GrowthEngine(store=GrowthSignalStore(), optimizer=optimizer)
            return engine
        analyzer = GrowthAnalyzer(llm_fn=_llm)
    else:
        analyzer = GrowthAnalyzer()  # 无 LLM → 只接收/存储

    engine = GrowthEngine(store=store, analyzer=analyzer, optimizer=optimizer)
    return engine


def cmd_growth_ingest(args, session: InteractionSession) -> int:
    if not args.summary:
        print("Error: --summary required (≥60 chars)", file=sys.stderr)
        return 2
    signal = TechSignal(
        topic=args.topic or "tech-signal",
        summary=args.summary,
        source=args.source or "external",
        source_url=args.url or "",
        domain=args.domain or "python",
        confidence=args.confidence or 0.5,
    )
    engine = _make_engine(llm=False)
    try:
        signal_id = engine.ingest(signal)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(f"Signal received: {signal_id}")
    print(f"  topic: {signal.topic}")
    print(f"  pending: run 'ocos growth analyze' to process")
    return 0


def cmd_growth_analyze(args, session: InteractionSession) -> int:
    engine = _make_engine(llm=True)
    proposals = engine.analyze_pending()
    if not proposals:
        print("No worthwhile proposals from pending signals (or no pending signals).")
        return 0
    for p in proposals:
        print(f"\nProposal: {p.proposal_id}")
        print(f"  topic:      {p.signal_topic}")
        print(f"  file:       {p.file_path}")
        print(f"  applies:    {p.applicability:.2f}")
        print(f"  rationale:  {p.rationale[:300]}")
        print(f"  → run 'ocos growth execute {p.proposal_id}' to apply (auto-test, rollback)")
    return 0


def cmd_growth_execute(args, session: InteractionSession) -> int:
    """执行已分析提案。Proposal 需从 DB 恢复 — 当前分析产物在内存,
    因此 execute 走重新分析+自动执行: 对最新提案直接 apply。"""
    engine = _make_engine(llm=False)
    # 从 growth_log / signals 恢复 proposal 不完整 — 此处执行最近一次分析
    # 简化: execute <proposal_id> 需配套 analyze 产物; 直接调 grow 一键链路
    print("Use 'ocos growth grow --topic ... --summary ...' for one-shot "
          "ingest→analyze→execute, or 'ocos growth analyze' to preview.")
    return 0


def cmd_growth_status(args, session: InteractionSession) -> int:
    engine = _make_engine(llm=False)
    history = engine.store.history(limit=args.limit or 20)
    print(f"Growth history ({len(history)} records):")
    if not history:
        print("  (empty)")
    for h in history:
        print(f"  {h['proposal_id']}  {h['status']:<12} {h['file_path']:<40} "
              f"tests {h['tests_passed']}p/{h['tests_failed']}f  {h['reason'][:80]}")
    return 0


def cmd_growth_grow(args, session: InteractionSession) -> int:
    """一键: 注入信号 → LLM 分析 → 自动执行 (受治理+回滚)。"""
    if not args.summary:
        print("Error: --summary required (≥60 chars)", file=sys.stderr)
        return 2
    signal = TechSignal(
        topic=args.topic or "tech-signal",
        summary=args.summary,
        source=args.source or "cli",
        source_url=args.url or "",
        domain=args.domain or "python",
        confidence=args.confidence or 0.5,
    )
    if args.preview:
        engine = _make_engine(llm=True)
        sig_id = engine.ingest(signal)
        print(f"Signal: {sig_id}")
        print("Analyzing (LLM)...")
        proposals = engine.analyze_pending()
        if not proposals:
            print("No worthwhile optimization proposed.")
            return 0
        for p in proposals:
            print(f"\nProposal: {p.proposal_id}  →  {p.file_path}")
            print(f"  applies={p.applicability:.2f}")
            print(f"  rationale: {p.rationale[:400]}")
            print(f"  new_content: {len(p.new_content)} chars")
            print("\n--- DIFF (preview) ---")
            try:
                import difflib
                orig = (PROJECT_ROOT / p.file_path).read_text(encoding="utf-8")
                for line in difflib.unified_diff(
                        orig.splitlines(), p.new_content.splitlines(),
                        fromfile=p.file_path, tofile=p.file_path + " (proposed)"):
                    print(line)
            except FileNotFoundError:
                print(f"(new file: {p.file_path})")
            print("--- END DIFF ---")
            print(f"\nApprove? Run: ocos growth grow --execute-proposal {p.proposal_id}")
        return 0

    # 完整自动链路
    engine = _make_engine(llm=True)
    sig_id = engine.ingest(signal)
    print(f"Signal: {sig_id}")
    print("Analyzing...")
    proposals = engine.analyze_pending()
    if not proposals:
        print("No worthwhile optimization proposed — nothing executed.")
        return 0
    for p in proposals:
        print(f"\nExecuting proposal {p.proposal_id} → {p.file_path}")
        result = engine.execute_proposal(p)
        print(f"  status: {result.status}")
        print(f"  reason: {result.reason}")
        if result.status == "applied":
            print(f"  tests:  {result.tests_passed} passed / {result.tests_failed} failed")
        elif result.status == "rolled_back":
            print("  ⚠ 修改已自动回滚 (测试失败/写入异常)")
        elif result.status == "skipped":
            print("  (跳过: 适用度低或修饰器拒绝)")
    return 0


def cmd_growth(args, session: InteractionSession) -> int:
    """growth 路由。"""
    action = getattr(args, "growth_action", "")
    if action == "ingest":
        return cmd_growth_ingest(args, session)
    if action == "analyze":
        return cmd_growth_analyze(args, session)
    if action == "status":
        return cmd_growth_status(args, session)
    if action == "grow":
        return cmd_growth_grow(args, session)
    if action == "execute":
        return cmd_growth_execute(args, session)
    print(__doc__)
    return 1
