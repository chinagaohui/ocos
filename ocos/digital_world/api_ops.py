"""Phase 21/29 — API 操作: api_get / api_post。

约束:
  - URL 白名单 (API_WHITELIST, 冻结基线)
  - 速率限制 60/min
  - POST 需审批
  - dry_run 模式 (OCOS_DW_DRY_RUN=1) 返回模拟结果，测试和生产可切换

生产模式: OCOS_DW_DRY_RUN=0 时使用 urllib.request 执行真实 HTTP 调用。
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from collections import defaultdict

from ocos.digital_world.base import DigitalOperation, OperationResult, API_RATE_LIMIT_PER_MIN

API_WHITELIST: tuple[str, ...] = (
    "https://api.github.com/",
    "https://api.openai.com/",
    "https://api.anthropic.com/",
)

# ── dry_run gate ──
_DRY_RUN = os.getenv("OCOS_DW_DRY_RUN", "1") == "1"

# 简易速率限制器
_request_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(target: str) -> bool:
    now = time.monotonic()
    window = 60.0
    key = target.split("/")[2] if "//" in target else target  # hostname
    timestamps = _request_timestamps[key]
    # 清理过期时间戳
    _request_timestamps[key] = [t for t in timestamps if now - t < window]
    return len(_request_timestamps[key]) < API_RATE_LIMIT_PER_MIN


def _record_request(target: str) -> None:
    key = target.split("/")[2] if "//" in target else target
    _request_timestamps[key].append(time.monotonic())


def _is_api_allowed(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in API_WHITELIST)


def _real_http_get(url: str, timeout: int = 10) -> tuple[int, str]:
    """使用 urllib 执行真实 GET 请求。返回 (status_code, body)。"""
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "OCOS-DigitalWorld/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body[:2000]  # 截断响应体
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


def _real_http_post(url: str, payload: str, timeout: int = 10) -> tuple[int, str]:
    """使用 urllib 执行真实 POST 请求。"""
    data = payload.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OCOS-DigitalWorld/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body[:2000]
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


# ── 公开操作函数 ──


def api_get(op: DigitalOperation) -> OperationResult:
    """GET 请求。dry_run 时返回模拟结果，否则执行真实 HTTP GET。"""
    start = time.monotonic()

    if not _is_api_allowed(op.target):
        return OperationResult.rejected(op.op_id, "API not in whitelist")

    if not _check_rate_limit(op.target):
        return OperationResult.rejected(op.op_id, "rate limit exceeded")

    _record_request(op.target)

    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id, f"GET {op.target} → 200 OK (simulated)", duration_ms,
        )

    # 真实 HTTP GET
    status, body = _real_http_get(op.target)
    duration_ms = int((time.monotonic() - start) * 1000)
    if 200 <= status < 300:
        return OperationResult.success(
            op.op_id, f"GET {op.target} → {status} OK\n{body[:500]}", duration_ms,
        )
    return OperationResult.failure(
        op.op_id, f"GET {op.target} → {status}: {body[:200]}", duration_ms,
    )


def api_post(op: DigitalOperation) -> OperationResult:
    """POST 请求（需审批）。dry_run 时返回模拟结果，否则执行真实 HTTP POST。"""
    start = time.monotonic()

    if not _is_api_allowed(op.target):
        return OperationResult.rejected(op.op_id, "API not in whitelist")

    if not _check_rate_limit(op.target):
        return OperationResult.rejected(op.op_id, "rate limit exceeded")

    _record_request(op.target)

    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id, f"POST {op.target} → 201 Created (simulated)", duration_ms,
        )

    # 真实 HTTP POST
    payload = json.dumps(op.params or {})
    status, body = _real_http_post(op.target, payload)
    duration_ms = int((time.monotonic() - start) * 1000)
    if 200 <= status < 300:
        return OperationResult.success(
            op.op_id, f"POST {op.target} → {status} Created\n{body[:500]}", duration_ms,
        )
    return OperationResult.failure(
        op.op_id, f"POST {op.target} → {status}: {body[:200]}", duration_ms,
    )
