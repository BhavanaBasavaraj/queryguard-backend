from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "QueryGuard"
    debug: bool = False
    database_url: str = "postgresql://user:password@localhost:5432/queryguard"
    redis_url: str = "redis://localhost:6379"
    gemini_api_key: str = ""
    nvidia_api_key: str = ""
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    dynamodb_table: str = "queryguard-audit-logs"
    max_rows: int = 10000
    query_timeout: int = 30
    rate_limit_per_day: int = 100

    class Config:
        env_file = ".env"

settings = Settings()
