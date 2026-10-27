class QueryGuardException(Exception):
    """Base exception for QueryGuard API errors."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class InvalidQueryError(QueryGuardException):
    """Raised when caller's request prompt is empty or malformed (HTTP 400)."""
    def __init__(self, message: str = "Natural language question prompt is invalid or empty"):
        super().__init__(
            code="INVALID_QUERY",
            message=message,
            status_code=400
        )

class SQLValidationError(QueryGuardException):
    """Raised when LLM-generated SQL fails security validation (HTTP 502 Bad Gateway)."""
    def __init__(self, message: str = "Generated query failed safety validation"):
        super().__init__(
            code="SQL_VALIDATION_FAILED",
            message=message,
            status_code=502
        )

class LLMProviderError(QueryGuardException):
    """Raised when all upstream LLM providers fail or time out (HTTP 502 Bad Gateway)."""
    def __init__(self, message: str = "Upstream AI provider failed to generate a query"):
        super().__init__(
            code="LLM_PROVIDER_FAILURE",
            message=message,
            status_code=502
        )

class DatabaseExecutionError(QueryGuardException):
    """Raised when database query execution fails (HTTP 500 Internal Server Error)."""
    def __init__(self, message: str = "Database query execution failed"):
        super().__init__(
            code="DATABASE_EXECUTION_ERROR",
            message=message,
            status_code=500
        )
