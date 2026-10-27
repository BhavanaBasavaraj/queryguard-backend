import boto3
from botocore.config import Config
from app.config import settings

fast_boto_config = Config(
    connect_timeout=1.0,
    read_timeout=1.0,
    retries={'max_attempts': 1}
)

def get_dynamodb_client():
    return boto3.client(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        endpoint_url="http://localhost:8001",  # local DynamoDB
        config=fast_boto_config
    )

def get_dynamodb_resource():
    return boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        endpoint_url="http://localhost:8001",  # local DynamoDB
        config=fast_boto_config
    )

