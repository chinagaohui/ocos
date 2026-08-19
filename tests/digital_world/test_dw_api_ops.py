"""Phase 29 — Gate Tests: api_ops。

验证:
  29-A01: api_get whitelist
  29-A02: api_get not whitelist → rejected
  29-A03: api_post requires approval
  29-A04: rate limit
"""

import pytest
from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.api_ops import api_get, api_post, _request_timestamps


def _op(op_type: str, target: str, approval_id: str | None = None, **params):
    return DigitalOperation.create(op_type, target, "G1", params=params, approval_id=approval_id)


# ── 29-A01: api_get whitelist ─────────────────────────────────────

def test_api_get_allowed():
    op = _op("api_get", "https://api.github.com/repos/test")
    result = api_get(op)
    assert result.status == "success"


# ── 29-A02: api_get not whitelist ─────────────────────────────────

def test_api_get_not_whitelisted():
    op = _op("api_get", "http://evil.com/api")
    result = api_get(op)
    assert result.status == "rejected"


# ── 29-A03: api_post requires approval ───────────────────────────

def test_api_post_needs_approval():
    try:
        # DigitalOperation.create 会拒绝无 approval 的 api_post
        _op("api_post", "https://api.github.com/test")
        pytest.fail("should have raised")
    except ValueError:
        pass


def test_api_post_with_approval():
    op = _op("api_post", "https://api.github.com/test", approval_id="A1")
    result = api_post(op)
    assert result.status == "success"


# ── 29-A04: rate limit ────────────────────────────────────────────

def test_rate_limit():
    from ocos.digital_world.base import API_RATE_LIMIT_PER_MIN
    # 清理之前的请求记录
    for k in list(_request_timestamps.keys()):
        del _request_timestamps[k]
    # 不超过限制
    for _ in range(API_RATE_LIMIT_PER_MIN - 1):
        op = _op("api_get", "https://api.github.com/test")
        result = api_get(op)
        assert result.status == "success"
