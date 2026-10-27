import unittest
from app.core.privacy_proxy import PrivacyProxy

class TestPrivacyProxy(unittest.TestCase):

    def setUp(self):
        self.proxy = PrivacyProxy(database_id="test_db")
        self.schema = {
            "users": ["id", "email", "ssn", "full_name"],
            "orders": ["id", "user_id", "total", "created_at"],
            "products": ["id", "name", "price", "category", "stock"]
        }

    def test_anonymize_schema(self):
        anonymized = self.proxy.anonymize_schema(self.schema)

        # Check table mapping
        self.assertIn("T1", anonymized)
        self.assertIn("T2", anonymized)
        self.assertIn("T3", anonymized)

        # Check column anonymization count
        self.assertEqual(len(anonymized["T1"]), 4)
        self.assertEqual(len(anonymized["T2"]), 4)

    def test_subtoken_deanonymize(self):
        self.proxy.anonymize_schema(self.schema)

        # C1 is users.id, C10 is products.category
        # SQL with literal numbers (e.g. C1 = 10) must NOT replace C1 inside C10
        anon_sql = "SELECT T1.C1 FROM T1 WHERE T1.C1 = 10 LIMIT 10"
        real_sql = self.proxy.deanonymize_sql(anon_sql)

        self.assertEqual(real_sql, "SELECT users.id FROM users WHERE users.id = 10 LIMIT 10")

    def test_table_and_column_name_collision(self):
        # Schema where a table name is also used as a column name elsewhere
        collision_schema = {
            "order": ["id", "user_id", "total"],
            "items": ["id", "order", "item_name"]
        }
        anon_schema = self.proxy.anonymize_schema(collision_schema)

        # "order" table becomes T1, "order" column in items becomes C_something (not T1)
        self.assertIn("T1", anon_schema)
        items_cols = anon_schema["T2"]
        self.assertNotIn("T1", items_cols)

if __name__ == "__main__":
    unittest.main()

