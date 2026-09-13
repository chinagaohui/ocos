"""Phase 22-E — search_ops: 带白名单的真实搜索操作。

职责:
  - URL 白名单（API_WHITELIST）— 只允许预授权的搜索目标
  - 本地搜索通道（local://websearch）— 经白名单调用本地 websearch.py
    （cn.bing 免费引擎，2026-09-12 替换被墙的 DuckDuckGo IA 通道）
  - 代理模式（可选）— 所有外部请求经代理转发
  - 审计日志 — 记录每次搜索请求

安全原则:
  - 无白名单 = 无外部调用
  - 白名单可配置但默认闭合
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    "local://websearch",         # 本地 websearch.py（cn.bing，2026-09-12）
}

# ── 本地搜索通道 ──────────────────────────────────────────────────────────────

LOCAL_WEBSEARCH_URL = "local://websearch"

# 脚本路径：环境变量 OCOS_WEBSEARCH_SCRIPT 可覆盖，默认 ~/.ocos/scripts/websearch.py
WEBSEARCH_SCRIPT = Path(
    os.environ.get("OCOS_WEBSEARCH_SCRIPT", "~/.ocos/scripts/websearch.py")
).expanduser()

# 本地脚本内部最多 2 次 UA 重试 × 15s 网络超时，subprocess 上限给足余量
LOCAL_SEARCH_TIMEOUT_FLOOR = 45.0

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

# ── 通道熔断（2026-09-12）────────────────────────────────────────────────────
# 背景: api.duckduckgo.com 在当前网络环境不可达（被墙），WebResearcher 每
# ~20min 周期重试，每次 urlopen 超时白烧时间并刷 ERROR 日志。通道级熔断:
# 连续失败达阈值后暂停该 base URL 一段时间，冷却结束自动半开（放行探测）。
SEARCH_FAILURE_THRESHOLD = 3      # 连续失败 N 次后熔断
SEARCH_COOLDOWN_SECONDS = 4 * 3600  # 熔断持续 4 小时


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

    # 类级熔断状态 — SearchOps() 多处临时实例化（daemon/bridge），
    # 熔断必须跨实例共享；锁保护并发 tick 线程的计数更新。
    _circuit_lock = threading.Lock()
    _failure_counts: dict[str, int] = {}
    _open_until: dict[str, datetime] = {}

    def __init__(self, proxy: Optional[str] = None, strict: bool = True):
        self._proxy = proxy
        self._strict = strict  # strict=True 时拦截非白名单 URL
        self._audit_log: list[SearchAuditRecord] = []

    @property
    def audit_log(self) -> list[SearchAuditRecord]:
        return list(self._audit_log)

    @staticmethod
    def _base_url(url: str) -> str:
        """提取通道标识 scheme://host[:port]（同主机不同路径/参数同一通道）。"""
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port and parsed.port not in (80, 443):
            base += f":{parsed.port}"
        return base

    @classmethod
    def _circuit_open(cls, url: str) -> Optional[datetime]:
        """若该 URL 所属通道熔断中，返回熔断截止时间；否则 None。"""
        base = cls._base_url(url)
        with cls._circuit_lock:
            until = cls._open_until.get(base)
            if until and datetime.now(timezone.utc) < until:
                return until
            if until:  # 冷却结束 → 半开，清态放行探测
                cls._open_until.pop(base, None)
                cls._failure_counts.pop(base, None)
        return None

    @classmethod
    def _record_failure(cls, url: str) -> None:
        base = cls._base_url(url)
        with cls._circuit_lock:
            count = cls._failure_counts.get(base, 0) + 1
            cls._failure_counts[base] = count
            if count >= SEARCH_FAILURE_THRESHOLD:
                cls._open_until[base] = datetime.now(timezone.utc) + timedelta(
                    seconds=SEARCH_COOLDOWN_SECONDS
                )
                logger.warning(
                    "SearchOps: circuit OPEN for %s after %d consecutive failures, "
                    "cooldown %ds", base, count, SEARCH_COOLDOWN_SECONDS,
                )

    @classmethod
    def _record_success(cls, url: str) -> None:
        base = cls._base_url(url)
        with cls._circuit_lock:
            cls._failure_counts.pop(base, None)
            cls._open_until.pop(base, None)

    @classmethod
    def reset_circuit(cls, url: Optional[str] = None) -> None:
        """运维/测试用：清除指定通道（None=全部）的熔断状态。"""
        with cls._circuit_lock:
            if url is None:
                cls._failure_counts.clear()
                cls._open_until.clear()
            else:
                base = cls._base_url(url)
                cls._failure_counts.pop(base, None)
                cls._open_until.pop(base, None)

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

        # ── 本地通道分流（local://）──────────────────────────────
        if query.url.startswith("local://"):
            return self._search_local(query)

        # ── 通道熔断检查 ────────────────────────────────────────
        open_until = self._circuit_open(query.url)
        if open_until is not None:
            self._audit_log.append(SearchAuditRecord(
                url=query.url,
                allowed=True,
                query=query.query,
                reason=f"circuit open until {open_until.isoformat()}",
            ))
            logger.warning(
                "SearchOps: short-circuit %s (circuit open until %s)",
                query.url, open_until.isoformat(),
            )
            return SearchResult(
                query=query.query,
                url=query.url,
                success=False,
                error=f"circuit open for {self._base_url(query.url)} until "
                      f"{open_until.isoformat()}",
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

            # 熔断计数清零
            self._record_success(query.url)

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
            # 累计连续失败，达阈值触发通道熔断
            self._record_failure(query.url)
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

    # ── local:// 本地搜索通道 ───────────────────────────────────────────────

    def _search_local(self, query: SearchQuery) -> SearchResult:
        """local://websearch — 经白名单执行本地 websearch.py（cn.bing 免费引擎）。

        与 HTTP 通道共享同一套熔断/审计路径；脚本由 argv 传查询词，
        无拼接注入面。脚本缺失/超时/解析为空均计通道失败（走熔断）。
        """
        # 熔断检查（与 HTTP 通道同一入口语义）
        open_until = self._circuit_open(query.url)
        if open_until is not None:
            self._audit_log.append(SearchAuditRecord(
                url=query.url, allowed=True, query=query.query,
                reason=f"circuit open until {open_until.isoformat()}",
            ))
            logger.warning("SearchOps: short-circuit %s (circuit open until %s)",
                           query.url, open_until.isoformat())
            return SearchResult(query=query.query, url=query.url, success=False,
                                error=f"circuit open for {self._base_url(query.url)} "
                                      f"until {open_until.isoformat()}")

        if not WEBSEARCH_SCRIPT.is_file():
            error = f"websearch script not found: {WEBSEARCH_SCRIPT}"
            self._record_failure(query.url)
            self._audit_log.append(SearchAuditRecord(
                url=query.url, allowed=True, query=query.query, reason=error))
            logger.error("SearchOps: %s", error)
            return SearchResult(query=query.query, url=query.url, success=False,
                                error=error)

        try:
            proc = subprocess.run(
                [sys.executable, str(WEBSEARCH_SCRIPT),
                 query.query, str(query.max_results)],
                capture_output=True, text=True,
                timeout=max(query.timeout, LOCAL_SEARCH_TIMEOUT_FLOOR),
            )
        except subprocess.TimeoutExpired:
            error = f"websearch script timeout after {max(query.timeout, LOCAL_SEARCH_TIMEOUT_FLOOR):.0f}s"
            self._record_failure(query.url)
            self._audit_log.append(SearchAuditRecord(
                url=query.url, allowed=True, query=query.query, reason=error))
            logger.error("SearchOps: %s", error)
            return SearchResult(query=query.query, url=query.url, success=False,
                                error=error)
        except Exception as e:
            self._record_failure(query.url)
            logger.error("SearchOps: local websearch failed: %s", e)
            return SearchResult(query=query.query, url=query.url, success=False,
                                error=str(e))

        out = proc.stdout or ""
        if proc.returncode != 0 or "search-failed" in out:
            first = next((ln for ln in out.splitlines()
                          if ln.strip()), proc.stderr.strip()[:200])
            self._record_failure(query.url)
            self._audit_log.append(SearchAuditRecord(
                url=query.url, allowed=True, query=query.query,
                reason=f"script failed: {first[:200]}"))
            logger.error("SearchOps: local websearch failed: %s", first[:200])
            return SearchResult(query=query.query, url=query.url, success=False,
                                error=f"websearch failed: {first[:200]}")

        results = self._parse_websearch_text(out, query.max_results)
        if not results:
            self._record_failure(query.url)
            self._audit_log.append(SearchAuditRecord(
                url=query.url, allowed=True, query=query.query,
                reason="websearch returned 0 parsed results"))
            logger.error("SearchOps: local websearch parsed 0 results")
            return SearchResult(query=query.query, url=query.url, success=False,
                                error="websearch returned 0 parsed results")

        self._record_success(query.url)
        self._audit_log.append(SearchAuditRecord(
            url=query.url, allowed=True, query=query.query,
            reason=f"ok ({len(results)} results via local websearch)"))
        return SearchResult(query=query.query, url=query.url, success=True,
                            status_code=proc.returncode, results=results)

    @staticmethod
    def _parse_websearch_text(text: str, max_results: int) -> list[dict[str, Any]]:
        """解析 websearch.py 文本输出（编号块: 标题 / URL / 摘要可选）。"""
        results: list[dict[str, Any]] = []
        blocks = re.split(r"(?m)^\d+\.\s", text)[1:]
        for b in blocks[:max_results]:
            lines = [ln.strip() for ln in b.strip().splitlines() if ln.strip()]
            if not lines:
                continue
            title = lines[0]
            url = lines[1] if len(lines) > 1 and lines[1].startswith("http") else ""
            body = " ".join(lines[2:]) if len(lines) > 2 else ""
            if not url and not body:
                continue
            results.append({"title": title[:200], "url": url, "body": body[:1000]})
        return results

    def get_history(self, limit: int = 20) -> list[SearchAuditRecord]:
        return self._audit_log[-limit:]

    def clear_history(self) -> None:
        self._audit_log.clear()
