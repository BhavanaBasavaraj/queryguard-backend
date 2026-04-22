import pytest
from unittest.mock import patch, MagicMock
from app.core.cache import cache_result, get_cached_result, get_cache_stats, _make_cache_key


QUESTION = "show me top 10 customers by revenue"
DATABASE_ID = "db_ecommerce"
USER_ID = "user_123"
RESULT = {
    "sql": "SELECT C1, C2 FROM T1 ORDER BY C5 DESC LIMIT 10",
    "rows": [{"C1": 1, "C2": "Alice"}]
}


def test_cache_key_includes_user_id():
    key1 = _make_cache_key(QUESTION, DATABASE_ID, "user_a")
    key2 = _make_cache_key(QUESTION, DATABASE_ID, "user_b")
    assert key1 != key2


def test_cache_key_case_insensitive_question():
    key1 = _make_cache_key(QUESTION.upper(), DATABASE_ID, USER_ID)
    key2 = _make_cache_key(QUESTION.lower(), DATABASE_ID, USER_ID)
    assert key1 == key2


@patch("app.core.cache.redis_client")
def test_cache_miss_returns_none(mock_redis):
    mock_redis.get.return_value = None
    result = get_cached_result(QUESTION, DATABASE_ID, USER_ID)
    assert result is None


@patch("app.core.cache.redis_client")
def test_cache_hit_returns_result(mock_redis):
    import json
    mock_redis.get.return_value = json.dumps(RESULT)
    result = get_cached_result(QUESTION, DATABASE_ID, USER_ID)
    assert result == RESULT


@patch("app.core.cache.redis_client")
def test_cache_result_calls_setex(mock_redis):
    cache_result(QUESTION, DATABASE_ID, USER_ID, RESULT)
    assert mock_redis.setex.called
    call_kwargs = mock_redis.setex.call_args
    assert call_kwargs is not None


@patch("app.core.cache.redis_client")
def test_get_cache_stats(mock_redis):
    mock_redis.info.return_value = {
        "used_memory_human": "1.5M",
        "keyspace_hits": 10,
        "keyspace_misses": 2,
    }
    mock_redis.dbsize.return_value = 5
    stats = get_cache_stats()
    assert stats["connected"] is True
    assert stats["total_keys"] == 5
    assert stats["hits"] == 10
    assert stats["misses"] == 2
