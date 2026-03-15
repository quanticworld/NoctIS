"""Application configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    app_name: str = "NoctIS"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # CORS settings
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Default search settings
    default_search_path: str = "/mnt/osint"
    default_threads: int = 8
    default_max_filesize: str = "100M"
    max_threads: int = 16

    # WebSocket settings
    ws_heartbeat_interval: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
