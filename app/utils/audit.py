import uuid
import logging
from datetime import datetime, timezone
from app.config import settings
from app.services.aws_clients import get_dynamodb_resource, get_dynamodb_client

logger = logging.getLogger(__name__)

# Audit writes fail open so a logging outage cannot stop query serving.
# That makes failures invisible by default, so they are counted and logged
# at ERROR rather than WARNING. Queue-and-retry is the better answer and is
# on the roadmap.
_audit_failures = 0


def audit_failure_count() -> int:
    """Number of audit writes that have failed since process start."""
    return _audit_failures

TABLE_NAME = settings.dynamodb_table

def create_table_if_not_exists():
    try:
        client = get_dynamodb_client()
        existing = client.list_tables()["TableNames"]
        if TABLE_NAME in existing:
            return

        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "query_id", "KeyType": "HASH"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "query_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        logger.info(f"Created DynamoDB table: {TABLE_NAME}")
    except Exception as e:
        logger.warning(f"Failed to create/verify DynamoDB audit table: {e}")

def log_query(
    user_id: str,
    database_id: str,
    natural_language: str,
    sql_generated: str = None,
    execution_time_ms: float = None,
    cache_hit: bool = False,
    llm_provider: str = None,
    success: bool = True,
    error_message: str = None
) -> str:
    query_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        table = get_dynamodb_resource().Table(TABLE_NAME)
        table.put_item(Item={
            "query_id": query_id,
            "user_id": user_id,
            "database_id": database_id,
            "natural_language": natural_language,
            "sql_generated": sql_generated or "",
            "execution_time_ms": str(execution_time_ms or 0),
            "cache_hit": cache_hit,
            "llm_provider": llm_provider or "",
            "success": success,
            "error_message": error_message or "",
            "timestamp": timestamp
        })
        logger.debug("audit row written: %s", query_id)
    except Exception as e:
        global _audit_failures
        _audit_failures += 1
        logger.error(
            "AUDIT WRITE FAILED (%d since start) for query_id=%s user=%s: %s",
            _audit_failures, query_id, user_id, e,
        )

    return query_id

def get_query_log(query_id: str) -> dict:
    try:
        table = get_dynamodb_resource().Table(TABLE_NAME)
        response = table.get_item(Key={"query_id": query_id})
        return response.get("Item")
    except Exception as e:
        logger.warning(f"DynamoDB audit log retrieval failed: {e}")
        return None

