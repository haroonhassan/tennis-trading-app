"""Application configuration."""

from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings."""
    
    # Server configuration
    app_name: str = "Tennis Trading API"
    debug: bool = False
    
    # Provider configuration
    enabled_providers: str = "betfair"  # Comma-separated list
    primary_provider: str = "betfair"
    
    # Betfair settings
    betfair_username: Optional[str] = None
    betfair_password: Optional[str] = None
    betfair_app_key: Optional[str] = None
    betfair_cert_path: Optional[str] = None
    
    # WebSocket settings
    ws_ping_interval: int = 30
    ws_max_connections: int = 100
    
    # Cache settings
    cache_ttl: int = 60
    update_interval: int = 30
    
    class Config:
        env_file = "../.env"  # Use .env from main folder
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields in .env