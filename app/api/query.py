import time
import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.privacy_proxy import PrivacyProxy
from app.core.llm_router import LLMRouter
from app.core.validator import SQLValidator
from app.core.executor import execute_query
from app.core.cache import get_cached_result, cache_result
from app.utils.audit import log_query
from app.core.exceptions import (
    QueryGuardException,
    InvalidQueryError,
    SQLValidationError,
    LLMProviderError,
    DatabaseExecutionError
)

logger = logging.getLogger("queryguard")

router = APIRouter()
llm_router = LLMRouter()
validator = SQLValidator()


SAMPLE_SCHEMA = {
    "customers": ["id", "name", "email", "revenue", "created_at"],
    "orders": ["id", "customer_id", "total", "status", "created_at"],
    "products": ["id", "name", "price", "category", "stock"]
}

COLUMN_HINTS = {
    "customers": {
        "id": "unique identifier (integer)",
        "name": "person name (text)",
        "email": "email address (text)",
        "revenue": "total revenue amount (numeric)",
        "created_at": "record creation timestamp"
    },
    "orders": {
        "id": "unique identifier (integer)",
        "customer_id": "reference to customer (integer)",
        "total": "order total amount (numeric)",
        "status": "order status text: completed/pending/cancelled",
        "created_at": "order timestamp"
    },
    "products": {
        "id": "unique identifier (integer)",
        "name": "product name (text)",
        "price": "product price (numeric)",
        "category": "product category text: Electronics/Furniture/Appliances",
        "stock": "available stock quantity (integer)"
    }
}

class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        description="Natural language question to query the database",
        example="Show top 5 customers by revenue"
    )
    database_id: str = Field(
        ...,
        description="Target database connection identifier",
        example="db_ecommerce"
    )
    user_id: str = Field(
        ...,
        description="Authenticated user identifier",
        example="user_123"
    )

class QueryResponse(BaseModel):
    query_id: str = Field(..., description="Unique audit query identifier", example="8f3b2d10-410a-4ca1-aaed-08d75620f30d")
    sql_generated: str = Field(..., description="De-anonymized SQL query executed against the database", example="SELECT customers.name, customers.revenue FROM customers ORDER BY customers.revenue DESC LIMIT 5")
    results: list = Field(..., description="Query result row objects", example=[{"name": "Alice", "revenue": 15000.0}])
    rows_returned: int = Field(..., description="Total row count returned", example=1)
    execution_time_ms: float = Field(..., description="Total processing latency in milliseconds", example=142.5)
    cache_hit: bool = Field(..., description="Indicates whether result was served from Redis cache", example=False)
    llm_provider: str = Field(..., description="LLM provider that generated the query (gcp.gemini, nvidia.nim, or cache)", example="gcp.gemini")
    message: str = Field(..., description="Human-readable response message", example="Query processed successfully")

class ErrorResponse(BaseModel):
    code: str = Field(..., description="Machine-readable error code", example="SQL_VALIDATION_FAILED")
    message: str = Field(..., description="Human-readable error explanation", example="Generated SQL query failed safety validation: Forbidden keyword detected: DROP")
    request_id: str = Field(..., description="Unique request correlation ID", example="8f3b2d10-410a-4ca1-aaed-08d75620f30d")

@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        200: {"description": "Query executed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid or empty query prompt"},
        500: {"model": ErrorResponse, "description": "Database execution error"},
        502: {"model": ErrorResponse, "description": "SQL validation error or LLM provider failure"}
    },
    summary="Translate Natural Language to SQL and Execute",
    description="Anonymizes schema, routes prompt to AI provider, validates generated SQL, de-anonymizes SQL, and executes on read-only database."
)
async def process_query(request: QueryRequest):
    start_time = time.time()

    if not request.question or not request.question.strip():
        raise InvalidQueryError("Natural language question prompt cannot be empty")

    cached = get_cached_result(request.question, request.database_id, request.user_id)
    if cached:
        execution_time = (time.time() - start_time) * 1000
        return QueryResponse(
            query_id=cached["query_id"],
            sql_generated=cached["sql_generated"],
            results=cached["results"],
            rows_returned=len(cached["results"]),
            execution_time_ms=round(execution_time, 2),
            cache_hit=True,
            llm_provider=cached.get("llm_provider", "cache"),
            message="Result served from cache"
        )

    proxy = PrivacyProxy(database_id=request.database_id)
    anonymized_schema = proxy.anonymize_schema(SAMPLE_SCHEMA)

    schema_with_hints = {}
    forward_map = proxy.get_forward_mapping()

    for real_table, anon_table in forward_map.items():
        if real_table not in SAMPLE_SCHEMA:
            continue
        anon_cols = anonymized_schema.get(anon_table, [])
        real_cols = SAMPLE_SCHEMA[real_table]
        col_hints = COLUMN_HINTS.get(real_table, {})

        col_descriptions = []
        for real_col, anon_col in zip(real_cols, anon_cols):
            hint = col_hints.get(real_col, "text")
            col_descriptions.append(f"{anon_col} ({hint})")

        schema_with_hints[anon_table] = {
            # The anonymized name only. Sending the real table name here
            # would undo the anonymization in the same prompt that applies
            # it, since the LLM receives both halves together.
            "hint": f"table {anon_table}",
            "columns": anon_cols,
            "col_descriptions": col_descriptions
        }

    try:
        sql, provider = llm_router.generate_sql(
            question=request.question,
            anonymized_schema=anonymized_schema,
            schema_hints=schema_with_hints
        )
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"LLM provider error: {str(e)}")
        log_query(
            user_id=request.user_id,
            database_id=request.database_id,
            natural_language=request.question,
            execution_time_ms=execution_time,
            success=False,
            error_message=f"LLM provider error: {str(e)}"
        )
        raise LLMProviderError()

    is_valid, reason = validator.validate(sql)
    if not is_valid:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Validation failed: {reason}")
        log_query(
            user_id=request.user_id,
            database_id=request.database_id,
            natural_language=request.question,
            sql_generated=sql,
            execution_time_ms=execution_time,
            cache_hit=False,
            llm_provider=provider,
            success=False,
            error_message=f"Validation failed: {reason}"
        )
        raise SQLValidationError()

    try:
        # De-anonymize ONLY on the success path after validation passes
        real_sql = proxy.deanonymize_sql(sql)
        results = execute_query(real_sql)
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Database execution error: {str(e)}")
        log_query(
            user_id=request.user_id,
            database_id=request.database_id,
            natural_language=request.question,
            execution_time_ms=execution_time,
            success=False,
            error_message=f"Database execution error: {str(e)}"
        )
        raise DatabaseExecutionError()



    execution_time = (time.time() - start_time) * 1000

    result_to_cache = {
        "query_id": "",
        "sql_generated": real_sql,
        "results": results,
        "llm_provider": provider
    }

    query_id = log_query(
        user_id=request.user_id,
        database_id=request.database_id,
        natural_language=request.question,
        sql_generated=real_sql,
        execution_time_ms=execution_time,
        cache_hit=False,
        llm_provider=provider,
        success=True
    )

    result_to_cache["query_id"] = query_id
    cache_result(request.question, request.database_id, request.user_id, result_to_cache)

    return QueryResponse(
        query_id=query_id,
        sql_generated=real_sql,
        results=results,
        rows_returned=len(results),
        execution_time_ms=round(execution_time, 2),
        cache_hit=False,
        llm_provider=provider,
        message="Query processed successfully"
    )

