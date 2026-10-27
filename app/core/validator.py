import re

DENY_LIST = [
    "DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE", "EXEC"
]

def _strip_comments_and_literals(sql: str) -> tuple[str, str]:
    # Strip block comments /* ... */
    clean_sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # Strip line comments -- ...
    clean_sql = re.sub(r'--.*$', '', clean_sql, flags=re.MULTILINE)
    clean_sql = clean_sql.strip()

    # Mask single-quoted and double-quoted string literals for safety checks
    masked_sql = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", clean_sql)
    masked_sql = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', masked_sql)

    return clean_sql, masked_sql

class SQLValidator:

    def validate(self, sql: str) -> tuple[bool, str]:
        if not sql or not sql.strip():
            return False, "Query cannot be empty"

        clean_sql, masked_sql = _strip_comments_and_literals(sql)
        sql_upper = masked_sql.upper().strip()

        # Check 1: Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Only SELECT statements are allowed"

        # Check 2: Deny list check against masked SQL (string values like 'UPDATE' won't trigger false positives)
        for keyword in DENY_LIST:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return False, f"Forbidden keyword detected: {keyword}"

        # Check 3: Must have LIMIT
        if "LIMIT" not in sql_upper:
            return False, "Query must include a LIMIT clause"

        # Check 4: LIMIT must be a number within bounds.
        # Requiring the match, rather than skipping when it is absent, is
        # deliberate: "LIMIT ALL" is valid PostgreSQL meaning no limit, and
        # a permissive `if limit_match:` lets it through check 3 and skips
        # this check entirely.
        limit_match = re.search(r'\bLIMIT\s+(\S+)', sql_upper)
        if not limit_match:
            return False, "LIMIT clause must specify a row count"
        limit_token = limit_match.group(1).rstrip(';')
        if not limit_token.isdigit():
            return False, f"LIMIT must be a number, got {limit_token}"
        limit_value = int(limit_token)
        if limit_value > 10000:
            return False, f"LIMIT cannot exceed 10000 rows, got {limit_value}"

        # Check 5: No semicolons except at the end (prevents multiple statements)
        sql_without_end = masked_sql.strip().rstrip(';')
        if ';' in sql_without_end:
            return False, "Multiple SQL statements are not allowed"

        return True, "Valid"

