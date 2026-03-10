from app.core.cache import cache_result, get_cached_result, get_cache_stats

def test_cache():
    question = "show me top 10 customers by revenue"
    database_id = "db_ecommerce"
    result = {
        "sql": "SELECT C1, C2 FROM T1 ORDER BY C5 DESC LIMIT 10",
        "rows": [{"C1": 1, "C2": "Alice"}]
    }

    # Test cache miss
    cached = get_cached_result(question, database_id)
    print(f"Cache miss: {cached is None} (expected True)")

    # Test cache store
    cache_result(question, database_id, result)
    print("Stored result in cache")

    # Test cache hit
    cached = get_cached_result(question, database_id)
    print(f"Cache hit: {cached is not None} (expected True)")
    print(f"Retrieved SQL: {cached['sql']}")

    # Test stats
    stats = get_cache_stats()
    print(f"Cache stats: {stats}")

if __name__ == "__main__":
    test_cache()
