import logging
import uuid
from datetime import datetime, timezone
from app.services.aws_clients import get_dynamodb_resource, get_dynamodb_client
from app.config import settings

logger = logging.getLogger(__name__)

TABLE_NAME = settings.dynamodb_table

def create_table_if_not_exists():
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

    return query_id

def get_query_log(query_id: str) -> dict:
    table = get_dynamodb_resource().Table(TABLE_NAME)
    response = table.get_item(Key={"query_id": query_id})
    return response.get("Item")
