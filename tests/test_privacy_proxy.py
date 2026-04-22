import pytest
from app.core.privacy_proxy import PrivacyProxy


SCHEMA = {
    "users": ["id", "email", "ssn", "full_name"],
    "orders": ["id", "user_id", "total", "created_at"],
    "credit_cards": ["id", "user_id", "card_number", "expiry"],
}


def test_anonymize_schema_table_names():
    proxy = PrivacyProxy(database_id="test_db")
    anon = proxy.anonymize_schema(SCHEMA)
    assert set(anon.keys()) == {"T1", "T2", "T3"}


def test_anonymize_schema_column_names():
    proxy = PrivacyProxy(database_id="test_db")
    anon = proxy.anonymize_schema(SCHEMA)
    for table, cols in anon.items():
        for col in cols:
            assert col.startswith("C"), f"Expected Cn column, got {col}"


def test_anonymize_schema_column_count():
    proxy = PrivacyProxy(database_id="test_db")
    anon = proxy.anonymize_schema(SCHEMA)
    assert len(anon["T1"]) == 4
    assert len(anon["T2"]) == 4
    assert len(anon["T3"]) == 4


def test_deanonymize_sql_basic():
    proxy = PrivacyProxy(database_id="test_db")
    proxy.anonymize_schema(SCHEMA)
    anon_sql = "SELECT T1.C1, T1.C2 FROM T1 LIMIT 10"
    real_sql = proxy.deanonymize_sql(anon_sql)
    assert "users" in real_sql
    assert "id" in real_sql
    assert "email" in real_sql
    assert "T1" not in real_sql
    assert "C1" not in real_sql


def test_deanonymize_sql_case_insensitive():
    proxy = PrivacyProxy(database_id="test_db")
    proxy.anonymize_schema(SCHEMA)
    anon_sql = "select t1.c1, t1.c2 from t1 limit 10"
    real_sql = proxy.deanonymize_sql(anon_sql)
    assert "users" in real_sql
    assert "id" in real_sql
    assert "email" in real_sql


def test_forward_mapping_correctness():
    proxy = PrivacyProxy(database_id="test_db")
    proxy.anonymize_schema(SCHEMA)
    fwd = proxy.get_forward_mapping()
    assert fwd["users"] == "T1"
    assert fwd["orders"] == "T2"
    assert fwd["credit_cards"] == "T3"


def test_reverse_mapping_correctness():
    proxy = PrivacyProxy(database_id="test_db")
    proxy.anonymize_schema(SCHEMA)
    rev = proxy.get_reverse_mapping()
    assert rev["T1"] == "users"
    assert rev["T2"] == "orders"
    assert rev["T3"] == "credit_cards"


def test_deterministic_mapping():
    proxy1 = PrivacyProxy(database_id="test_db")
    proxy2 = PrivacyProxy(database_id="test_db")
    anon1 = proxy1.anonymize_schema(SCHEMA)
    anon2 = proxy2.anonymize_schema(SCHEMA)
    assert anon1 == anon2
