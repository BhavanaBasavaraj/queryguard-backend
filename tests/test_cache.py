import unittest
from app.core.cache import (
    cache_result,
    get_cached_result,
    get_cache_stats,
    _make_cache_key,
)

class TestCache(unittest.TestCase):

    def test_cache_graceful_handling(self):
        question = "show me top 10 customers by revenue"
        database_id = "db_ecommerce"
        result = {
            "sql": "SELECT C1, C2 FROM T1 ORDER BY C5 DESC LIMIT 10",
            "rows": [{"C1": 1, "C2": "Alice"}]
        }

        # get_cached_result should return None on miss or connection error (fails open safely)
        cached = get_cached_result(question, database_id, "test_user")
        self.assertIn(cached, (None, result))

        # cache_result should not raise exception even if Redis is unreachable
        try:
            cache_result(question, database_id, "test_user", result)
        except Exception as e:
            self.fail(f"cache_result raised exception: {e}")

        # get_cache_stats returns a dict with 'connected' key
        stats = get_cache_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("connected", stats)

if __name__ == "__main__":
    unittest.main()


class TestCacheIsolation(unittest.TestCase):
    """Cached results are scoped to the user who asked.

    Without user_id in the key, two users asking the same question
    against the same database share one entry, so the second receives
    the first user's rows. This is a data leak, not a cache miss, so
    it is asserted directly rather than left to integration coverage.
    """

    def test_same_question_different_users_get_different_keys(self):
        a = _make_cache_key("show top customers", "db1", "user_a")
        b = _make_cache_key("show top customers", "db1", "user_b")
        self.assertNotEqual(a, b)

    def test_same_user_same_question_gets_same_key(self):
        a = _make_cache_key("show top customers", "db1", "user_a")
        b = _make_cache_key("show top customers", "db1", "user_a")
        self.assertEqual(a, b)

    def test_different_databases_get_different_keys(self):
        a = _make_cache_key("show top customers", "db1", "user_a")
        b = _make_cache_key("show top customers", "db2", "user_a")
        self.assertNotEqual(a, b)
