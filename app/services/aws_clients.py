import boto3
from app.config import settings

def get_dynamodb_client():
    return boto3.client(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        endpoint_url="http://localhost:8001"  # local DynamoDB
    )

def get_dynamodb_resource():
    return boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        endpoint_url="http://localhost:8001"  # local DynamoDB
    )
