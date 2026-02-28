from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    app_name: str = "QueryGuard"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/queryguard"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # AI Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # JWT Auth
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    dynamodb_table: str = "queryguard-audit-logs"
    
    # Query limits
    max_rows: int = 10000
    query_timeout: int = 30
    rate_limit_per_day: int = 100

    class Config:
        env_file = ".env"

settings = Settings()
