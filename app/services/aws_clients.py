import boto3
from botocore.config import Config
from app.config import settings

# Short timeouts: the audit path must never slow down a user request.
fast_boto_config = Config(
    connect_timeout=1.0,
    read_timeout=1.0,
    retries={"max_attempts": 1},
)


def _client_kwargs() -> dict:
    """Build boto3 kwargs for DynamoDB.

    When dynamodb_endpoint_url is set we are talking to DynamoDB Local,
    which requires credentials to be present but does not validate them.
    When it is empty, boto3 resolves real credentials from the environment
    or instance role in the normal way.
    """
    kwargs = {
        "region_name": settings.aws_region,
        "config": fast_boto_config,
    }
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        kwargs["aws_access_key_id"] = "local"
        kwargs["aws_secret_access_key"] = "local"
    return kwargs


def get_dynamodb_client():
    return boto3.client("dynamodb", **_client_kwargs())


def get_dynamodb_resource():
    return boto3.resource("dynamodb", **_client_kwargs())
