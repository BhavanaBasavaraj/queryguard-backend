from app.core.validator import SQLValidator

validator = SQLValidator()

tests = [
    ("SELECT C1, C2 FROM T1 LIMIT 10", True),
    ("DROP TABLE T1", False),
    ("SELECT * FROM T1", False),
    ("SELECT * FROM T1; DROP TABLE T1; LIMIT 10", False),
    ("DELETE FROM T1 WHERE C1 = 1 LIMIT 10", False),
    ("SELECT * FROM T1 LIMIT 99999", False),
]

for sql, expected in tests:
    passed, message = validator.validate(sql)
    status = "✅ PASS" if passed == expected else "❌ FAIL"
    print(f"{status} | Expected:{expected} Got:{passed} | {message} | SQL: {sql[:50]}")
