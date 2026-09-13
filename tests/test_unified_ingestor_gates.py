"""COG-V2 Phase 0.2: UnifiedIngestor 语义质量门测试。

生产实测 808 条 knowledge 中 64% 是垃圾（LLM 拒答/套娃引用/原始日志）。
质量门必须在入库前确定性拦截，且不误伤正常知识。
"""

from __future__ import annotations

from ocos.learning.unified_ingestor import (
    IngestArtifact,
    IngestStatus,
    SourceChannel,
    UnifiedIngestor,
)


def _ingest(content: str):
    ing = UnifiedIngestor(idempotent_check=lambda _key: False)
    art = IngestArtifact(
        channel=SourceChannel.LLM_QA,
        content=content,
        confidence=0.8,
        knowledge_type="fact",
    )
    return ing.ingest(art)[0]


def test_json_log_gate():
    r = _ingest('{"success": false, "cycle": 4, "task_success_rate": 0.0}')
    assert r.status == IngestStatus.FILTERED_LOW_QUALITY


def test_refusal_gate_chinese():
    r = _ingest("我没有关于「环境探测任务」这一特定任务类型的权威知识库来源，"
                "无法确认你所指的具体定义。")
    assert r.status == IngestStatus.FILTERED_LOW_QUALITY
    assert "拒答" in r.message


def test_refusal_gate_english():
    r = _ingest("As an AI, I don't have access to a live database and "
                "cannot provide the exact current numbers.")
    assert r.status == IngestStatus.FILTERED_LOW_QUALITY


def test_recursive_quote_gate():
    r = _ingest("✓ EVO-Plan: new_knowledge — 新知识 [procedure] 说 "
                "'✓ EVO → retry scheduled' 这一轮学习到了什么？")
    assert r.status == IngestStatus.FILTERED_LOW_QUALITY
    assert "套娃" in r.message


def test_normal_knowledge_passes_gate():
    # 无 registry 时存储降级（可能带 errors），但不得被质量门拦截
    r = _ingest("arXiv API 的正确用法：query 参数使用 all: 字段检索，"
                "多词用 AND 连接，sortBy=submittedDate 可按日期排序。")
    assert r.status != IngestStatus.FILTERED_LOW_QUALITY, r.message
