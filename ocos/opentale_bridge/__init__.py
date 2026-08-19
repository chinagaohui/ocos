"""Phase 59: OCOS-OpenTale Bridge.

Hermes Agent as the operator: feeds OCOS (brain), translates decisions,
invokes OpenTale (writing organ), and feeds output back to OCOS for learning.

Architecture:
    Hermes Agent ──feed──▶ OCOS ──decide──▶ Translator ──▶ OpenTale Writer
         ▲                                                       │
         └────────── Feedback Loop ◀────── chapter output ───────┘

Usage:
    from ocos.opentale_bridge import BridgeSessionOrchestrator, quick_bridge_test

    orch = BridgeSessionOrchestrator("my_novel")
    orch.run_full_cycle(context_chunks=["romance novel setup"], genre="romance")
"""

from ocos.opentale_bridge.bridge_model import (
    BridgePhase,
    BridgeSession,
    OcosDecision,
    TranslationResult,
    FeedbackInput,
    WebFeedResult,
    RepairDecision,
    ContractAdjustment,
)
from ocos.opentale_bridge.decision_translator import DecisionTranslator
from ocos.opentale_bridge.feedback_loop import FeedbackLoop
from ocos.opentale_bridge.web_feeder import WebFeeder
from ocos.opentale_bridge.bridge_session import BridgeSessionOrchestrator
from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer, QualityReport, DimensionScore
from ocos.opentale_bridge.trend_analyzer import TrendAnalyzer, TrendSignal


def quick_bridge_test() -> dict:
    """Run a quick bridge verification and return summary."""
    from ocos.opentale_bridge.bridge_session import BridgeSessionOrchestrator

    orch = BridgeSessionOrchestrator("ocos_bridge_test")

    # Step 1: Feed web data to OCOS
    orch.feed_web_data("writing_techniques")
    orch.feed_web_data("genre_analysis")

    # Step 2-5: Full cycle
    orch.run_full_cycle(
        context_chunks=[
            "古言言情小说《凤囚凰》续写项目",
            "主角设定：女将军x腹黑王爷，权谋+爱情双线",
            "当前进度：第12章，感情线正在升温，权谋线暗流涌动",
        ],
        genre="romance",
        chapter_number=13,
        total_chapters=60,
    )

    return orch.session.to_dict()


def quick_web_feed_test() -> dict:
    """Test web feeding to OCOS and return summary."""
    feeder = WebFeeder()
    results = feeder.feed_all_topics()
    return {
        "strategies_used": len(results),
        "total_chunks": sum(r.chunks_ingested for r in results),
        "all_topics": [r.topics_covered for r in results],
    }


__all__ = [
    # Types
    "BridgePhase", "BridgeSession", "OcosDecision",
    "TranslationResult", "FeedbackInput", "WebFeedResult",
    "RepairDecision", "ContractAdjustment",
    # Trend analysis (Phase 59-j)
    "TrendAnalyzer", "TrendSignal",
    # Components
    "DecisionTranslator", "FeedbackLoop", "WebFeeder",
    "BridgeSessionOrchestrator",
    # Quality analysis (Phase 59-g)
    "QualityAnalyzer", "QualityReport", "DimensionScore",
    # Quick tests
    "quick_bridge_test", "quick_web_feed_test",
]
