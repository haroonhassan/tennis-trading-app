"""Application configuration."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Tennis Trading API"
    
    # Betfair Settings
    BETFAIR_USERNAME: Optional[str] = None
    BETFAIR_PASSWORD: Optional[str] = None
    BETFAIR_APP_KEY: Optional[str] = None
    BETFAIR_CERT_FILE: Optional[str] = None
    
    # Database Settings
    DATABASE_URL: str = "sqlite:///./tennis_trading.db"
    
    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379"
    
    # WebSocket Settings
    WS_MESSAGE_QUEUE: str = "redis://localhost:6379/1"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000"]
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()