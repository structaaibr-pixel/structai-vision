from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://structai:structai@db:5432/structai"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "structai"
    minio_secret_key: str = "structai123"
    minio_bucket: str = "structai"
    minio_secure: bool = False
    nodeodm_host: str = "nodeodm"
    nodeodm_port: int = 3000
    jwt_secret: str = "dev-secret"
    jwt_expire_minutes: int = 1440
    odm_quality: str = "high"  # high | medium


settings = Settings()
