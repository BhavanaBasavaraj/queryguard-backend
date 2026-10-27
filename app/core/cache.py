import redis
import json
import hashlib
import logging
from app.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

CACHE_TTL = 3600  # 1 hour in seconds

def _make_cache_key(question: str, database_id: str, user_id: str) -> str:
    """Build the cache key.

    user_id is part of the key because results are scoped to the user
    who asked. Without it, two users asking the same question against
    the same database share one entry, and the second receives the
    first user's rows.
    """
    raw_key = f"query:{question.lower().strip()}:{database_id}:{user_id}"
    hashed = hashlib.md5(raw_key.encode()).hexdigest()
    return f"queryguard:{hashed}"

def get_cached_result(question: str, database_id: str, user_id: str) -> dict | None:
    try:
        key = _make_cache_key(question, database_id, user_id)
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache lookup failed (failing open): {e}")
    return None

def cache_result(question: str, database_id: str, user_id: str, result: dict) -> None:
    try:
        key = _make_cache_key(question, database_id, user_id)
        redis_client.setex(
            name=key,
            time=CACHE_TTL,
            value=json.dumps(result)
        )
    except Exception as e:
        logger.warning(f"Redis cache store failed: {e}")

def invalidate_cache(question: str, database_id: str, user_id: str) -> None:
    try:
        key = _make_cache_key(question, database_id, user_id)
        redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Redis cache invalidation failed: {e}")

def get_cache_stats() -> dict:
    try:
        info = redis_client.info()
        return {
            "connected": True,
            "used_memory": info.get("used_memory_human"),
            "total_keys": redis_client.dbsize(),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0)
        }
    except Exception as e:
        logger.warning(f"Redis stats fetch failed: {e}")
        return {
            "connected": False,
            "error": str(e)
        }

