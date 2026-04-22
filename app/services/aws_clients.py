import boto3
from app.config import settings

def _get_boto_kwargs() -> dict:
    kwargs = dict(
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return kwargs

def get_dynamodb_client():
    return boto3.client("dynamodb", **_get_boto_kwargs())

def get_dynamodb_resource():
    return boto3.resource("dynamodb", **_get_boto_kwargs())
