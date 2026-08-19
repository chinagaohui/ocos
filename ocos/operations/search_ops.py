"""Phase 22-E — search_ops: 带白名单的真实搜索操作。

职责:
  - URL 白名单（API_WHITELIST）— 只允许预授权的搜索目标
  - 代理模式（可选）— 所有外部请求经代理转发
  - 审计日志 — 记录每次搜索请求

安全原则:
  - 无白名单 = 无外部调用
  - 白名单可配置但默认闭合
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import urllib.parse

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 白名单 ────────────────────────────────────────────────────────────────────

API_WHITELIST: set[str] = {
    "https://api.duckduckgo.com",
    "https://lite.duckduckgo.com",
    "https://en.wikipedia.org",
    "https://api.github.com",
    "http://localhost:11434",    # Ollama
    "http://localhost:8080",     # Local services
}

# 域名后缀白名单（*.example.com → example.com）
DOMAIN_SUFFIX_WHITELIST: set[str] = {
    "openai.com",
    "anthropic.com",
}


def is_url_allowed(url: str) -> bool:
    """检查 URL 是否在白名单中（含域名后缀匹配）。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname:
        base = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port and parsed.port not in (80, 443):
            base += f":{parsed.port}"
    else:
        base = url

    # 精确匹配
    if base in API_WHITELIST:
        return True

    # 域名后缀匹配
    if parsed.hostname:
        for suffix in DOMAIN_SUFFIX_WHITELIST:
            if parsed.hostname.endswith("." + suffix) or parsed.hostname == suffix:
                if parsed.scheme in ("https", "http"):
                    return True

    return False


# ── 搜索操作 ──────────────────────────────────────────────────────────────────


@dataclass
class SearchQuery:
    """搜索查询。"""
    query: str
    url: str
    params: dict[str, str] = field(default_factory=dict)
    timeout: float = 10.0
    max_results: int = 10


@dataclass
class SearchResult:
    """搜索结果。"""
    query: str
    url: str
    success: bool
    status_code: Optional[int] = None
    results: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SearchAuditRecord:
    """搜索审计记录。"""
    url: str
    allowed: bool
    query: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class SearchOps:
    """安全的搜索操作 — 白名单 + 审计。

    用法:
        ops = SearchOps(proxy=None)
        result = ops.search(SearchQuery(query="...", url="https://api.duckduckgo.com"))
    """

    def __init__(self, proxy: Optional[str] = None, strict: bool = True):
        self._proxy = proxy
        self._strict = strict  # strict=True 时拦截非白名单 URL
        self._audit_log: list[SearchAuditRecord] = []

    @property
    def audit_log(self) -> list[SearchAuditRecord]:
        return list(self._audit_log)

    def search(self, query: SearchQuery) -> SearchResult:
        """执行搜索（经白名单 + 代理）。

        Args:
            query: 搜索查询

        Returns:
            SearchResult
        """
        # ── 白名单校验 ──────────────────────────────────────────
        if not is_url_allowed(query.url):
            record = SearchAuditRecord(
                url=query.url,
                allowed=False,
                query=query.query,
                reason="URL not in allowed list",
            )
            self._audit_log.append(record)
            logger.warning("SearchOps: blocked URL %s", query.url)
            if self._strict:
                return SearchResult(
                    query=query.query,
                    url=query.url,
                    success=False,
                    error=f"URL not in allowed list: {query.url}",
                )

        # ── 代理转发 ────────────────────────────────────────────
        target_url = query.url
        if self._proxy:
            target_url = f"{self._proxy.rstrip('/')}/proxy?url={urllib.parse.quote(query.url)}"

        # ── 执行请求（真实 HTTP） ────────────────────────────────
        try:
            import urllib.request as urllib_request
            import json as _json

            full_url = target_url
            if query.params:
                full_url += "?" + urllib.parse.urlencode(query.params)

            req = urllib_request.Request(
                full_url,
                headers={"User-Agent": "OCOS/22.0 SearchOps"},
            )

            with urllib_request.urlopen(req, timeout=query.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                results = self._parse_response(body, query.max_results)

            search_result = SearchResult(
                query=query.query,
                url=query.url,
                success=True,
                status_code=resp.status,
                results=results,
            )

            # 审计
            self._audit_log.append(SearchAuditRecord(
                url=query.url,
                allowed=True,
                query=query.query,
                reason="ok",
            ))

            return search_result

        except Exception as e:
            logger.error("SearchOps: request failed for %s: %s", query.url, e)
            return SearchResult(
                query=query.query,
                url=query.url,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _parse_response(body: str, max_results: int) -> list[dict[str, Any]]:
        """解析搜索结果（JSON 或纯文本）。"""
        try:
            import json
            data = json.loads(body)
            # 尝试常见格式
            if isinstance(data, list):
                return data[:max_results]
            if isinstance(data, dict):
                for key in ("results", "items", "data", "hits"):
                    if key in data:
                        return data[key][:max_results]
                return [data]
        except Exception:
            pass
        return [{"text": body[:1000]}]  # fallback

    def get_history(self, limit: int = 20) -> list[SearchAuditRecord]:
        return self._audit_log[-limit:]

    def clear_history(self) -> None:
        self._audit_log.clear()
