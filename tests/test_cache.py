import unittest
from app.core.cache import cache_result, get_cached_result, get_cache_stats

class TestCache(unittest.TestCase):

    def test_cache_graceful_handling(self):
        question = "show me top 10 customers by revenue"
        database_id = "db_ecommerce"
        result = {
            "sql": "SELECT C1, C2 FROM T1 ORDER BY C5 DESC LIMIT 10",
            "rows": [{"C1": 1, "C2": "Alice"}]
        }

        # get_cached_result should return None on miss or connection error (fails open safely)
        cached = get_cached_result(question, database_id)
        self.assertIn(cached, (None, result))

        # cache_result should not raise exception even if Redis is unreachable
        try:
            cache_result(question, database_id, result)
        except Exception as e:
            self.fail(f"cache_result raised exception: {e}")

        # get_cache_stats returns a dict with 'connected' key
        stats = get_cache_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("connected", stats)

if __name__ == "__main__":
    unittest.main()

