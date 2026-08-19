"""Phase 29 — Gate Tests: search_ops。

验证:
  29-S01: search query within limit
  29-S02: search query too long
"""

from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.search_ops import search
from ocos.digital_world.base import SEARCH_QUERY_MAX_LEN


def _op(target: str, **params):
    return DigitalOperation.create("search", target, "G1", params=params)


def test_search_success():
    op = _op("OCOS architecture", query="OCOS architecture")
    result = search(op)
    assert result.status == "success"


def test_search_query_too_long():
    long_query = "X" * (SEARCH_QUERY_MAX_LEN + 1)
    op = _op(long_query)
    result = search(op)
    assert result.status == "rejected"
