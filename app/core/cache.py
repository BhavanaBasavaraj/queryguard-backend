import redis
import json
import hashlib
from app.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

CACHE_TTL = 3600  # 1 hour in seconds

def _make_cache_key(question: str, database_id: str, user_id: str) -> str:
    raw_key = f"query:{question.lower().strip()}:{database_id}:{user_id}"
    hashed = hashlib.md5(raw_key.encode()).hexdigest()
    return f"queryguard:{hashed}"

def get_cached_result(question: str, database_id: str, user_id: str) -> dict | None:
    key = _make_cache_key(question, database_id, user_id)
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def cache_result(question: str, database_id: str, user_id: str, result: dict) -> None:
    key = _make_cache_key(question, database_id, user_id)
    redis_client.setex(
        name=key,
        time=CACHE_TTL,
        value=json.dumps(result)
    )

def invalidate_cache(question: str, database_id: str, user_id: str) -> None:
    key = _make_cache_key(question, database_id, user_id)
    redis_client.delete(key)

def get_cache_stats() -> dict:
    info = redis_client.info()
    return {
        "connected": True,
        "used_memory": info.get("used_memory_human"),
        "total_keys": redis_client.dbsize(),
        "hits": info.get("keyspace_hits", 0),
        "misses": info.get("keyspace_misses", 0)
    }
