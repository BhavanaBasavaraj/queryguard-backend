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

    @patch("app.api.query.execute_query")
    @patch("app.api.query.llm_router.generate_sql")
    def test_full_query_pipeline(self, mock_llm, mock_execute):
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

if __name__ == "__main__":
    unittest.main()
