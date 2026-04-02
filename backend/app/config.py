"""Application configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    app_name: str = "NoctIS"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # CORS settings
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://192.168.1.44"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Default search settings
    default_search_path: str = "/breaches"
    default_threads: int = 8
    default_max_filesize: str = "100M"
    max_threads: int = 16

    # WebSocket settings
    ws_heartbeat_interval: int = 30

    # Meilisearch settings
    meilisearch_host: str = "localhost"
    meilisearch_port: int = 7700
    meilisearch_master_key: str = "noctis_dev_meilisearch_key"
    meilisearch_timeout: int = 600  # 10 minutes for large datasets
    meilisearch_batch_size: int = 100000  # Large batch for async indexing (100k docs per batch)
    meilisearch_async_mode: bool = True  # Don't wait for indexing to complete

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
