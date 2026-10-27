import io
import logging
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core import providers

from app.main import app

class TestDeveloperExperience(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_error_contract_shape(self):
        # 1. Invalid prompt -> HTTP 400
        payload = {
            "question": "   ",
            "database_id": "db_ecommerce",
            "user_id": "user_test"
        }
        response = self.client.post("/query", json=payload)
        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertIn("code", data)
        self.assertIn("message", data)
        self.assertIn("request_id", data)
        self.assertEqual(data["code"], "INVALID_QUERY")
        self.assertIn("X-Request-ID", response.headers)
        self.assertEqual(response.headers["X-Request-ID"], data["request_id"])

    @patch("app.api.query.llm_router.generate_sql")
    def test_sql_validation_error_status_502(self, mock_llm):
        # 2. Rejection by validator -> HTTP 502 Bad Gateway
        mock_llm.return_value = ("SELECT * FROM T1; DROP TABLE T1; LIMIT 5", providers.GEMINI)

        payload = {
            "question": "Drop tables if exists",
            "database_id": "db_ecommerce",
            "user_id": "user_test"
        }
        response = self.client.post("/query", json=payload)
        self.assertEqual(response.status_code, 502)

        data = response.json()
        self.assertEqual(data["code"], "SQL_VALIDATION_FAILED")
        self.assertEqual(data["message"], "Generated query failed safety validation")
        self.assertIn("request_id", data)



    def test_inbound_request_id_reuse(self):
        custom_id = "11111111-2222-3333-4444-555555555555"
        headers = {"X-Request-ID": custom_id}

        response = self.client.get("/health", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), custom_id)

        # On error response
        payload = {"question": "", "database_id": "db1", "user_id": "u1"}
        error_resp = self.client.post("/query", json=payload, headers=headers)
        self.assertEqual(error_resp.headers.get("X-Request-ID"), custom_id)
        self.assertEqual(error_resp.json()["request_id"], custom_id)

    @patch("app.api.query.validator.validate")
    @patch("app.api.query.llm_router.generate_sql")
    def test_zero_exfiltration_in_error_body_and_logs(self, mock_llm, mock_val):
        # Mock LLM and validator to simulate a non-keyword validation failure whose reason includes real schema identifiers
        mock_llm.return_value = ("SELECT T1.C1 FROM T1 LIMIT 99999", providers.GEMINI)
        mock_val.return_value = (False, "Table 'customers' column 'revenue' exceeds max query limit of 10000 rows, got 99999")

        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger("queryguard")
        logger.addHandler(handler)

        try:
            payload = {
                "question": "show excessive rows for revenue",
                "database_id": "db_ecommerce",
                "user_id": "user_test"
            }
            response = self.client.post("/query", json=payload)
            self.assertEqual(response.status_code, 502)

            resp_str = response.text
            log_str = log_capture.getvalue()

            # 1. Assert response body is fixed and contains ZERO detail from validator reason
            data = response.json()
            self.assertEqual(data["code"], "SQL_VALIDATION_FAILED")
            self.assertEqual(data["message"], "Generated query failed safety validation")

            # 2. Assert real identifiers appear in log output but NOT in client response body
            real_identifiers = ["revenue", "customers"]
            for identifier in real_identifiers:
                self.assertNotIn(identifier, resp_str, f"Real identifier '{identifier}' leaked in client error body!")
                self.assertIn(identifier, log_str, f"Real identifier '{identifier}' missing from server log!")

        finally:
            logger.removeHandler(handler)


    @patch("app.api.query.execute_query")
    @patch("app.api.query.llm_router.generate_sql")
    @patch("app.api.query.get_cached_result")
    def test_redis_offline_resilience(self, mock_cache_get, mock_llm, mock_execute):
        # Cache lookup fails / returns None
        mock_cache_get.return_value = None
        mock_llm.return_value = ("SELECT T1.C1 FROM T1 LIMIT 5", providers.GEMINI)
        mock_execute.return_value = [{"id": 1}]

        payload = {
            "question": "show me customers",
            "database_id": "db_ecommerce",
            "user_id": "user_test"
        }
        response = self.client.post("/query", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertFalse(data["cache_hit"])
        self.assertEqual(data["message"], "Query processed successfully")

if __name__ == "__main__":
    unittest.main()
