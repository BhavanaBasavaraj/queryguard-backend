import unittest
from app.core.validator import SQLValidator

class TestSQLValidator(unittest.TestCase):

    def setUp(self):
        self.validator = SQLValidator()

    def test_valid_select_query(self):
        passed, msg = self.validator.validate("SELECT C1, C2 FROM T1 LIMIT 10")
        self.assertTrue(passed, msg)

    def test_valid_cte_query(self):
        sql = "WITH summary AS (SELECT C1 FROM T1) SELECT * FROM summary LIMIT 5"
        passed, msg = self.validator.validate(sql)
        self.assertTrue(passed, msg)

    def test_leading_comment(self):
        sql = "-- Fetch user statistics\nSELECT C1 FROM T1 LIMIT 10"
        passed, msg = self.validator.validate(sql)
        self.assertTrue(passed, msg)

    def test_string_literal_with_keyword(self):
        # Searching for status = 'UPDATE' or 'DELETED' must not trigger false positive deny-list block
        sql = "SELECT C1 FROM T1 WHERE C2 = 'UPDATE' AND C3 = 'DELETED' LIMIT 10"
        passed, msg = self.validator.validate(sql)
        self.assertTrue(passed, msg)

    def test_string_literal_with_semicolon(self):
        sql = "SELECT C1 FROM T1 WHERE C2 = 'item1; item2' LIMIT 10"
        passed, msg = self.validator.validate(sql)
        self.assertTrue(passed, msg)

    def test_deny_drop_table(self):
        passed, _ = self.validator.validate("DROP TABLE T1")
        self.assertFalse(passed)

    def test_deny_missing_limit(self):
        passed, _ = self.validator.validate("SELECT * FROM T1")
        self.assertFalse(passed)

    def test_deny_excessive_limit(self):
        passed, _ = self.validator.validate("SELECT * FROM T1 LIMIT 99999")
        self.assertFalse(passed)

    def test_deny_multiple_statements(self):
        passed, _ = self.validator.validate("SELECT * FROM T1; DROP TABLE T1; LIMIT 10")
        self.assertFalse(passed)

    def test_deny_delete_statement(self):
        passed, _ = self.validator.validate("DELETE FROM T1 WHERE C1 = 1 LIMIT 10")
        self.assertFalse(passed)

if __name__ == "__main__":
    unittest.main()

