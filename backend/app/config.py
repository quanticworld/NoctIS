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
    default_search_path: str = "/"
    default_threads: int = 8
    default_max_filesize: str = "100M"
    max_threads: int = 16

    # WebSocket settings
    ws_heartbeat_interval: int = 30

    # ClickHouse settings
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000  # Native protocol
    clickhouse_http_port: int = 8123  # HTTP interface
    clickhouse_user: str = "default"
    clickhouse_password: str = "noctis_dev_clickhouse_password"
    clickhouse_database: str = "noctis"
    clickhouse_batch_size: int = 100000  # Bulk insert batch size
    clickhouse_compression: str = "lz4"  # Compression algorithm (lz4, zstd, none)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
