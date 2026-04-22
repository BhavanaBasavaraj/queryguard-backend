import pytest
from app.core.validator import SQLValidator

validator = SQLValidator()


def test_valid_select_with_limit():
    passed, message = validator.validate("SELECT C1, C2 FROM T1 LIMIT 10")
    assert passed is True


def test_drop_table_rejected():
    passed, message = validator.validate("DROP TABLE T1")
    assert passed is False
    assert "SELECT" in message or "Forbidden" in message


def test_select_without_limit_rejected():
    passed, message = validator.validate("SELECT * FROM T1")
    assert passed is False
    assert "LIMIT" in message


def test_multiple_statements_rejected():
    passed, message = validator.validate("SELECT * FROM T1; DROP TABLE T1; LIMIT 10")
    assert passed is False


def test_delete_rejected():
    passed, message = validator.validate("DELETE FROM T1 WHERE C1 = 1 LIMIT 10")
    assert passed is False
    assert "Forbidden" in message or "SELECT" in message


def test_limit_exceeding_max_rejected():
    passed, message = validator.validate("SELECT * FROM T1 LIMIT 99999")
    assert passed is False
    assert "10000" in message


def test_limit_at_max_allowed():
    passed, message = validator.validate("SELECT * FROM T1 LIMIT 10000")
    assert passed is True


def test_limit_all_rejected():
    passed, message = validator.validate("SELECT * FROM T1 LIMIT ALL")
    assert passed is False
    assert "numeric" in message.lower()


def test_case_insensitive_deny_list():
    passed, message = validator.validate("select * from t1 where 1=1; drop table t1 limit 10")
    assert passed is False


def test_deny_list_update():
    passed, message = validator.validate("UPDATE T1 SET C1 = 1 LIMIT 10")
    assert passed is False
