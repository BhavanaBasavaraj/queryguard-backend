import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core import providers

from app.main import app

class TestIntegrationAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertEqual(response.json()["app"], "QueryGuard")

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "QueryGuard API is running")

    # The cache is patched to miss. Without this the test depends on
    # whatever Redis happens to hold: a warm cache short-circuits the
    # request and the mocked router is never called. It passed for
    # months only because Redis was unreachable and the cache failed open.
    @patch("app.api.query.get_cached_result", return_value=None)
    @patch("app.api.query.execute_query")
    @patch("app.api.query.llm_router.generate_sql")
    def test_full_query_pipeline(self, mock_llm, mock_execute, mock_cache):
        # 1. LLM returns anonymized SQL with table T1 and columns C1, C2, C4
        mock_llm.return_value = (
            "SELECT T1.C1, T1.C2 FROM T1 ORDER BY T1.C4 DESC LIMIT 2",
            providers.GEMINI
        )

        # 2. Database returns mock row results
        mock_execute.return_value = [
            {"id": 101, "name": "Alice", "revenue": 15000.0},
            {"id": 102, "name": "Bob", "revenue": 12000.0}
        ]

        payload = {
            "question": "Show top 2 customers by revenue",
            "database_id": "db_ecommerce",
            "user_id": "user_456"
        }

        response = self.client.post("/query", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check response contract
        self.assertIn("query_id", data)
        self.assertEqual(
            data["sql_generated"],
            "SELECT customers.id, customers.name FROM customers ORDER BY customers.revenue DESC LIMIT 2"
        )
        self.assertEqual(data["rows_returned"], 2)
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["name"], "Alice")
        self.assertEqual(data["llm_provider"], providers.GEMINI)
        self.assertEqual(data["message"], "Query processed successfully")

    # Regression test for the schema leak: the anonymized schema and hints
    # are what the LLM receives. They must never contain a real table name,
    # or the anonymization is undone in the same prompt that applies it.
    @patch("app.api.query.get_cached_result", return_value=None)
    @patch("app.api.query.execute_query", return_value=[])
    @patch("app.api.query.llm_router.generate_sql")
    def test_llm_input_contains_no_real_table_names(self, mock_llm, mock_execute, mock_cache):
        import json
        import re
        from app.api.query import SAMPLE_SCHEMA

        mock_llm.return_value = ("SELECT T1.C1 FROM T1 LIMIT 1", providers.GEMINI)
        resp = self.client.post("/query", json={
            "question": "show customers",
            "database_id": "db_ecommerce",
            "user_id": "user_leak_test",
        })
        self.assertEqual(resp.status_code, 200)

        kwargs = mock_llm.call_args.kwargs
        sent = json.dumps([kwargs["anonymized_schema"], kwargs["schema_hints"]])
        for table in SAMPLE_SCHEMA:
            self.assertIsNone(
                re.search(r"\b" + re.escape(table) + r"\b", sent, re.IGNORECASE),
                f"Real table name '{table}' reached the LLM input: {sent}",
            )

if __name__ == "__main__":
    unittest.main()


class TestCachePath(unittest.TestCase):
    """The cache-hit branch returns a different message and skips the model.

    Untested until now, which is why a warm Redis silently broke
    test_full_query_pipeline instead of failing a test of its own.
    """

    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.query.llm_router.generate_sql")
    @patch("app.api.query.get_cached_result")
    def test_cache_hit_skips_the_model(self, mock_cache, mock_llm):
        mock_cache.return_value = {
            "query_id": "cached-id",
            "sql_generated": "SELECT customers.id FROM customers LIMIT 1",
            "results": [{"id": 101}],
            "rows_returned": 1,
            "llm_provider": providers.GEMINI,
        }

        r = self.client.post("/query", json={
            "question": "anything",
            "database_id": "db1",
            "user_id": "user_cache",
        })

        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["cache_hit"])
        self.assertEqual(data["message"], "Result served from cache")
        mock_llm.assert_not_called()
