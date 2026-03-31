"""Tests for app/store/cache.py — Redis cache layer.

Run: pytest tests/test_cache.py -v

These tests mock the Redis client so no running Redis is required.
The key behaviors:
  - Cache miss → db_fn() is called, result cached
  - Cache hit → db_fn() is NOT called
  - invalidate() deletes only the target key
  - Redis DOWN → db_fn() is called, no exception raised
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock(get_return=None, ping_raises=False):
    mock = MagicMock()
    if ping_raises:
        mock.ping.side_effect = Exception("Redis connection refused")
    else:
        mock.ping.return_value = True
    mock.get.return_value = get_return
    return mock


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------

def test_cache_miss_calls_db_fn():
    """Redis DOWN (ping fails) → db_fn() is called, result returned, no exception."""
    import app.store.cache as cache_module

    # Reset pool so it will be re-initialized
    cache_module._redis_pool = None

    def db_fn():
        return {"Energy": 1.5, "Finance": 0.8}

    with patch("app.store.cache._get_redis", return_value=None):
        result = cache_module.get_cached("heatmap:v1", ttl=30, db_fn=db_fn)

    assert result == {"Energy": 1.5, "Finance": 0.8}


def test_cache_miss_on_key_calls_db_fn():
    """Redis UP but key not found → db_fn() is called and result is cached."""
    import json
    import app.store.cache as cache_module

    mock_redis = _make_redis_mock(get_return=None)
    db_calls = []

    def db_fn():
        db_calls.append(1)
        return [{"title": "test", "total_score": 0.9}]

    with patch("app.store.cache._get_redis", return_value=mock_redis):
        result = cache_module.get_cached("timeline:v1:50", ttl=15, db_fn=db_fn)

    assert len(db_calls) == 1
    assert result[0]["title"] == "test"
    mock_redis.setex.assert_called_once()


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

def test_cache_hit_skips_db_fn():
    """Redis GET returns cached value → db_fn() is NOT called."""
    import json
    import app.store.cache as cache_module

    cached_value = {"Energy": 2.1}
    mock_redis = _make_redis_mock(get_return=json.dumps(cached_value))
    db_calls = []

    def db_fn():
        db_calls.append(1)
        return {"Energy": 999.0}  # should never be returned

    with patch("app.store.cache._get_redis", return_value=mock_redis):
        result = cache_module.get_cached("heatmap:v1", ttl=30, db_fn=db_fn)

    assert result == cached_value
    assert len(db_calls) == 0


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------

def test_invalidate_deletes_key():
    """invalidate('key') calls redis.delete('key') once."""
    import app.store.cache as cache_module

    mock_redis = _make_redis_mock()

    with patch("app.store.cache._get_redis", return_value=mock_redis):
        cache_module.invalidate("heatmap:v1")

    mock_redis.delete.assert_called_once_with("heatmap:v1")


def test_invalidate_does_not_delete_other_keys():
    """invalidate('key-A') does not touch 'key-B'."""
    import app.store.cache as cache_module

    mock_redis = _make_redis_mock()

    with patch("app.store.cache._get_redis", return_value=mock_redis):
        cache_module.invalidate("heatmap:v1")

    calls = [call.args[0] for call in mock_redis.delete.call_args_list]
    assert "timeline:v1:50" not in calls


def test_invalidate_pipeline_caches_hits_all_keys():
    """invalidate_pipeline_caches() calls delete for all 3 known keys."""
    import app.store.cache as cache_module

    mock_redis = _make_redis_mock()

    with patch("app.store.cache._get_redis", return_value=mock_redis):
        cache_module.invalidate_pipeline_caches()

    deleted_keys = {call.args[0] for call in mock_redis.delete.call_args_list}
    assert deleted_keys == {"heatmap:v1", "timeline:v1:50", "timeline:v1:20"}


# ---------------------------------------------------------------------------
# Redis unavailable — no exception propagated
# ---------------------------------------------------------------------------

def test_get_cached_redis_down_no_exception():
    """Redis completely unavailable → get_cached() returns db_fn() result without raising."""
    import app.store.cache as cache_module

    with patch("app.store.cache._get_redis", return_value=None):
        result = cache_module.get_cached("any:key", ttl=10, db_fn=lambda: 42)

    assert result == 42


def test_invalidate_redis_down_no_exception():
    """invalidate() with Redis down → no exception raised."""
    import app.store.cache as cache_module

    with patch("app.store.cache._get_redis", return_value=None):
        cache_module.invalidate("heatmap:v1")  # should not raise
