"""trace_context.py — Phase R1 Trace Identity：结构化 TraceContext（OCOS 侧）。

R1.1 契约（docs/audit/PHASE_R1_TRACE_CONTRACT_20260819.md）：
- correlation_id 跨系统根（OpenTale 生成，OCOS 原样传播，禁止重新生成）
- agent_run_id 由 OCOS（Agent 入口）生成
- 传输：HTTP 头 X-Trace-Correlation-Id / X-Trace-Agent-Run-Id /
         X-Trace-Generation-Request-Id / X-Trace-Source(JSON)
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = "1.0"

HDR_CORRELATION = "X-Trace-Correlation-Id"
HDR_AGENT_RUN = "X-Trace-Agent-Run-Id"
HDR_GENERATION = "X-Trace-Generation-Request-Id"
HDR_SOURCE = "X-Trace-Source"

ALL_HDRS = (HDR_CORRELATION, HDR_AGENT_RUN, HDR_GENERATION, HDR_SOURCE)


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%S")


def new_id(prefix: str, size: int = 8) -> str:
    return f"{prefix}{_ts()}_{uuid.uuid4().hex[:size]}"


@dataclass(frozen=True)
class TraceContext:
    """结构化 Trace Context（冻结 schema，R1.1 §3）。"""
    correlation_id: str
    agent_run_id: str = ""
    generation_request_id: str = ""
    parent_id: str = ""
    source_system: str = "OCOS"
    source_component: str = ""
    schema_version: str = SCHEMA_VERSION

    def with_component(self, comp: str) -> "TraceContext":
        return TraceContext(
            correlation_id=self.correlation_id,
            agent_run_id=self.agent_run_id,
            generation_request_id=self.generation_request_id,
            parent_id=self.parent_id,
            source_system=self.source_system,
            source_component=comp,
            schema_version=self.schema_version,
        )

    def to_headers(self) -> dict[str, str]:
        """结构化传输（R1.1 §3）：禁止散落 payload 字段。"""
        src = {"system": self.source_system, "component": self.source_component,
               "schema_version": self.schema_version}
        h = {HDR_CORRELATION: self.correlation_id}
        if self.agent_run_id:
            h[HDR_AGENT_RUN] = self.agent_run_id
        if self.generation_request_id:
            h[HDR_GENERATION] = self.generation_request_id
        h[HDR_SOURCE] = json.dumps(src, ensure_ascii=False, separators=(",", ":"))
        return h

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def parse_headers(headers: dict) -> "TraceContext":
        """从入站请求头解析（T-04 Stability：收到的 ID 原样保留，不重新定义）。"""
        src = {}
        try:
            src = json.loads(headers.get(HDR_SOURCE, "{}") or "{}")
        except Exception:
            src = {}
        return TraceContext(
            correlation_id=(headers.get(HDR_CORRELATION) or "").strip(),
            agent_run_id=(headers.get(HDR_AGENT_RUN) or "").strip(),
            generation_request_id=(headers.get(HDR_GENERATION) or "").strip(),
            source_system=src.get("system", "") or "",
            source_component=src.get("component", "") or "",
            schema_version=src.get("schema_version", SCHEMA_VERSION),
        )

    @staticmethod
    def new_root(component: str = "", source_system: str = "OpenTale") -> "TraceContext":
        """生成新的跨系统根。

        R1.1 契约：根由入口系统生成（OpenTale 入口 = OpenTale 生成）。
        U4.2 修正：OCOS chat 为独立用户入口（无 OpenTale 前置）时，OCOS 作为入口
        生成根（source_system="OCOS"）；**已收到外部 corr 时禁止重新生成**（T-04）。
        """
        return TraceContext(correlation_id=new_id("corr_"), source_system=source_system,
                            source_component=component)
