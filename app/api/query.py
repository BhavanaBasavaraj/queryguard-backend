import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.privacy_proxy import PrivacyProxy
from app.core.llm_router import LLMRouter
from app.core.validator import SQLValidator
from app.core.executor import execute_query
from app.core.cache import get_cached_result, cache_result
from app.utils.audit import log_query

router = APIRouter()
llm_router = LLMRouter()
validator = SQLValidator()

SAMPLE_SCHEMA = {
    "customers": ["id", "name", "email", "revenue", "created_at"],
    "orders": ["id", "customer_id", "total", "status", "created_at"],
    "products": ["id", "name", "price", "category", "stock"]
}

# Column hints tell AI what each column type is — without revealing real names
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
    question: str
    database_id: str
    user_id: str

class QueryResponse(BaseModel):
    query_id: str
    sql_generated: str
    results: list
    rows_returned: int
    execution_time_ms: float
    cache_hit: bool
    llm_provider: str
    message: str

@router.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    start_time = time.time()

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

    try:
        proxy = PrivacyProxy(database_id=request.database_id)
        anonymized_schema = proxy.anonymize_schema(SAMPLE_SCHEMA)

        # Build rich schema hints with column type info
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
                "hint": f"table {anon_table}",
                "columns": anon_cols,
                "col_descriptions": col_descriptions
            }

        sql, provider = llm_router.generate_sql(
            question=request.question,
            anonymized_schema=anonymized_schema,
            schema_hints=schema_with_hints
        )

        is_valid, reason = validator.validate(sql)
        if not is_valid:
            execution_time = (time.time() - start_time) * 1000
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
            raise HTTPException(
                status_code=400,
                detail=f"Generated SQL failed validation: {reason}"
            )

        real_sql = proxy.deanonymize_sql(sql)
        results = execute_query(real_sql)
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

    except HTTPException:
        raise
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        log_query(
            user_id=request.user_id,
            database_id=request.database_id,
            natural_language=request.question,
            execution_time_ms=execution_time,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
